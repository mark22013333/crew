#!/usr/bin/env python3
"""Read-only approval proof verification for plan-start before state exists."""
import argparse
import json
import sys
from pathlib import Path

from importlib.util import module_from_spec, spec_from_file_location
path = Path(__file__).with_name("review-once-grant.py")
spec = spec_from_file_location("crew_review_once_proof_contract", path)
assert spec is not None and spec.loader is not None
mod = module_from_spec(spec)
spec.loader.exec_module(mod)


def main() -> int:
    p = argparse.ArgumentParser(description="Verify Host-signed approval before CREW plan-start")
    p.add_argument("--project", type=Path, default=Path("."))
    p.add_argument("--packet", required=True, type=Path)
    p.add_argument("--event", required=True, type=Path)
    p.add_argument("--signature", required=True, type=Path)
    a = p.parse_args()
    try:
        packet, event, _ = mod.verify_event(a.project.resolve(), a.packet, a.event, a.signature)
    except (mod.GrantError, OSError, ValueError, KeyError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "status": "valid_signed_human_review",
        "slug": packet["proposal"]["slug"],
        "branch": packet["proposal"]["repository"]["branch"],
        "packet_sha256": packet["packet_sha256"],
        "grant_id": event["grant_id"],
        "expires_at": event["expires_at"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
