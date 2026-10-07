#!/usr/bin/env python3
"""Lint：主要 README 必須描述 CREW 6 portable architecture，而不是舊 Host/provider contract。"""

import re
import sys
from pathlib import Path
from urllib.parse import unquote

REPO = Path(__file__).resolve().parent.parent

MAIN_READMES = (
    REPO / "README.md",
    REPO / "plugins" / "bug-workflow" / "README.md",
    REPO / "plugins" / "feature-workflow" / "README.md",
)

FORBIDDEN = {
    ".claude-company": re.compile(r"\.claude-company"),
    "direct feature config path": re.compile(r"~\/\.claude\/feature-workflow\/"),
    "direct bug config path": re.compile(r"~\/\.claude\/bug-workflow-config\.md"),
    "provider model contract": re.compile(r"\b(?:sonnet|opus|haiku)\b", re.IGNORECASE),
    "host-specific team contract": re.compile(r"Agent Teams?"),
    "old Codex phase wording": re.compile(r"Codex（CREW 6\.0 遷移 Phase 1）|Phase 1 的目標是讓 Codex"),
    "mandatory Claude team env": re.compile(r"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"),
}

REQUIRED = {
    "README.md": (
        "Host Capability Contract",
        "NONE",
        "FAST",
        "STANDARD",
        "DEEP",
        "AGENTS.md",
        "CLAUDE.md",
        "CREW_CONFIG_HOME",
        "XDG_CONFIG_HOME",
        "crew-config.py",
        "codex plugin add bug-workflow@crew",
        "codex plugin add feature-workflow@crew",
        "/crew-upgrade",
        "claude plugin marketplace update company-marketplace",
        "claude plugin update bug-workflow@company-marketplace",
        "claude plugin update feature-workflow@company-marketplace",
        "codex plugin marketplace upgrade crew",
        "feature-intake-refiner",
        "bug-intake-refiner",
        ".cache/intake.md",
        "notion_page_id",
        "Bug intake recovery preflight",
        "Persistence security preflight",
        "redacted",
        ".gitignore",
        "page-aware recovery journal",
        "五個標準 Bug sections",
        "CREW_PLUGIN_ROOT",
        "Intake Refinement Contract",
        "zero side effect",
        "2026-10-26",
    ),
    "plugins/bug-workflow/README.md": (
        "Host Capability Contract",
        "NONE",
        "FAST",
        "STANDARD",
        "DEEP",
        "bug/config",
        "bug/learning",
        "feature/project",
        "AGENTS.md",
        "CLAUDE.md",
        "crew-config.py",
        "Human UAT",
        "/crew-upgrade",
        "claude plugin marketplace update company-marketplace",
        "claude plugin update bug-workflow@company-marketplace",
        "codex plugin marketplace upgrade crew",
        "bug-intake-refiner",
        ".cache/intake.md",
        "notion_page_id",
        "Bug intake recovery preflight",
        "redacted",
        ".gitignore",
        "五個標準 Bug sections",
        "CREW_PLUGIN_ROOT",
        "references/intake-refinement.md",
        "zero side effect",
    ),
    "plugins/feature-workflow/README.md": (
        "Host Capability Contract",
        "NONE",
        "FAST",
        "STANDARD",
        "DEEP",
        "feature/config",
        "feature/project",
        "feature/stack",
        "AGENTS.md",
        "CLAUDE.md",
        "crew-config.py",
        "/crew-upgrade",
        "claude plugin marketplace update company-marketplace",
        "claude plugin update feature-workflow@company-marketplace",
        "codex plugin marketplace upgrade crew",
        ".crew/verify-memory.md",
        "Human UAT 在 `/plan-close` 內取得",
        "feature-intake-refiner",
        ".cache/intake.md",
        "notion_page_id",
        "redacted",
        ".gitignore",
        "pending task",
        "reconcile cache/page/state",
        "CREW_PLUGIN_ROOT",
        "references/intake-refinement.md",
        "2026-10-26",
    ),
}

ADR_INDEX = REPO / "docs" / "adr" / "README.md"
ADR_002 = REPO / "docs" / "adr" / "002-agent-teams-leader-delegate.md"
ADR_007 = REPO / "docs" / "adr" / "007-host-capability-portable-orchestration.md"
DOCX_README = REPO / "plugins" / "feature-workflow" / "references" / "dotnet" / "verify-docx-cli" / "README.md"

