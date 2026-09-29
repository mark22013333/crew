#!/usr/bin/env python3
"""檢查 CREW portable workflow 沒有重新引入 Host-specific orchestration 硬耦合。

Phase 2 的契約：
- active SKILL.md / references/*.md 的 workflow 語意使用 host-capabilities.md。
- Claude/Codex 的工具名稱只能留在 host-capabilities.md（adapter 契約）或非 portable
  的 agents/ 定義中。
- 專案指令檔名與舊設定路徑目前仍在漸進遷移，所以列 advisory，不在 Phase 2A 阻擋。

用法：
  python3 scripts/lint-host-portability.py
  python3 scripts/lint-host-portability.py --strict
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STRICT = "--strict" in sys.argv

SCAN_GLOBS = (
    "plugins/*/skills/*/SKILL.md",
    "plugins/*/references/*.md",
)

# 這些代表 workflow 直接依賴某個 Host 的 orchestration / CLI。
HARD_PATTERNS = {
    "AGENT_TOOL": re.compile(r"\bAgent\s+tool\b", re.I),
    "AGENT_TEAMS": re.compile(r"\bAgent\s+Teams?\b", re.I),
    "TEAM_LIFECYCLE": re.compile(r"\bTeam(?:Create|Delete)\b", re.I),
    "CLAUDE_TEAM_ENV": re.compile(r"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"),
    "CLAUDE_MCP_LIST": re.compile(r"\bclaude\s+mcp\s+list\b", re.I),
}

# Phase 2B/後續才全面收斂；目前只做可見性。
SOFT_PATTERNS = {
    "CLAUDE_MD": re.compile(r"CLAUDE\.md"),
    "CLAUDE_CONFIG_PATH": re.compile(r"~/\.claude(?:-company)?/"),
    "CLAUDE_PLUGIN_CLI": re.compile(r"\bclaude\s+plugin\b", re.I),
}

# adapter / portability contract 本來就必須列出 Host-specific 名稱或 legacy fallback；consumer 才是 lint 對象。
EXEMPT_REFERENCE_NAMES = {"host-capabilities.md", "config-contract.md"}


def rel(path: Path) -> str:
    return str(path.relative_to(REPO))


def scan_line_patterns(path: Path, line: str, lineno: int, patterns: dict[str, re.Pattern]) -> list[str]:
    out: list[str] = []
    for code, pattern in patterns.items():
        if pattern.search(line):
            out.append(f"{rel(path)}:{lineno} [{code}] {line.strip()}")
    return out


def main() -> int:
    hard: list[str] = []
    soft: list[str] = []
    scanned: set[Path] = set()

    for glob in SCAN_GLOBS:
        for path in sorted(REPO.glob(glob)):
            if path in scanned:
                continue
            scanned.add(path)
            if path.name in EXEMPT_REFERENCE_NAMES:
                continue

            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), 1):
                hard += scan_line_patterns(path, line, lineno, HARD_PATTERNS)
                soft += scan_line_patterns(path, line, lineno, SOFT_PATTERNS)

    for item in hard:
        print(f"❌ {item}")
    for item in soft:
        print(f"⚠️  {item}")

    print(
        f"\nHost portability：掃描 {len(scanned)} 個 active Skill/reference；"
        f"hard={len(hard)}、advisory={len(soft)}"
    )

    if hard:
        print(
            "修法：把 workflow 語意改寫成 references/host-capabilities.md 的 "
            "delegate_readonly / delegate_write / parallel_delegate / tool_probe。"
        )
        return 1 if STRICT else 0

    print("✅ 沒有 Host-specific orchestration 硬耦合")
    return 0


if __name__ == "__main__":
    sys.exit(main())
