"""Standalone MCP mesh worker — run on a separate PC or process."""

from __future__ import annotations

import argparse
import json
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from safety_eval.mcp.mesh import hub_complete, register_local_node, run_worker_local
from safety_eval.mcp.workforce import list_workers

app = FastAPI(title="Jekyll & Hyde MCP Mesh Worker", version="1.6.0")


class MeshRunRequest(BaseModel):
    task_id: str = ""
    worker: str
    args: dict[str, Any] = {}
    manager_id: str = ""


@app.get("/mesh/health")
def health() -> dict[str, Any]:
    return {"ok": True, "workers": [w["name"] for w in list_workers()]}


@app.post("/mesh/run")
def mesh_run(req: MeshRunRequest) -> dict[str, Any]:
    try:
        output = run_worker_local(req.worker, req.args)
        if req.task_id:
            hub_complete(req.task_id, ok=True, output=output)
        return {"ok": True, "worker": req.worker, "output": output}
    except Exception as exc:
        if req.task_id:
            hub_complete(req.task_id, ok=False, error=str(exc))
        raise HTTPException(500, str(exc)) from exc


@app.get("/mesh/register")
def mesh_register(node_id: str = "worker-1", port: int = 8092) -> dict[str, Any]:
    workers = [w["name"] for w in list_workers()]
    return register_local_node(node_id, workers, port=port)


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP mesh worker HTTP node")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8092)
    parser.add_argument("--node-id", default="mesh-worker-1")
    args = parser.parse_args()
    info = register_local_node(args.node_id, [w["name"] for w in list_workers()], port=args.port)
    print(json.dumps(info, indent=2))
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