HISTORICAL_READMES = (
    REPO / ".spec" / "bug-optimization" / "README.md",
    REPO / ".spec" / "crew-optimization" / "README.md",
    REPO / ".spec" / "plan-verify-evolution" / "README.md",
    REPO / ".spec" / "verify-word-report" / "README.md",
)

MERMAID_REQUIRED = {
    "README.md": (
        "portable-architecture",
        "feature-lifecycle",
        "bug-lifecycle",
        "capability-fallback",
        "intake-refinement-flow",
    ),
    "plugins/bug-workflow/README.md": (
        "bug-lifecycle",
        "intake-refinement-flow",
    ),
    "plugins/feature-workflow/README.md": (
        "feature-lifecycle",
        "plan-build-orchestration",
        "plan-review-orchestration",
        "plan-verify-flow",
        "intake-refinement-flow",
    ),
}

LINKED_DOCS_REQUIRED = {
    REPO / "docs" / "prerequisites.md": (
        "Host Capability Contract",
        "Python 3",
        "NONE / FAST / STANDARD / DEEP",
        "sequential fallback",
        "AGENTS.md",
        "CLAUDE.md",
        "CREW_CONFIG_HOME",
    ),
    REPO / "docs" / "windows.md": (
        "Claude Code",
        "Codex",
        "CREW_CONFIG_HOME",
        "AGENTS.md",
        "CLAUDE.md",
    ),
    REPO / "docs" / "dbhub.md": (
        "tool_probe",
        "Claude Code adapter",
        "Codex / 其他 Host",
        "不得猜 schema",
    ),
}


def check_mermaid_contract(errors: list[str]) -> None:
    marker_pattern = re.compile(
        r"<!--\s*crew:diagram\s+([a-z0-9-]+)\s*-->\s*\n"
        r"```mermaid\s*\n([\s\S]*?)\n```",
        re.IGNORECASE,
    )

    for rel, required in MERMAID_REQUIRED.items():
        path = REPO / rel
        if not path.is_file():
            errors.append(f"{rel} 不存在，無法檢查 Mermaid contract")
            continue

        text = path.read_text(encoding="utf-8")
        blocks = {name: body for name, body in marker_pattern.findall(text)}

        raw_mermaid_count = len(re.findall(r"```mermaid\s*\n", text))
        if raw_mermaid_count != len(blocks):
            errors.append(
                f"{rel} 有未標記或重複 marker 的 Mermaid block："
                f"fences={raw_mermaid_count}, markers={len(blocks)}"
            )

        for name in required:
            body = blocks.get(name)
            if body is None:
                errors.append(f"{rel} 缺 Mermaid design contract：{name}")
                continue
            first = next((line.strip() for line in body.splitlines() if line.strip()), "")
            if not re.match(r"^(?:flowchart|graph)\s+(?:TB|TD|BT|RL|LR)\b", first):
                errors.append(
                    f"{rel} Mermaid {name} 必須以 flowchart/graph direction 開頭，目前：{first!r}"
                )

        extras = sorted(set(blocks) - set(required))
        if extras:
            errors.append(f"{rel} 有未登錄 Mermaid marker：{', '.join(extras)}")


def github_heading_anchors(text: str) -> set[str]:
    anchors: set[str] = set()
    seen: dict[str, int] = {}
    for line in text.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        title = match.group(1).strip().lower()
        slug = re.sub(r"[^\w\-\s]", "", title, flags=re.UNICODE)
        slug = re.sub(r"\s+", "-", slug).strip("-")
        index = seen.get(slug, 0)
        seen[slug] = index + 1
        anchors.add(slug if index == 0 else f"{slug}-{index}")
    return anchors


def check_readme_commands(errors: list[str]) -> None:
    skill_commands = {
        f"/{path.parent.name}"
        for path in REPO.glob("plugins/*/skills/*/SKILL.md")
    }
    allowed_host_commands = {"/init", "/crew-cockpit"}  # /crew-cockpit 是 Claude Code Mod 的 command，非 Skill
    known = skill_commands | allowed_host_commands

    inline_pattern = re.compile(r"`(/[a-z][a-z0-9-]*)(?:\s[^`]*)?`")
    line_pattern = re.compile(r"^\s*(/[a-z][a-z0-9-]*)(?:\s|$)")

    for readme in sorted(REPO.rglob("README.md")):
        text = readme.read_text(encoding="utf-8")
        commands = set(inline_pattern.findall(text))
        for line in text.splitlines():
            match = line_pattern.match(line)
            if match:
                commands.add(match.group(1))

        for command in sorted(commands):
            if command not in known:
                errors.append(
                    f"{readme.relative_to(REPO)} 引用不存在/非允許的 slash command：{command}"
                )


