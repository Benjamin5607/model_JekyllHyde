#!/usr/bin/env python3
"""Subscribe tenancy to extra OCI regions (required before VCN/API in those regions).

Usage:
  python deploy/oracle/subscribe_regions.py
  python deploy/oracle/subscribe_regions.py --wait
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retry_a1_instance import (  # noqa: E402
    DEFAULT_FALLBACK_REGIONS,
    load_config,
    log_line,
    oci_json,
    parse_region_entries,
    read_profile_region,
    tenancy_ocid,
)

TARGET_REGIONS = (
    "ap-tokyo-1",
    "ap-osaka-1",
    "ap-singapore-1",
    "ap-seoul-1",
    "ap-sydney-1",
    "us-phoenix-1",
    "us-ashburn-1",
)


def list_subscriptions(tenancy_id: str) -> dict[str, str]:
    payload = oci_json(
        ["iam", "region-subscription", "list", "--tenancy-id", tenancy_id]
    )
    return {item["region-name"]: item.get("status", "") for item in payload.get("data", [])}


def region_key_map() -> dict[str, str]:
    payload = oci_json(["iam", "region", "list"])
    return {item["name"]: item["key"] for item in payload.get("data", [])}


def subscribe(tenancy_id: str, region: str, keys: dict[str, str]) -> None:
    region_key = keys.get(region)
    if not region_key:
        raise RuntimeError(f"unknown region name: {region}")
    oci_json(
        [
            "iam",
            "region-subscription",
            "create",
            "--tenancy-id",
            tenancy_id,
            "--region-key",
            region_key,
        ]
    )


def wait_ready(tenancy_id: str, regions: list[str], timeout_sec: int = 900) -> None:
    deadline = time.time() + timeout_sec
    pending = set(regions)
    while pending and time.time() < deadline:
        subs = list_subscriptions(tenancy_id)
        for region in list(pending):
            status = subs.get(region, "")
            if status == "READY":
                log_line(f"region {region} is READY")
                pending.remove(region)
            else:
                log_line(f"region {region} status={status or 'PENDING'}")
        if pending:
            time.sleep(30)
    if pending:
        raise SystemExit(f"Timed out waiting for regions: {', '.join(sorted(pending))}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Subscribe OCI tenancy to more regions.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("deploy/oracle/retry_a1.config.json"),
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait until new regions reach READY (can take several minutes).",
    )
    args = parser.parse_args()

    cfg = load_config(args.config) if args.config.is_file() else {}
    tenancy_id = tenancy_ocid()
    home = read_profile_region()

    requested = [t.region for t in parse_region_entries(cfg)] if cfg else list(TARGET_REGIONS)
    requested = [r for r in requested if r != home]

    print("=== OCI region subscription ===")
    print(f"Home region: {home}")
    print(f"Target regions: {', '.join(requested) or '(none)'}\n")

    subs = list_subscriptions(tenancy_id)
    print("Currently subscribed:")
    for name, status in sorted(subs.items()):
        mark = " (home)" if name == home else ""
        print(f"  {name}: {status}{mark}")
    print()

    keys = region_key_map()
    created: list[str] = []
    for region in requested:
        if region in subs:
            print(f"  skip {region} (already subscribed: {subs[region]})")
            continue
        try:
            subscribe(tenancy_id, region, keys)
            created.append(region)
            print(f"  + subscribed {region} ({keys.get(region, '?')})")
        except Exception as exc:
            msg = str(exc)
            if "already" in msg.lower():
                print(f"  skip {region} (already subscribed)")
            elif "TenantCapacityExceeded" in msg:
                print(f"  FAIL {region}: TenantCapacityExceeded (tenancy cannot add more regions)")
            else:
                print(f"  FAIL {region}: {msg[:200]}")

    if created:
        if args.wait:
            print("\nWaiting for regions to become READY ...")
            wait_ready(tenancy_id, created)
    elif requested and not any(r in subs for r in requested):
        print(
            "\nCannot subscribe to extra regions on this tenancy (TenantCapacityExceeded).\n"
            "Oracle Free accounts are often locked to the home region only.\n"
            "Options:\n"
            "  1) Keep retrying A1.Flex in ap-kulai-2 only\n"
            "  2) Use local Ollama API (already set up)\n"
            "  3) New OCI account with home region us-phoenix-1 / us-ashburn-1 (if you need ARM elsewhere)"
        )

    print("\nDone. Next: .\\deploy\\oracle\\bootstrap_multi_region.ps1")


if __name__ == "__main__":
    main()
