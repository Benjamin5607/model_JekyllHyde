#!/usr/bin/env python3
"""Retry Oracle Cloud VM.Standard.A1.Flex launch until capacity is available.

Requires OCI CLI configured (`oci setup config`). Works on Windows and Linux.

Usage:
  python deploy/oracle/retry_a1_instance.py --discover
  python deploy/oracle/retry_a1_instance.py --discover-regions
  python deploy/oracle/retry_a1_instance.py --config deploy/oracle/retry_a1.config.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_FILE = Path(__file__).resolve().parent / "retry_a1.log"

CAPACITY_MARKERS = (
    "out of capacity",
    "out of host capacity",
    "Out of capacity",
    "Out of host capacity",
    "OutOfCapacity",
    "limit exceeded",
)

# Popularity-ordered ARM free-tier regions (skipped if no public subnet).
DEFAULT_FALLBACK_REGIONS = (
    "ap-kulai-2",
    "ap-tokyo-1",
    "ap-osaka-1",
    "ap-singapore-1",
    "ap-seoul-1",
    "ap-sydney-1",
    "ap-mumbai-1",
    "us-phoenix-1",
    "us-ashburn-1",
    "eu-frankfurt-1",
    "uk-london-1",
)


class RetryableLaunchError(RuntimeError):
    def __init__(self, message: str, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass
class RegionTarget:
    region: str
    subnet_id: str = ""
    image_id: str = ""
    ads: list[str] = field(default_factory=list)
    ad_index: int = 0

    def next_ad(self) -> str:
        if not self.ads:
            raise RuntimeError(f"No ADs for region {self.region}")
        ad = self.ads[self.ad_index % len(self.ads)]
        self.ad_index += 1
        return ad


class OciRegion:
    current: str | None = None


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def expand_path(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


def log_line(message: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {message}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def short_oci_error(detail: str) -> str:
    code = re.search(r'"code":\s*"([^"]+)"', detail)
    message = re.search(r'"message":\s*"([^"]+)"', detail)
    if message:
        prefix = code.group(1) if code else "ServiceError"
        return f"{prefix}: {message.group(1)}"
    return detail.splitlines()[0][:160]


def run_oci(
    args: list[str],
    *,
    check: bool = True,
    timeout_sec: int = 180,
    region: str | None = None,
) -> subprocess.CompletedProcess[str]:
    active_region = region or OciRegion.current
    cmd = ["oci"]
    if active_region:
        cmd.extend(["--region", active_region])
    cmd.extend([*args, "--output", "json"])
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        raise RetryableLaunchError(
            f"OCI CLI timed out after {timeout_sec}s",
            "timeout",
        ) from exc
    except FileNotFoundError as exc:
        raise SystemExit(
            "OCI CLI not found. Install: pip install oci-cli\n"
            "Then run: oci setup config"
        ) from exc

    if check and proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "unknown error"
        raise RuntimeError(detail)
    return proc


def oci_json(args: list[str], *, region: str | None = None) -> Any:
    proc = run_oci(args, region=region)
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)


def read_profile_region() -> str:
    config_path = expand_path("~/.oci/config")
    if not config_path.is_file():
        raise SystemExit("~/.oci/config not found. Run: oci setup config")
    for line in config_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("region="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("region not found in ~/.oci/config")


def load_config(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    required = ("compartment_id", "ssh_public_key_file", "display_name")
    missing = [k for k in required if not data.get(k)]
    if missing:
        raise SystemExit(f"Config missing required keys: {', '.join(missing)}")
    if not data.get("regions") and not data.get("subnet_id"):
        raise SystemExit("Set subnet_id or a non-empty regions list in config.")
    return data


def read_ssh_public_key(path: str) -> str:
    key_path = expand_path(path)
    if not key_path.is_file():
        raise SystemExit(f"SSH public key not found: {key_path}")
    key = key_path.read_text(encoding="utf-8").strip()
    if not key:
        raise SystemExit(f"SSH public key file is empty: {key_path}")
    return key


def tenancy_ocid() -> str:
    config_path = expand_path("~/.oci/config")
    if not config_path.is_file():
        raise SystemExit("~/.oci/config not found. Run: oci setup config")
    for line in config_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("tenancy="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("tenancy OCID not found in ~/.oci/config")


def parse_region_entries(cfg: dict[str, Any]) -> list[RegionTarget]:
    entries = cfg.get("regions")
    if entries:
        targets: list[RegionTarget] = []
        for entry in entries:
            if isinstance(entry, str):
                targets.append(RegionTarget(region=entry))
            else:
                targets.append(
                    RegionTarget(
                        region=entry["region"],
                        subnet_id=entry.get("subnet_id", ""),
                        image_id=entry.get("image_id", ""),
                    )
                )
        return targets

    return [
        RegionTarget(
            region=read_profile_region(),
            subnet_id=cfg.get("subnet_id", ""),
            image_id=cfg.get("image_id", ""),
        )
    ]


def discover_public_subnet(compartment_id: str, region: str) -> str | None:
    try:
        subnets = oci_json(
            ["network", "subnet", "list", "--compartment-id", compartment_id, "--limit", "100"],
            region=region,
        )
    except RuntimeError:
        return None
    if not subnets:
        return None
    for sn in subnets.get("data", []):
        if sn.get("prohibit-public-ip-on-vnic") is False:
            return sn["id"]
    return None


def prepare_region_targets(cfg: dict[str, Any]) -> list[RegionTarget]:
    compartment_id = cfg["compartment_id"]
    raw = parse_region_entries(cfg)
    if not raw:
        raw = [RegionTarget(region=r) for r in DEFAULT_FALLBACK_REGIONS]

    ready: list[RegionTarget] = []
    seen: set[str] = set()
    for target in raw:
        if target.region in seen:
            continue
        seen.add(target.region)

        if not target.subnet_id:
            subnet_id = discover_public_subnet(compartment_id, target.region)
            if not subnet_id:
                log_line(f"skip region {target.region}: no public subnet (create VCN there or set subnet_id)")
                continue
            target.subnet_id = subnet_id
            log_line(f"region {target.region}: auto-selected subnet {subnet_id}")

        ads = list_availability_domains(compartment_id, target.region)
        if not ads:
            log_line(f"skip region {target.region}: no availability domains")
            continue
        target.ads = ads
        ready.append(target)

    return ready


def list_availability_domains(compartment_id: str, region: str) -> list[str]:
    tenancy = tenancy_ocid()
    payload = oci_json(
        ["iam", "availability-domain", "list", "--compartment-id", tenancy],
        region=region,
    )
    return [item["name"] for item in payload.get("data", [])]


def resolve_image_id(
    compartment_id: str,
    shape: str,
    region: str,
    image_id: str,
) -> str:
    if image_id:
        return image_id
    tenancy = tenancy_ocid()
    payload = oci_json(
        [
            "compute",
            "image",
            "list",
            "--compartment-id",
            tenancy,
            "--operating-system",
            "Canonical Ubuntu",
            "--operating-system-version",
            "22.04",
            "--shape",
            shape,
            "--sort-by",
            "TIMECREATED",
            "--sort-order",
            "DESC",
            "--limit",
            "1",
        ],
        region=region,
    )
    images = payload.get("data", [])
    if not images:
        raise RuntimeError(f"No Ubuntu 22.04 ARM image in region {region}")
    chosen = images[0]
    return chosen["id"]


def is_capacity_error(message: str) -> bool:
    lower = message.lower()
    if any(marker.lower() in lower for marker in CAPACITY_MARKERS):
        return True
    return "capacity" in lower and ("out of" in lower or "internalerror" in lower)


def is_rate_limit_error(message: str) -> bool:
    lower = message.lower()
    return (
        "toomanyrequests" in lower
        or "too many requests" in lower
        or '"status": 429' in lower
        or '"code": "toomanyrequests"' in lower
    )


def classify_launch_error(message: str) -> str | None:
    if is_rate_limit_error(message):
        return "rate_limit"
    if is_capacity_error(message):
        return "capacity"
    lower = message.lower()
    if any(x in lower for x in ("timed out", "timeout", "connection", "temporary failure")):
        return "timeout"
    return None


def launch_instance(
    cfg: dict[str, Any],
    *,
    region: str,
    ad: str,
    subnet_id: str,
    ssh_key: str,
    image_id: str,
) -> dict[str, Any]:
    shape_config = json.dumps(
        {"ocpus": int(cfg.get("ocpus", 4)), "memoryInGBs": int(cfg.get("memory_in_gbs", 24))}
    )
    metadata = json.dumps({"ssh_authorized_keys": ssh_key})
    args = [
        "compute",
        "instance",
        "launch",
        "--availability-domain",
        ad,
        "--compartment-id",
        cfg["compartment_id"],
        "--shape",
        cfg.get("shape", "VM.Standard.A1.Flex"),
        "--shape-config",
        shape_config,
        "--image-id",
        image_id,
        "--subnet-id",
        subnet_id,
        "--display-name",
        cfg["display_name"],
        "--metadata",
        metadata,
        "--assign-public-ip",
        "true" if cfg.get("assign_public_ip", True) else "false",
    ]
    boot_gb = cfg.get("boot_volume_size_in_gbs")
    if boot_gb:
        args.extend(["--boot-volume-size-in-gbs", str(int(boot_gb))])

    timeout_sec = int(cfg.get("oci_request_timeout_seconds", 180))
    proc = run_oci(args, check=False, timeout_sec=timeout_sec, region=region)
    if proc.returncode == 0:
        return json.loads(proc.stdout)

    detail = proc.stderr.strip() or proc.stdout.strip()
    reason = classify_launch_error(detail)
    if reason:
        raise RetryableLaunchError(detail, reason)
    raise RuntimeError(detail)


def wait_for_public_ip(instance_id: str, region: str, timeout_sec: int = 300) -> str | None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        payload = oci_json(
            ["compute", "instance", "get", "--instance-id", instance_id],
            region=region,
        )
        vnic_attachments = oci_json(
            [
                "compute",
                "vnic-attachment",
                "list",
                "--compartment-id",
                payload["data"]["compartment-id"],
                "--instance-id",
                instance_id,
            ],
            region=region,
        )
        for att in vnic_attachments.get("data", []):
            vnic = oci_json(["network", "vnic", "get", "--vnic-id", att["vnic-id"]], region=region)
            ip = vnic["data"].get("public-ip")
            if ip:
                return ip
        time.sleep(10)
    return None


def cmd_discover(compartment_id: str | None, region: str | None) -> None:
    tenancy = tenancy_ocid()
    cid = compartment_id or tenancy
    active_region = region or read_profile_region()
    print(f"=== OCI discover ({active_region}) ===")
    print(f"tenancy_ocid: {tenancy}")
    print(f"compartment_id: {cid}")
    print()

    print("Availability domains:")
    for ad in list_availability_domains(cid, active_region):
        print(f"  - {ad}")
    print()

    print("Public subnets:")
    subnet_id = discover_public_subnet(cid, active_region)
    subnets = oci_json(
        ["network", "subnet", "list", "--compartment-id", cid, "--limit", "50"],
        region=active_region,
    )
    for sn in subnets.get("data", []):
        public = sn.get("prohibit-public-ip-on-vnic") is False
        mark = " <-- use this" if public and sn["id"] == subnet_id else ""
        print(
            f"  - {sn.get('display-name', '(no name)')} | {sn['id']} | public={public}{mark}"
        )
    if not subnets.get("data"):
        eprint("  (none - create a VCN + public subnet in this region)")
    print()


def cmd_discover_regions(cfg_path: Path) -> None:
    cfg = load_config(cfg_path)
    configured = {
        entry["region"]: entry.get("subnet_id", "")
        for entry in (cfg.get("regions") or [])
        if isinstance(entry, dict) and entry.get("region")
    }
    print("=== Multi-region subnet scan ===")
    for region in DEFAULT_FALLBACK_REGIONS:
        subnet_id = configured.get(region) or discover_public_subnet(cfg["compartment_id"], region)
        if subnet_id:
            ads = list_availability_domains(cfg["compartment_id"], region)
            src = "config" if configured.get(region) else "discovered"
            print(f"  OK  {region} | subnet={subnet_id} | ADs={len(ads)} | {src}")
        else:
            print(f"  --  {region} | no public subnet")
    print()
    print("If only home region works: python deploy/oracle/subscribe_regions.py --wait")


def cmd_retry(cfg_path: Path, interval: int | None, max_attempts: int | None) -> None:
    cfg = load_config(cfg_path)
    ssh_key = read_ssh_public_key(cfg["ssh_public_key_file"])
    targets = prepare_region_targets(cfg)
    if not targets:
        raise SystemExit(
            "No usable regions. Create a VCN + public subnet in at least one region,\n"
            "or set regions[].subnet_id in retry_a1.config.json"
        )

    sleep_sec = interval if interval is not None else int(cfg.get("retry_interval_seconds", 120))
    limit = max_attempts if max_attempts is not None else int(cfg.get("max_attempts", 0))
    region_switch_delay = int(cfg.get("region_switch_delay_seconds", 15))
    shape = cfg.get("shape", "VM.Standard.A1.Flex")

    image_cache: dict[str, str] = {}

    print("=== Oracle A1.Flex capacity retry (multi-region) ===")
    print(f"Config: {cfg_path}")
    print(f"Shape: {shape} ({cfg.get('ocpus', 4)} OCPU / {cfg.get('memory_in_gbs', 24)} GB)")
    print(f"Regions: {', '.join(t.region for t in targets)}")
    print(f"Interval (full round): {sleep_sec}s | max_attempts: {limit or 'unlimited'}")
    print(f"Log: {LOG_FILE}")
    print("Press Ctrl+C to stop.\n")
    log_line(f"retry loop started; regions={[t.region for t in targets]}")

    attempt = 0
    region_index = 0
    regions_failed_this_round = 0

    try:
        while True:
            attempt += 1
            if limit and attempt > limit:
                raise SystemExit(f"Stopped after {limit} attempts without success.")

            target = targets[region_index % len(targets)]
            OciRegion.current = target.region
            ad = target.next_ad()

            if target.region not in image_cache:
                image_cache[target.region] = resolve_image_id(
                    cfg["compartment_id"],
                    shape,
                    target.region,
                    target.image_id or cfg.get("image_id", ""),
                )
                log_line(
                    f"region {target.region}: image {image_cache[target.region]}"
                )
            image_id = image_cache[target.region]

            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            print(
                f"[{ts}] attempt {attempt} - region {target.region} - AD {ad} ...",
                flush=True,
            )

            try:
                result = launch_instance(
                    cfg,
                    region=target.region,
                    ad=ad,
                    subnet_id=target.subnet_id,
                    ssh_key=ssh_key,
                    image_id=image_id,
                )
            except RetryableLaunchError as exc:
                label = short_oci_error(str(exc))
                if exc.reason == "capacity":
                    regions_failed_this_round += 1
                    region_index += 1
                    if regions_failed_this_round >= len(targets):
                        regions_failed_this_round = 0
                        wait = sleep_sec
                        log_line(
                            f"attempt {attempt} all regions full; sleep {wait}s "
                            f"({label})"
                        )
                        print(f"  all regions full: {label}")
                    else:
                        wait = region_switch_delay
                        next_region = targets[region_index % len(targets)].region
                        log_line(
                            f"attempt {attempt} {target.region} full -> switch to {next_region}; "
                            f"sleep {wait}s ({label})"
                        )
                        print(f"  capacity full in {target.region} -> next region {next_region}")
                    print(f"  sleeping {wait}s\n", flush=True)
                    time.sleep(wait)
                    continue

                if exc.reason == "rate_limit":
                    wait = int(cfg.get("rate_limit_interval_seconds", max(sleep_sec * 5, 300)))
                    log_line(f"attempt {attempt} rate limited: {label}; sleep {wait}s")
                    print(f"  rate limited (429): {label}")
                else:
                    wait = int(cfg.get("timeout_interval_seconds", max(sleep_sec * 2, 180)))
                    log_line(f"attempt {attempt} timeout/transient: {label}; sleep {wait}s")
                    print(f"  timeout/transient: {label}")
                print(f"  sleeping {wait}s\n", flush=True)
                time.sleep(wait)
                continue
            except Exception as exc:
                wait = int(cfg.get("timeout_interval_seconds", max(sleep_sec * 2, 180)))
                log_line(f"attempt {attempt} unexpected error: {exc}; sleep {wait}s")
                print(f"  unexpected error: {exc}")
                print(f"  sleeping {wait}s (will retry)\n", flush=True)
                time.sleep(wait)
                continue

            instance = result["data"]
            instance_id = instance["id"]
            log_line(f"SUCCESS region={target.region} instance_id={instance_id}")
            print("\nSUCCESS - instance created!")
            print(f"  region: {target.region}")
            print(f"  instance_id: {instance_id}")
            print(f"  display_name: {instance.get('display-name')}")
            print(f"  lifecycle_state: {instance.get('lifecycle-state')}")

            print("  waiting for public IP ...", flush=True)
            public_ip = wait_for_public_ip(instance_id, target.region)
            if public_ip:
                print(f"  public_ip: {public_ip}")
                print(f"\nSSH: ssh -i ~/.ssh/oci_jekyll_hyde.key ubuntu@{public_ip}")
                print("Then: git clone <repo> && bash deploy/oracle/setup.sh")
            else:
                print("  public IP not ready yet - check OCI Console > Instances.")
            return

    except KeyboardInterrupt:
        print("\nStopped by user.")
        raise SystemExit(0) from None


def main() -> None:
    parser = argparse.ArgumentParser(description="Retry Oracle A1.Flex instance launch.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("deploy/oracle/retry_a1.config.json"),
        help="Path to JSON config",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Print ADs/subnets for one region (default: profile region).",
    )
    parser.add_argument(
        "--discover-regions",
        action="store_true",
        help="Scan DEFAULT_FALLBACK_REGIONS for public subnets.",
    )
    parser.add_argument("--compartment-id", help="Compartment for --discover.")
    parser.add_argument("--region", help="Region for --discover.")
    parser.add_argument("--interval", type=int, help="Seconds between full region rounds.")
    parser.add_argument("--max-attempts", type=int, help="Stop after N attempts (0=unlimited).")
    args = parser.parse_args()

    if args.discover_regions:
        if not args.config.is_file():
            raise SystemExit(f"Config not found: {args.config}")
        cmd_discover_regions(args.config)
        return

    if args.discover:
        cmd_discover(args.compartment_id, args.region)
        return

    if not args.config.is_file():
        example = Path("deploy/oracle/retry_a1.config.example.json")
        raise SystemExit(
            f"Config not found: {args.config}\n"
            f"Copy {example} -> {args.config} and run --discover-regions"
        )

    cmd_retry(args.config, args.interval, args.max_attempts)


if __name__ == "__main__":
    main()