def check_internal_readme_links(errors: list[str]) -> None:
    pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for readme in sorted(REPO.rglob("README.md")):
        text = readme.read_text(encoding="utf-8")
        rel = readme.relative_to(REPO)
        for raw in pattern.findall(text):
            target = raw.strip()
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if target.startswith("~"):
                errors.append(f"{rel} 不得把 home path 寫成 Markdown link：{target}")
                continue

            path_part, sep, fragment = target.partition("#")
            target_path = readme if not path_part else (readme.parent / path_part).resolve()
            try:
                target_path.relative_to(REPO.resolve())
            except ValueError:
                errors.append(f"{rel} link 逃出 repo：{target}")
                continue

            if path_part and not target_path.exists():
                errors.append(f"{rel} broken internal link：{target}")
                continue

            if sep and fragment:
                if not target_path.is_file() or target_path.suffix.lower() != ".md":
                    errors.append(f"{rel} anchor target 不是 Markdown file：{target}")
                    continue
                anchors = github_heading_anchors(target_path.read_text(encoding="utf-8"))
                requested = unquote(fragment).lower()
                if requested not in anchors:
                    errors.append(f"{rel} broken Markdown anchor：{target}")


def main() -> int:
    errors: list[str] = []

    check_internal_readme_links(errors)
    check_readme_commands(errors)
    check_mermaid_contract(errors)

    for path in HISTORICAL_READMES:
        if not path.is_file():
            errors.append(f"historical README 不存在：{path.relative_to(REPO)}")
            continue
        if "歷史 v1 規劃 artifact" not in path.read_text(encoding="utf-8"):
            errors.append(f"{path.relative_to(REPO)} 缺歷史 artifact banner")

    for path, markers in LINKED_DOCS_REQUIRED.items():
        if not path.is_file():
            errors.append(f"README linked doc 不存在：{path.relative_to(REPO)}")
            continue
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                errors.append(f"{path.relative_to(REPO)} 缺 portable-doc marker：{marker}")

    for path in MAIN_READMES:
        rel = str(path.relative_to(REPO))
        if not path.is_file():
            errors.append(f"{rel} 不存在")
            continue
        text = path.read_text(encoding="utf-8")

        for label, pattern in FORBIDDEN.items():
            match = pattern.search(text)
            if match:
                line = text[:match.start()].count("\n") + 1
                errors.append(f"{rel}:{line} 仍含舊架構描述 [{label}]：{match.group(0)!r}")

        for marker in REQUIRED.get(rel, ()):
            if marker not in text:
                errors.append(f"{rel} 缺 CREW 6 README contract marker：{marker}")

    if not ADR_007.is_file():
        errors.append("缺 docs/adr/007-host-capability-portable-orchestration.md")
    else:
        text = ADR_007.read_text(encoding="utf-8")
        for marker in ("Host Capability Contract", "sequential", "NONE / FAST / STANDARD / DEEP", "ADR-002"):
            if marker not in text:
                errors.append(f"ADR-007 缺 marker：{marker}")

    if ADR_002.is_file():
        text = ADR_002.read_text(encoding="utf-8")
        if "已由 ADR-007 取代" not in text:
            errors.append("ADR-002 未標示已由 ADR-007 取代核心部分")

    if ADR_INDEX.is_file():
        text = ADR_INDEX.read_text(encoding="utf-8")
        if "ADR-007" not in text or "007-host-capability-portable-orchestration.md" not in text:
            errors.append("docs/adr/README.md 未列出 ADR-007")

    if DOCX_README.is_file():
        text = DOCX_README.read_text(encoding="utf-8")
        if "cd ~/.claude/plugins/marketplaces/company-marketplace" in text:
            errors.append("verify-docx-cli README 仍硬編碼 Claude marketplace install path")
        for marker in ("CREW_PLUGIN_ROOT", "MinimaxCorePath", "Host-specific 相容層"):
            if marker not in text:
                errors.append(f"verify-docx-cli README 缺 marker：{marker}")

    for error in errors:
        print(f"❌ {error}")

    if errors:
        print(f"\nREADME architecture lint：{len(errors)} 個問題")
        return 1

    print("✅ README architecture contract aligned with CREW 6 portable architecture")
    return 0


if __name__ == "__main__":
    sys.exit(main())
