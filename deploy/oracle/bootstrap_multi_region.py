#!/usr/bin/env python3
"""Create VCN + public subnet in Oracle regions that lack one (for A1 retry).

Usage:
  python deploy/oracle/bootstrap_multi_region.py
  python deploy/oracle/bootstrap_multi_region.py --dry-run
  python deploy/oracle/bootstrap_multi_region.py --update-config
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Import shared OCI helpers from retry script in same directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from retry_a1_instance import (  # noqa: E402
    DEFAULT_FALLBACK_REGIONS,
    discover_public_subnet,
    load_config,
    log_line,
    oci_json,
    parse_region_entries,
    run_oci,
    short_oci_error,
)


def short_err(msg: str) -> str:
    return short_oci_error(msg) if "ServiceError" in msg else msg[:120]

VCN_CIDR = "10.70.0.0/16"
SUBNET_CIDR = "10.70.0.0/24"
VCN_NAME = "jekyll-hyde-vcn"
SUBNET_NAME = "jekyll-hyde-public"
IGW_NAME = "jekyll-hyde-igw"

INGRESS_RULES = [
    {
        "protocol": "6",
        "source": "0.0.0.0/0",
        "isStateless": False,
        "description": "SSH",
        "tcpOptions": {"destinationPortRange": {"min": 22, "max": 22}},
    },
    {
        "protocol": "6",
        "source": "0.0.0.0/0",
        "isStateless": False,
        "description": "Jekyll-Hyde API",
        "tcpOptions": {"destinationPortRange": {"min": 8080, "max": 8080}},
    },
]

EGRESS_RULES = [
    {
        "protocol": "all",
        "destination": "0.0.0.0/0",
        "isStateless": False,
        "description": "All outbound",
        "destinationType": "CIDR_BLOCK",
    }
]


def region_subnet_from_config(cfg: dict, region: str) -> str:
    for entry in cfg.get("regions") or []:
        if isinstance(entry, dict) and entry.get("region") == region:
            return entry.get("subnet_id", "") or ""
    return cfg.get("subnet_id", "") if region == cfg.get("home_region") else ""


def bootstrap_region(
    compartment_id: str,
    region: str,
    *,
    configured_subnet: str = "",
    dry_run: bool,
) -> str | None:
    if configured_subnet:
        log_line(f"{region}: using configured subnet {configured_subnet}")
        return configured_subnet

    existing = discover_public_subnet(compartment_id, region)
    if existing:
        log_line(f"{region}: already has public subnet {existing}")
        return existing

    log_line(f"{region}: creating VCN + public subnet ...")
    if dry_run:
        print(f"  [dry-run] would bootstrap {region}")
        return None

    vcn = oci_json(
        [
            "network",
            "vcn",
            "create",
            "--compartment-id",
            compartment_id,
            "--cidr-block",
            VCN_CIDR,
            "--display-name",
            VCN_NAME,
            "--dns-label",
            "jhvcn",
        ],
        region=region,
    )["data"]
    vcn_id = vcn["id"]
    route_table_id = vcn["default-route-table-id"]
    security_list_id = vcn["default-security-list-id"]

    igw = oci_json(
        [
            "network",
            "internet-gateway",
            "create",
            "--compartment-id",
            compartment_id,
            "--vcn-id",
            vcn_id,
            "--is-enabled",
            "true",
            "--display-name",
            IGW_NAME,
        ],
        region=region,
    )["data"]

    route_rules = json.dumps(
        [
            {
                "destination": "0.0.0.0/0",
                "destinationType": "CIDR_BLOCK",
                "networkEntityId": igw["id"],
                "description": "internet",
            }
        ]
    )
    run_oci(
        [
            "network",
            "route-table",
            "update",
            "--rt-id",
            route_table_id,
            "--route-rules",
            route_rules,
            "--force",
        ],
        region=region,
    )

    run_oci(
        [
            "network",
            "security-list",
            "update",
            "--security-list-id",
            security_list_id,
            "--ingress-security-rules",
            json.dumps(INGRESS_RULES),
            "--egress-security-rules",
            json.dumps(EGRESS_RULES),
            "--force",
        ],
        region=region,
    )

    subnet = oci_json(
        [
            "network",
            "subnet",
            "create",
            "--compartment-id",
            compartment_id,
            "--vcn-id",
            vcn_id,
            "--cidr-block",
            SUBNET_CIDR,
            "--display-name",
            SUBNET_NAME,
            "--dns-label",
            "jhpublic",
            "--prohibit-public-ip-on-vnic",
            "false",
            "--route-table-id",
            route_table_id,
            "--security-list-ids",
            json.dumps([security_list_id]),
        ],
        region=region,
    )["data"]

    subnet_id = subnet["id"]
    log_line(f"{region}: created subnet {subnet_id}")
    return subnet_id


def update_config_regions(cfg_path: Path, subnet_map: dict[str, str]) -> None:
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    regions = []
    seen: set[str] = set()
    for entry in cfg.get("regions") or []:
        if isinstance(entry, str):
            region = entry
            subnet_id = subnet_map.get(region, "")
            regions.append({"region": region, "subnet_id": subnet_id} if subnet_id else {"region": region})
            seen.add(region)
        else:
            region = entry["region"]
            entry["subnet_id"] = subnet_map.get(region, entry.get("subnet_id", ""))
            regions.append(entry)
            seen.add(region)

    for region, subnet_id in subnet_map.items():
        if region not in seen and subnet_id:
            regions.append({"region": region, "subnet_id": subnet_id})

    cfg["regions"] = regions
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    log_line(f"updated {cfg_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap OCI VCN/subnet in multiple regions.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("deploy/oracle/retry_a1.config.json"),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--update-config", action="store_true", default=True)
    parser.add_argument("--no-update-config", action="store_true")
    args = parser.parse_args()

    if not args.config.is_file():
        raise SystemExit(f"Config not found: {args.config}")

    cfg = load_config(args.config)
    compartment_id = cfg["compartment_id"]

    requested = [t.region for t in parse_region_entries(cfg)]
    if not requested:
        requested = list(DEFAULT_FALLBACK_REGIONS)

    print("=== Bootstrap multi-region networking ===")
    print(f"Compartment: {compartment_id}")
    print(f"Regions: {', '.join(requested)}\n")

    subnet_map: dict[str, str] = {}
    for region in requested:
        configured = region_subnet_from_config(cfg, region)
        try:
            subnet_id = bootstrap_region(
                compartment_id,
                region,
                configured_subnet=configured,
                dry_run=args.dry_run,
            )
            if subnet_id:
                subnet_map[region] = subnet_id
                print(f"  OK  {region} -> {subnet_id}")
            elif not args.dry_run:
                # may have been existing; re-discover
                found = discover_public_subnet(compartment_id, region)
                if found:
                    subnet_map[region] = found
                    print(f"  OK  {region} -> {found} (existing)")
                else:
                    print(f"  --  {region} -> skipped")
        except Exception as exc:
            msg = str(exc)
            if "NotAuthenticated" in msg:
                hint = (
                    f"{region}: auth failed - check ~/.oci/config and API key in OCI Console"
                )
                log_line(hint)
                print(f"  FAIL {region} -> NotAuthenticated (run `oci setup config` / add API key)")
            else:
                log_line(f"{region}: bootstrap failed: {exc}")
                print(f"  FAIL {region} -> {short_err(msg)}")

    if args.update_config and not args.no_update_config and not args.dry_run and subnet_map:
        update_config_regions(args.config, subnet_map)

    print("\nDone. Run: python deploy/oracle/retry_a1_instance.py --discover-regions")


if __name__ == "__main__":
    main()
