"""Manager-Worker MCP workforce — async task queue with data-only workers."""

from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "config" / "workforce.yaml"
_lock = threading.Lock()
_executor: ThreadPoolExecutor | None = None
_jobs: dict[str, WorkforceJob] = {}


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WORKERS_COMPLETE = "workers_complete"
    MANAGER_RUNNING = "manager_running"
    APPROVED = "approved"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


@dataclass
class WorkerStep:
    worker: str
    args: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    # Only run this step when an upstream worker output satisfies the condition.
    # Format: {"worker": "market_scan", "field": "count", "op": "gt", "value": 0}
    branch_if: dict[str, Any] | None = None
    attempts: int = 0


@dataclass
class WorkerResult:
    worker: str
    ok: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    elapsed_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkforceJob:
    id: str
    brief: str
    plan: list[WorkerStep]
    status: JobStatus = JobStatus.PENDING
    results: list[WorkerResult] = field(default_factory=list)
    manager_verdict: str = ""
    manager_meta: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "brief": self.brief,
            "plan": [
                {
                    "worker": s.worker,
                    "args": s.args,
                    "depends_on": s.depends_on,
                    "branch_if": s.branch_if,
                }
                for s in self.plan
            ],
            "status": self.status.value,
            "results": [r.to_dict() for r in self.results],
            "manager_verdict": self.manager_verdict,
            "manager_meta": self.manager_meta,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }


def _load_cfg() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {"workforce": {"enabled": True}}
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _jobs_path() -> Path:
    cfg = _load_cfg().get("workforce", {})
    rel = (cfg.get("paths") or {}).get("jobs", "data/learning/workforce_jobs.jsonl")
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _persist_job(job: WorkforceJob) -> None:
    cfg = _load_cfg().get("workforce", {})
    if not cfg.get("persist_jobs", True):
        return
    path = _jobs_path()
    line = json.dumps(job.to_dict(), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _executor_pool() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        workers = int(_load_cfg().get("workforce", {}).get("max_parallel_workers", 4))
        _executor = ThreadPoolExecutor(max_workers=max(2, workers), thread_name_prefix="jh-worker")
    return _executor


def _worker_market_weather(**_: Any) -> dict[str, Any]:
    from safety_eval.quant import market_weather_text

    return {"text": market_weather_text()}


def _worker_market_scan(market: str = "Korea", limit: int = 10, **_: Any) -> dict[str, Any]:
    from safety_eval.quant import MARKET_SAMPLES, scan_market_universe

    if market not in MARKET_SAMPLES:
        market = "Korea"
    rows = scan_market_universe(market, limit=max(1, min(limit, 20)))
    return {"market": market, "rows": rows, "count": len(rows)}


def _worker_quant_context(query: str = "", **_: Any) -> dict[str, Any]:
    from safety_eval.quant import build_quant_context

    q = (query or "market overview").strip()
    ctx = build_quant_context(q, mode="chat")
    if not ctx:
        return {"query": q, "resolved": False, "tickers": [], "block": ""}
    return {
        "query": q,
        "resolved": True,
        "tickers": [s.ticker for s in ctx.snapshots],
        "block": ctx.to_prompt_block(mode="chat")[:4000],
    }


def _worker_guidelines_snapshot(**_: Any) -> dict[str, Any]:
    from safety_eval.store import get_guidelines_store

    store = get_guidelines_store()
    snap = store.snapshot()
    return {
        "title": snap.title,
        "source": snap.source,
        "chars": len(store.text),
        "text": store.text[:8000],
    }


def _worker_memory_retrieve(query: str = "", **_: Any) -> dict[str, Any]:
    from safety_eval.learning.memory_store import get_rule_memory

    q = (query or "gray zone policy").strip()
    hits = get_rule_memory().retrieve(q, k=5)
    return {
        "query": q,
        "hits": [
            {
                "rule": h.entry.rule_text[:400],
                "topic": h.entry.topic,
                "score": round(h.score, 3),
                "source": h.entry.source,
            }
            for h in hits
        ],
    }


def _worker_verification_scan(text: str = "", topic: str = "", **_: Any) -> dict[str, Any]:
    from safety_eval.store import get_guidelines_store
    from safety_eval.verification.registry import run_verification

    store = get_guidelines_store()
    body = text or store.text[:2000]
    report = run_verification(
        text=body,
        topic=topic or "policy audit",
        guidelines_text=store.text,
        guidelines_title=store.title,
    )
    findings = [
        {"provider": f.provider, "finding": (f.finding or "")[:240], "ok": f.ok}
        for f in report.findings
        if f.ok and f.finding
    ][:8]
    return {
        "providers_ok": report.providers_ok,
        "findings": findings,
        "query": report.query,
    }


WORKER_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {
    "market_weather": _worker_market_weather,
    "market_scan": _worker_market_scan,
    "quant_context": _worker_quant_context,
    "guidelines_snapshot": _worker_guidelines_snapshot,
    "memory_retrieve": _worker_memory_retrieve,
    "verification_scan": _worker_verification_scan,
}


def list_workers() -> list[dict[str, str]]:
    cfg = _load_cfg().get("workers", {})
    return [
        {"name": name, "desc": cfg.get(name, {}).get("desc", "Data worker (no LLM)")}
        for name in WORKER_REGISTRY
    ]


def plan_from_brief(brief: str) -> list[WorkerStep]:
    """Heuristic planner — map one-sentence brief to worker chain."""
    low = brief.lower()
    steps: list[WorkerStep] = []

    finance = any(
        k in low
        for k in (
            "stock", "invest", "equity", "sector", "semiconductor", "it ",
            "market", "quarter", "memo", "ticker", "earnings",
        )
    )
    policy = any(
        k in low
        for k in ("gray", "grey", "policy", "guideline", "loophole", "audit", "report", "defense")
    )

    if finance:
        steps.append(WorkerStep("market_weather", {}))
        market = "Korea"
        if "usa" in low or " us " in low or "america" in low:
            market = "USA"
        elif "japan" in low:
            market = "Japan"
        elif "vietnam" in low:
            market = "Vietnam"
        steps.append(WorkerStep("market_scan", {"market": market, "limit": 10}))
        if any(k in low for k in ("vs", "analyze", "compare", "memo", "stock")):
            # quant_context runs after scan, only if scan actually returned movers
            steps.append(
                WorkerStep(
                    "quant_context",
                    {"query": brief},
                    depends_on=["market_scan"],
                    branch_if={"worker": "market_scan", "field": "count", "op": "gt", "value": 0},
                )
            )

    if policy or "report" in low:
        steps.append(WorkerStep("guidelines_snapshot", {}))
        steps.append(WorkerStep("memory_retrieve", {"query": brief}))
        # verification depends on guidelines snapshot being available first
        steps.append(
            WorkerStep(
                "verification_scan",
                {"topic": brief, "text": ""},
                depends_on=["guidelines_snapshot"],
            )
        )

    if not steps:
        steps = [
            WorkerStep("guidelines_snapshot", {}),
            WorkerStep("memory_retrieve", {"query": brief}),
            WorkerStep("market_weather", {}),
        ]
    return steps


def _plan_from_config(brief: str) -> list[WorkerStep] | None:
    """Build plan from a named pipeline in config/workforce.yaml if the brief matches."""
    pipelines = _load_cfg().get("pipelines") or {}
    if not pipelines:
        return None
    low = brief.lower()
    chosen: dict[str, Any] | None = None
    for _name, spec in pipelines.items():
        triggers = [t.lower() for t in (spec.get("triggers") or [])]
        if triggers and any(t in low for t in triggers):
            chosen = spec
            break
    if chosen is None:
        chosen = pipelines.get("default")
    if not chosen:
        return None

    steps: list[WorkerStep] = []
    for raw in chosen.get("steps", []):
        args = dict(raw.get("args") or {})
        # allow {brief} substitution in string args
        for k, v in list(args.items()):
            if isinstance(v, str):
                args[k] = v.replace("{brief}", brief)
        steps.append(
            WorkerStep(
                worker=raw["worker"],
                args=args,
                depends_on=list(raw.get("depends_on") or []),
                branch_if=raw.get("branch_if"),
            )
        )
    return steps or None


def _run_worker(step: WorkerStep) -> WorkerResult:
    import time

    start = time.perf_counter()
    fn = WORKER_REGISTRY.get(step.worker)
    if not fn:
        return WorkerResult(worker=step.worker, ok=False, error=f"unknown worker: {step.worker}")
    try:
        try:
            from safety_eval.mcp.mesh import dispatch_remote, mesh_enabled, pick_node

            if mesh_enabled() and pick_node(step.worker):
                out = dispatch_remote(step.worker, step.args)
                elapsed = int((time.perf_counter() - start) * 1000)
                return WorkerResult(
                    worker=step.worker,
                    ok=True,
                    output=out.get("output", out),
                    elapsed_ms=elapsed,
                )
        except RuntimeError:
            pass
        out = fn(**step.args)
        elapsed = int((time.perf_counter() - start) * 1000)
        return WorkerResult(worker=step.worker, ok=True, output=out, elapsed_ms=elapsed)
    except Exception as exc:
        elapsed = int((time.perf_counter() - start) * 1000)
        return WorkerResult(worker=step.worker, ok=False, error=str(exc), elapsed_ms=elapsed)


_OPS: dict[str, Callable[[Any, Any], bool]] = {
    "gt": lambda a, b: a is not None and a > b,
    "gte": lambda a, b: a is not None and a >= b,
    "lt": lambda a, b: a is not None and a < b,
    "lte": lambda a, b: a is not None and a <= b,
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "truthy": lambda a, _b: bool(a),
    "falsy": lambda a, _b: not bool(a),
}


def _branch_allows(step: WorkerStep, done: dict[str, WorkerResult]) -> bool:
    cond = step.branch_if
    if not cond:
        return True
    src = done.get(str(cond.get("worker", "")))
    if not src or not src.ok:
        return False
    value = src.output.get(cond.get("field", ""))
    op = _OPS.get(str(cond.get("op", "truthy")), _OPS["truthy"])
    try:
        return op(value, cond.get("value"))
    except TypeError:
        return False


def _inject_upstream(step: WorkerStep, done: dict[str, WorkerResult]) -> dict[str, Any]:
    """Pass upstream outputs to a dependent worker under `upstream` (workers accept **_)."""
    if not step.depends_on:
        return dict(step.args)
    upstream = {dep: done[dep].output for dep in step.depends_on if dep in done and done[dep].ok}
    merged = dict(step.args)
    if upstream:
        merged["upstream"] = upstream
    return merged


def _run_plan_sequenced(job_id: str, plan: list[WorkerStep]) -> list[WorkerResult]:
    """Execute plan honoring depends_on: independent steps parallelize, dependents wait."""
    pool = _executor_pool()
    done: dict[str, WorkerResult] = {}
    results: list[WorkerResult] = []
    pending = list(plan)
    guard = 0

    while pending and guard < len(plan) + 5:
        guard += 1
        ready = [s for s in pending if all(d in done for d in s.depends_on)]
        if not ready:
            for s in pending:
                results.append(
                    WorkerResult(worker=s.worker, ok=False, error="unresolved dependency / cycle")
                )
            break

        batch: list[WorkerStep] = []
        for step in ready:
            pending.remove(step)
            if not _branch_allows(step, done):
                skipped = WorkerResult(
                    worker=step.worker, ok=True, output={"skipped": "branch_condition_false"}
                )
                done[step.worker] = skipped
                results.append(skipped)
                continue
            batch.append(step)

        if not batch:
            continue

        futures = {}
        for step in batch:
            resolved = WorkerStep(worker=step.worker, args=_inject_upstream(step, done))
            futures[pool.submit(_run_worker, resolved)] = step
        for fut in as_completed(futures):
            step = futures[fut]
            res = fut.result()
            done[step.worker] = res
            results.append(res)

    return results


def _run_workers_job(job_id: str) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job.status = JobStatus.RUNNING
        job.updated_at = datetime.now(UTC).isoformat()
        plan = list(job.plan)

    results = _run_plan_sequenced(job_id, plan)

    with _lock:
        job = _jobs[job_id]
        job.results = results
        job.updated_at = datetime.now(UTC).isoformat()
        if any(not r.ok for r in results):
            job.status = JobStatus.FAILED
            job.error = "; ".join(r.error for r in results if r.error)[:500]
        else:
            job.status = JobStatus.WORKERS_COMPLETE
        _persist_job(job)

    cfg = _load_cfg().get("workforce", {})
    if cfg.get("auto_manager_approve", False):
        with _lock:
            ready = _jobs[job_id].status == JobStatus.WORKERS_COMPLETE
        if ready:
            manager_approve(job_id)


def delegate_brief(brief: str, *, plan: list[WorkerStep] | None = None) -> WorkforceJob:
    """Enqueue worker chain; manager stays idle until approve."""
    brief = (brief or "").strip()
    if not brief:
        raise ValueError("brief is required")

    wf_cfg = _load_cfg().get("workforce", {})
    if not wf_cfg.get("enabled", True):
        raise RuntimeError("workforce disabled in config/workforce.yaml")

    job_id = uuid.uuid4().hex[:12]
    steps = plan or _plan_from_config(brief) or plan_from_brief(brief)
    now = datetime.now(UTC).isoformat()
    job = WorkforceJob(
        id=job_id,
        brief=brief,
        plan=steps,
        status=JobStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    with _lock:
        _jobs[job_id] = job
    _persist_job(job)
    pool = _executor_pool()
    pool.submit(_run_workers_job, job_id)
    return job


def get_job(job_id: str) -> WorkforceJob | None:
    with _lock:
        return _jobs.get(job_id)


def list_jobs(limit: int = 20) -> list[dict[str, Any]]:
    with _lock:
        items = sorted(_jobs.values(), key=lambda j: j.created_at, reverse=True)
    return [j.to_dict() for j in items[:limit]]


def _format_worker_bundle(job: WorkforceJob) -> str:
    lines = [f"USER BRIEF: {job.brief}", "", "WORKER OUTPUTS:"]
    for r in job.results:
        lines.append(f"\n## {r.worker} ({'ok' if r.ok else 'fail'})")
        if r.error:
            lines.append(f"Error: {r.error}")
        else:
            lines.append(json.dumps(r.output, ensure_ascii=False, indent=2)[:2500])
    return "\n".join(lines)


def _weak_workers(job: WorkforceJob) -> list[str]:
    """Workers whose output is failed, empty, or a skipped branch — candidates to re-run."""
    weak: list[str] = []
    for r in job.results:
        if not r.ok:
            weak.append(r.worker)
            continue
        out = r.output or {}
        if out.get("skipped"):
            continue
        meaningful = {k: v for k, v in out.items() if k not in ("query", "market")}
        if not any(meaningful.values()):
            weak.append(r.worker)
    return weak


def _rerun_workers(job: WorkforceJob, worker_names: list[str]) -> None:
    """Re-execute specific workers and splice fresh results back into the job."""
    steps = [s for s in job.plan if s.worker in worker_names]
    if not steps:
        return
    fresh = _run_plan_sequenced(job.id, steps)
    by_worker = {r.worker: r for r in fresh}
    job.results = [by_worker.get(r.worker, r) for r in job.results]


def manager_approve(job_id: str) -> WorkforceJob:
    """Manager (JekyllHyde LLM) synthesizes, verifies, and re-runs weak workers with back-off."""
    import time

    with _lock:
        job = _jobs.get(job_id)
        if not job:
            raise KeyError(f"job not found: {job_id}")
        if job.status not in (JobStatus.WORKERS_COMPLETE, JobStatus.NEEDS_REVIEW):
            raise RuntimeError(f"job not ready for manager: {job.status.value}")
        job.status = JobStatus.MANAGER_RUNNING
        job.updated_at = datetime.now(UTC).isoformat()

    mgr_cfg = _load_cfg().get("manager", {})
    mode = mgr_cfg.get("mode", "jekyll")
    max_retries = int(mgr_cfg.get("max_retries", 1))
    backoff_base = float(mgr_cfg.get("retry_backoff_seconds", 2.0))
    min_score = float(mgr_cfg.get("rlaif_min_score", 85))

    try:
        from safety_eval.platform.engine import JekyllHydeEngine
        from safety_eval.learning.rlaif_gate import RlaifGate

        engine = JekyllHydeEngine()
        gate = RlaifGate()
        min_score = float(mgr_cfg.get("rlaif_min_score", gate.threshold()))
        attempts: list[dict[str, Any]] = []
        verdict_text = ""
        score = None
        approved = False

        for attempt in range(max_retries + 1):
            # Manager verifies intermediate worker outputs first; re-run weak ones with back-off
            weak = _weak_workers(job)
            if weak and attempt > 0:
                time.sleep(backoff_base * (2 ** (attempt - 1)))
                _rerun_workers(job, weak)

            bundle = _format_worker_bundle(job)
            prompt = (
                f"{bundle}\n\n"
                "--- MANAGER TASK ---\n"
                "You are the Jekyll & Hyde manager. Workers collected data without using the main LLM. "
                "Verify the worker data is sufficient, then synthesize a structured final report. "
                "Include: Executive summary, Key findings, Gray zones (if any), Recommended actions. "
                "If worker data is insufficient, say what is missing. "
                "End with a line: VERDICT: APPROVED or VERDICT: NEEDS_REVIEW"
            )
            resp = engine.complete(prompt, mode=mode)
            verdict_text = resp.content

            record = {
                "messages": [
                    {"role": "user", "content": job.brief},
                    {"role": "assistant", "content": verdict_text},
                ],
                "meta": {"quality_score": 0.8, "source": "workforce_manager"},
            }
            score = gate.score_record(record, topic=job.brief)
            approved = score.passed and score.score >= min_score
            if "NEEDS_REVIEW" in verdict_text.upper():
                approved = False

            attempts.append({
                "attempt": attempt,
                "rlaif": score.to_dict(),
                "weak_workers": weak,
                "approved": approved,
            })
            if approved or not weak:
                break

        with _lock:
            job.manager_verdict = verdict_text
            job.manager_meta = {
                "rlaif": score.to_dict() if score else {},
                "approved": approved,
                "mode": mode,
                "attempts": attempts,
                "retries_used": len(attempts) - 1,
            }
            job.status = JobStatus.APPROVED if approved else JobStatus.NEEDS_REVIEW
            job.updated_at = datetime.now(UTC).isoformat()
            _persist_job(job)
        return job
    except Exception as exc:
        with _lock:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.updated_at = datetime.now(UTC).isoformat()
            _persist_job(job)
        raise


def run_brief_sync(brief: str, *, wait_seconds: float = 120.0) -> WorkforceJob:
    """Delegate, wait for workers, then manager approve (blocking convenience)."""
    import time

    job = delegate_brief(brief)
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        current = get_job(job.id)
        if not current:
            break
        if current.status == JobStatus.WORKERS_COMPLETE:
            return manager_approve(job.id)
        if current.status in (JobStatus.FAILED, JobStatus.APPROVED, JobStatus.NEEDS_REVIEW):
            return current
        time.sleep(0.5)
    raise TimeoutError(f"workforce job {job.id} timed out after {wait_seconds}s")
