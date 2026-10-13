#!/usr/bin/env python3
"""Deterministic Review Once proposal contract (pre-approval, no state writes).

Preparation NEVER approves a gate, modifies plan.md, or grants autonomy.
All approval evidence is separate and must originate from a trusted Host.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
MAX_SECONDS = 4 * 60 * 60
SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
HEX40 = re.compile(r"^[a-fA-F0-9]{40}$")
HEX64 = re.compile(r"^[a-fA-F0-9]{64}$")
AC_RE = re.compile(r"^- \[ \] AC-([1-9]\d*)\s+\S")
SPEC_DEC_RE = re.compile(r"^- D-1 \[spec\] ")
ARCH_DEC_RE = re.compile(r"^- D-[1-9]\d* \[arch\] ")
ACTION_ALLOWLIST = {"write_source", "write_tests", "generate_migration"}
DENIED_ACTIONS = (
    "execute_production_sql", "production_deploy", "git_push", "git_merge",
    "modify_secrets", "change_permissions", "auto_approve_uat",
)


class PacketError(ValueError):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise PacketError(message)


def parse_object(path: Path) -> dict[str, Any]:
    def no_duplicate(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise PacketError(f"JSON 欄位重複：{key}")
            out[key] = value
        return out
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicate)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PacketError(f"JSON 無法讀取：{path}: {exc}") from exc
    need(isinstance(value, dict), "JSON root 必須是 object")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def exact_fields(obj: Any, fields: set[str], place: str) -> dict:
    need(isinstance(obj, dict), f"{place} 必須是 object")
    need(set(obj) == fields,
         f"{place} 欄位不符：缺少 {sorted(fields - set(obj))}；多餘 {sorted(set(obj) - fields)}")
    return obj


def lines(value: Any, where: str, max_count: int, required: bool = False) -> list[str]:
    need(isinstance(value, list) and len(value) <= max_count, f"{where} 應為 <= {max_count} 行陣列")
    if required:
        need(bool(value), f"{where} 不可為空")
    for line in value:
        need(isinstance(line, str) and bool(line.strip()), f"{where} 不可有空白或非字串行")
        need("\n" not in line and "\r" not in line, f"{where} 每個條目必須只有一行")
        need(len(line) <= 1100, f"{where} 單行過長")
    return value


def validate_proposal(proposal: dict) -> dict:
    exact_fields(proposal, {"schema_version", "mode", "task_type", "slug",
                            "repository", "spec", "db", "architecture", "scope",
                            "test_policy", "max_duration_seconds"}, "proposal")
    need(type(proposal["schema_version"]) is int and proposal["schema_version"] == SCHEMA_VERSION,
         "schema_version 必須為 1")
    need(proposal["mode"] == "review_once" and proposal["task_type"] == "feature",
         "v1 僅支援 Feature Review Once")
    need(isinstance(proposal["slug"], str) and SLUG_RE.fullmatch(proposal["slug"]) is not None,
         "slug 不合法")
    need(type(proposal["max_duration_seconds"]) is int and
         proposal["max_duration_seconds"] == MAX_SECONDS, "授權時間固定為 14400 秒（4 小時）")
    need(proposal["test_policy"] in ("with_test", "bdd"), "Review Once 必須包含測試策略")

    repository = exact_fields(proposal["repository"],
                              {"full_name", "branch", "base_commit"}, "repository")
    need(isinstance(repository["full_name"], str) and
         re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository["full_name"]) is not None,
         "repository.full_name 不合法")
    need(isinstance(repository["branch"], str) and repository["branch"].strip() and
         not repository["branch"].startswith("-") and ".." not in repository["branch"] and
         " " not in repository["branch"] and len(repository["branch"]) <= 180,
         "repository.branch 不合法")
    need(isinstance(repository["base_commit"], str) and
         HEX40.fullmatch(repository["base_commit"]) is not None, "base_commit 必須是完整 Git SHA")

    spec = exact_fields(proposal["spec"], {"goal", "ac", "decisions", "risks"}, "spec")
    lines(spec["goal"], "spec.goal", 12, True)
    ac = lines(spec["ac"], "spec.ac", 15, True)
    ac_numbers = []
    for line in ac:
        m = AC_RE.match(line)
        need(m is not None, f"驗收條件必須使用 - [ ] AC-n 格式：{line}")
        ac_numbers.append(int(m.group(1)))
    need(len(set(ac_numbers)) == len(ac_numbers) and ac_numbers == sorted(ac_numbers),
         "AC-n 不可重複或倒序")
    decisions = lines(spec["decisions"], "spec.decisions", 30, True)
    need(SPEC_DEC_RE.match(decisions[0]) is not None, "spec.decisions 第一條必須是 D-1 [spec]")
    lines(spec["risks"], "spec.risks", 8)
    need(all(x.startswith("- D-") and " [spec] " in x for x in decisions),
         "spec.decisions 僅能放 [spec] 決策")

    db = exact_fields(proposal["db"], {"required", "deploy_sql", "decisions"}, "db")
    need(type(db["required"]) is bool, "db.required 必須是 boolean")
    need(isinstance(db["deploy_sql"], str), "db.deploy_sql 必須是字串")
    lines(db["decisions"], "db.decisions", 25)
    need(all(x.startswith("- D-") and " [db] " in x for x in db["decisions"]),
         "db.decisions 僅能放 [db] 決策")
    if db["required"]:
        need(bool(db["deploy_sql"].strip()), "DB_REQUIRED=true 時 deploy_sql 不可空白")
    else:
        need(not db["deploy_sql"].strip() and not db["decisions"],
             "DB_REQUIRED=false 不得挾帶 SQL 或 DB 決策")

    arch = exact_fields(proposal["architecture"], {"decisions", "risks"}, "architecture")
    adec = lines(arch["decisions"], "architecture.decisions", 25, True)
    need(all(ARCH_DEC_RE.match(x) is not None for x in adec),
         "architecture.decisions 必須是 - D-n [arch] 格式")
    lines(arch["risks"], "architecture.risks", 8)

    scope = exact_fields(proposal["scope"], {"allowed_paths", "allowed_actions"}, "scope")
    paths = lines(scope["allowed_paths"], "scope.allowed_paths", 40, True)
    need(len(set(paths)) == len(paths), "allowed_paths 不可重複")
    for value in paths:
        need(not value.startswith(("/", "\\", "~", ".")) and
             "\\" not in value and ".." not in value.split("/") and
             not value.endswith("/") and not value.startswith("**") and
             not value.startswith(".git/") and not value.startswith(".spec/"),
             f"拒絕不安全的 allowed_paths：{value}")
    actions = scope["allowed_actions"]
    need(isinstance(actions, list) and bool(actions) and len(actions) == len(set(actions))
         and set(actions) <= ACTION_ALLOWLIST, "allowed_actions 超過 v1 寫入範圍")
    return proposal


def stage_snapshots(proposal: dict) -> dict[str, str]:
    return {
        "spec": digest(proposal["spec"]),
        "db": digest(proposal["db"]),
        "architecture": digest(proposal["architecture"]),
        "scope": digest(proposal["scope"]),
    }


def create_packet(proposal: dict) -> dict:
    validate_proposal(proposal)
    return {
        "proposal": proposal,
        "stage_sha256": stage_snapshots(proposal),
        "packet_sha256": digest(proposal),
    }


def verify_packet(packet: dict) -> dict:
    exact_fields(packet, {"proposal", "stage_sha256", "packet_sha256"}, "packet")
    proposal = validate_proposal(packet["proposal"])
    need(isinstance(packet["packet_sha256"], str) and
         HEX64.fullmatch(packet["packet_sha256"]) is not None and
         packet["packet_sha256"] == digest(proposal),
         "審查封包內容已變更（packet_sha256 mismatch）")
    need(packet["stage_sha256"] == stage_snapshots(proposal),
         "stage_sha256 mismatch")
    return proposal


def save_json(path: Path, payload: dict) -> None:
    need(path.name not in ("state.json", "plan.md", "deploy.sql"),
         "不得覆寫 CREW 正式狀態、規格與 SQL")
    path.parent.mkdir(parents=True, exist_ok=True)
    need(not path.exists(), f"封包已存在，避免覆蓋既有核准版本：{path}")
    path.write_bytes(canonical_bytes(payload) + b"\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="CREW Review Once proposal packet (read-only planning)")
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("prepare")
    a.add_argument("--draft", required=True, type=Path)
    a.add_argument("--output", required=True, type=Path)
    b = sub.add_parser("verify")
    b.add_argument("--packet", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            packet = create_packet(parse_object(args.draft))
            save_json(args.output, packet)
            result = {"status": "awaiting_review", "packet": str(args.output),
                      "packet_sha256": packet["packet_sha256"]}
        else:
            proposal = verify_packet(parse_object(args.packet))
            result = {"status": "valid_unapproved_packet", "slug": proposal["slug"],
                      "packet_sha256": digest(proposal),
                      "max_duration_seconds": MAX_SECONDS}
    except (PacketError, TypeError, ValueError, OSError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
