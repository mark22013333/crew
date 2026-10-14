#!/usr/bin/env python3
"""Review Once signed approval proof and stage binding helpers.

The public key must be provisioned by a trusted Host outside the workspace.
A path supplied by an untrusted agent is NOT a security boundary.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

PACKET_MODULE = Path(__file__).with_name("review-once-packet.py")
_spec = importlib.util.spec_from_file_location("crew_review_once_packet", PACKET_MODULE)
assert _spec and _spec.loader
packet_contract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(packet_contract)


class GrantError(ValueError):
    pass


def require(test: bool, reason: str) -> None:
    if not test:
        raise GrantError(reason)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value: object, field: str) -> datetime:
    require(isinstance(value, str), f"{field} 必須是具時區的 ISO-8601")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GrantError(f"{field} 時間格式錯誤") from exc
    require(dt.tzinfo is not None and dt.utcoffset() is not None, f"{field} 不可缺時區")
    return dt.astimezone(timezone.utc)


def key_path(project: Path) -> Path:
    raw = os.environ.get("CREW_REVIEW_ONCE_TRUSTED_PUBLIC_KEY", "")
    require(bool(raw), "Host 未配置 CREW_REVIEW_ONCE_TRUSTED_PUBLIC_KEY，拒絕委派授權")
    key = Path(raw)
    require(key.is_absolute() and key.is_file(), "Host 信任公鑰必須是可讀取的絕對檔案路徑")
    require(not key.resolve().is_relative_to(project.resolve()),
            "信任公鑰不能放在 Agent 可修改的專案工作區")
    return key


def verify_event(project: Path, packet_file: Path, event_file: Path,
                 signature_file: Path, when: datetime | None = None) -> tuple[dict, dict, str]:
    current = when or now_utc()
    try:
        packet = packet_contract.parse_object(packet_file)
        proposal = packet_contract.verify_packet(packet)
        event = packet_contract.parse_object(event_file)
    except packet_contract.PacketError as exc:
        raise GrantError(str(exc)) from exc

    packet_contract.exact_fields(
        event,
        {"schema_version", "decision", "actor", "grant_id", "packet_sha256",
         "slug", "repository", "issued_at", "expires_at"},
        "approval_event",
    )
    require(event["schema_version"] == 1 and event["decision"] == "approve_review_once" and
            event["actor"] == "human", "必須是 Human 明確核准 Review Once 的事件")
    try:
        uuid.UUID(str(event["grant_id"]))
    except (ValueError, TypeError, AttributeError) as exc:
        raise GrantError("grant_id 必須是 UUID") from exc
    require(event["packet_sha256"] == packet["packet_sha256"], "授權事件與審查封包 Hash 不一致")
    require(event["slug"] == proposal["slug"] and
            event["repository"] == proposal["repository"],
            "授權事件的任務／Git 來源與審查封包不一致")
    issued = parse_time(event["issued_at"], "issued_at")
    expires = parse_time(event["expires_at"], "expires_at")
    require(issued <= current + timedelta(seconds=60), "授權簽發時間在未來")
    require(expires > current, "授權已到期")
    require(timedelta(seconds=0) < expires - issued <= timedelta(seconds=14400),
            "Review Once 授權不可超過四小時")

    key = key_path(project)
    try:
        signature = signature_file.read_bytes()
    except OSError as exc:
        raise GrantError(f"無法讀取授權簽章：{exc}") from exc
    require(bool(signature), "授權簽章不可為空")
    # OpenSSL verifies SHA-256 RSA / ECDSA signatures with a *public* key;
    # the private key belongs exclusively to a trusted external Host broker.
    with tempfile.TemporaryDirectory() as tmp:
        payload_file = Path(tmp) / "approval.json"
        payload_file.write_bytes(packet_contract.canonical_bytes(event))
        try:
            process = subprocess.run(
                ["openssl", "dgst", "-sha256", "-verify", str(key),
                 "-signature", str(signature_file), str(payload_file)],
                capture_output=True, text=True, timeout=8, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GrantError(f"授權簽章驗證工具不可用：{exc}") from exc
        require(process.returncode == 0, "授權事件簽章驗證失敗")
    return packet, event, packet_contract.digest(key.read_bytes().hex())


def sections(plan_text: str) -> dict[str, list[str]]:
    result = {}
    current = None
    for raw in plan_text.splitlines():
        if raw.startswith("## "):
            m = re.search(r"<!--\s*crew:(goal|ac|dec|risk|map)\b", raw)
            current = m.group(1) if m else None
            if current:
                result[current] = []
        elif current and raw.strip():
            result[current].append(raw.strip())
    return result


def check_stage(project: Path, slug: str, proposal: dict, stage: str) -> None:
    plan = project / ".spec" / slug / "plan.md"
    try:
        content = sections(plan.read_text(encoding="utf-8"))
    except OSError as exc:
        raise GrantError(f"無法讀取 plan.md：{exc}") from exc
    decisions = content.get("dec", [])
    risks = content.get("risk", [])
    if stage in ("spec", "all"):
        spec = proposal["spec"]
        require(content.get("goal", []) == spec["goal"], "Goal 已偏離核准規格")
        require(content.get("ac", []) == spec["ac"], "AC 已偏離核准規格")
        require([x for x in decisions if " [spec] " in x] == spec["decisions"],
                "Spec 決策已偏離核准規格")
        require(all(x in risks for x in spec["risks"]), "Spec 風險未完整套用")
    if stage in ("arch", "all"):
        arch = proposal["architecture"]
        require([x for x in decisions if " [arch] " in x] == arch["decisions"],
                "Architecture 決策已偏離核准規格")
        require(all(x in risks for x in arch["risks"]), "Architecture 風險未完整套用")
        db = proposal["db"]
        require([x for x in decisions if " [db] " in x] == db["decisions"],
                "DB 決策已偏離核准規格")
        sql = project / ".spec" / slug / "deploy.sql"
        if db["required"]:
            try:
                existing = sql.read_text(encoding="utf-8")
            except OSError as exc:
                raise GrantError(f"DB SQL 證據不可讀：{exc}") from exc
            require(existing == db["deploy_sql"], "deploy.sql 已偏離核准版本")
        else:
            require(not sql.exists(), "DB_REQUIRED=false 不得新增 deploy.sql")


def verify_dialogue(project: Path, grant: dict, when: datetime | None = None) -> dict:
    """同 session 對話核准（proof=dialogue）的防竄改檢查，回傳重新驗證過的 packet。

    只保證「套用的＝Human 在對話中審過的 packet」：重讀 packet_path、重算 hash、
    比對 grant 記錄的 packet_sha256，並確認未到期、期限不超過四小時。
    信任等級等同 Interactive 的 Human 核准，不是不可偽造的簽章。
    """
    current = when or now_utc()
    require(grant.get("by") == "human-dialogue", "dialogue Grant 的核准者紀錄不合法")
    try:
        uuid.UUID(str(grant.get("grant_id")))
    except (ValueError, TypeError, AttributeError) as exc:
        raise GrantError("grant_id 必須是 UUID") from exc
    raw_path = grant.get("packet_path")
    require(isinstance(raw_path, str) and bool(raw_path), "dialogue Grant 缺 packet_path")
    try:
        packet = packet_contract.parse_object(Path(raw_path))
        packet_contract.verify_packet(packet)
    except packet_contract.PacketError as exc:
        raise GrantError(str(exc)) from exc
    require(grant.get("packet_sha256") == packet["packet_sha256"],
            "審查封包已變更：重算 hash 與 Human 核准的 packet_sha256 不一致")
    issued = parse_time(grant.get("issued_at"), "issued_at")
    expires = parse_time(grant.get("expires_at"), "expires_at")
    require(issued <= current + timedelta(seconds=60), "授權簽發時間在未來")
    require(expires > current, "授權已到期")
    require(timedelta(seconds=0) < expires - issued <= timedelta(seconds=14400),
            "Review Once 授權不可超過四小時")
    return packet


def validate_active(project: Path, slug: str, state: dict,
                    stage: str = "all") -> tuple[dict, dict | None]:
    """回傳 (proposal, event)；dialogue Grant 沒有簽署事件，event 為 None。"""
    grant = state.get("autonomy") or {}
    require(grant.get("mode") == "review_once" and grant.get("status") == "active",
            "沒有可用的 Review Once Grant")
    proof = grant.get("proof", "signed")
    require(proof in ("signed", "dialogue"), f"未知的 Review Once 核准證明：{proof}")
    if proof == "dialogue":
        packet = verify_dialogue(project, grant)
        event = None
    else:
        packet_file = Path(grant["packet_path"])
        event_file = Path(grant["event_path"])
        sig_file = Path(grant["signature_path"])
        packet, event, key_sha = verify_event(project, packet_file, event_file, sig_file)
        require(grant.get("packet_sha256") == packet["packet_sha256"] and
                grant.get("grant_id") == event["grant_id"] and
                grant.get("trusted_key_sha256") == key_sha,
                "Review Once Grant 內容／信任根與原始授權不符")
        require(grant.get("issued_at") == event["issued_at"] and
                grant.get("expires_at") == event["expires_at"],
                "Grant 記錄的原始四小時期限與簽署事件不符")
    proposal = packet["proposal"]
    require(proposal["slug"] == slug and state.get("type") == "feature",
            "僅支援授權的 Feature slug")
    actual_branch = (state.get("git") or {}).get("branch")
    require(actual_branch == proposal["repository"]["branch"], "任務分支與核准分支不符")
    check_stage(project, slug, proposal, stage)
    return proposal, event
