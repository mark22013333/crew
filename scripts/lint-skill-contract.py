#!/usr/bin/env python3
"""Lint SKILL.md 內容契約（補 lint-skills.py 結構檢查之外的內容層）。

檢查項目：
  1. frontmatter description 含「當使用者提到」觸發詞段落
     （讓 skill 可被自然語言觸發）
  2. 內部 markdown 連結 [text](path) 指向的相對路徑檔案存在
     （排除 http/https/anchor 連結）

退出碼：
  0 = 通過
  1 = 有違規

例外清單：可在本檔頂部 EXEMPTIONS 設定。
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL_GLOB = "plugins/*/skills/*/SKILL.md"

# 觸發詞 frontmatter 應包含的關鍵字
TRIGGER_KEYWORD = "當使用者提到"

# markdown 連結 pattern：[text](path)，排除 http/https/mailto/anchor
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
SKIP_PREFIXES = ("http://", "https://", "mailto:", "#")

CREW_UPGRADE = REPO / "plugins" / "bug-workflow" / "skills" / "crew-upgrade" / "SKILL.md"
CREW_UPGRADE_REQUIRED = (
    "claude plugin marketplace update company-marketplace",
    "claude plugin update bug-workflow@company-marketplace",
    "claude plugin update feature-workflow@company-marketplace",
    "codex plugin marketplace upgrade crew",
    "codex plugin marketplace list",
    "codex plugin list",
    "claude plugin list",
)
CREW_UPGRADE_FORBIDDEN = (
    ".claude-company",
    "installed_plugins.json",
    "~/.claude/plugins/marketplaces/",
    "~/.codex/plugins/",
)

PLAN_VERIFY = REPO / "plugins" / "feature-workflow" / "skills" / "plan-verify" / "SKILL.md"
PLAN_VERIFY_WORD_REPORT = PLAN_VERIFY.parent / "phases" / "word-report.md"
PLAN_VERIFY_MEMORY = REPO / "plugins" / "feature-workflow" / "references" / "verify-memory.md"
PLAN_VERIFY_MCP = REPO / "plugins" / "feature-workflow" / "references" / "mcp-install.md"
PLAN_VERIFY_PRODUCT_MEMORY = REPO / "plugins" / "feature-workflow" / "products" / "smartrobot-memory.md"

PLAN_VERIFY_REQUIRED = (
    "CREW_PLUGIN_ROOT",
    "tool_probe(tool_kind=browser",
    ".crew/verify-memory.md",
    "../../references/verify-memory.md",
    "Human UAT 在 /plan-close 內取得",
    "local CDP",
)
PLAN_VERIFY_FORBIDDEN = (
    'python3 "${CLAUDE_PLUGIN_ROOT}/',
    "~/.claude/plugins/marketplaces/company-marketplace/plugins/feature-workflow",
    "{plugin_path}",
    "review 完成後由使用者做 UAT 決策",
    "Playwright MCP（必要",
    "claude mcp add playwright",
)


def parse_frontmatter(text: str) -> dict | None:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return None
    fm = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm


def check_trigger_keyword(fm: dict | None, rel: Path) -> str | None:
    if fm is None:
        return None  # 結構錯誤由 lint-skills.py 報
    desc = fm.get("description", "")
    if TRIGGER_KEYWORD not in desc:
        return f"{rel}: frontmatter description 缺「{TRIGGER_KEYWORD}」觸發詞段落"
    return None


def resolve_link(skill_path: Path, link: str) -> Path:
    """解析 SKILL.md 內的相對連結為絕對路徑。"""
    # 去除 anchor（#xxx）
    link = link.split("#", 1)[0]
    if not link:
        return None  # 純 anchor 跳過

    skill_dir = skill_path.parent  # plugins/{p}/skills/{name}/

    # 規則：以 references/ 開頭視為「相對 plugin root」
    # plugin root = skill_dir.parent.parent
    if link.startswith("references/"):
        plugin_root = skill_dir.parent.parent
        return (plugin_root / link).resolve()

    # 其他：相對 skill_dir
    return (skill_dir / link).resolve()


def check_internal_links(text: str, skill_path: Path) -> list[str]:
    errors = []
    for m in LINK_RE.finditer(text):
        link_target = m.group(2).strip()
        if link_target.startswith(SKIP_PREFIXES):
            continue
        if link_target.startswith("#"):
            continue
        # 跳過純錨點 / 變數 placeholder
        if "{" in link_target or "}" in link_target:
            continue
        resolved = resolve_link(skill_path, link_target)
        if resolved is None:
            continue
        if not resolved.exists():
            line = text[:m.start()].count("\n") + 1
            rel = skill_path.relative_to(REPO)
            errors.append(
                f"{rel}:{line} 內部連結 `{link_target}` 指向不存在的檔案 ({resolved.relative_to(REPO) if REPO in resolved.parents else resolved})"
            )
    return errors


def check_crew_upgrade_contract() -> list[str]:
    errors: list[str] = []
    if not CREW_UPGRADE.is_file():
        return [f"{CREW_UPGRADE.relative_to(REPO)} 不存在"]

    text = CREW_UPGRADE.read_text(encoding="utf-8")
    rel = CREW_UPGRADE.relative_to(REPO)

    for marker in CREW_UPGRADE_REQUIRED:
        if marker not in text:
            errors.append(f"{rel} 缺 portable update marker：{marker}")

    for marker in CREW_UPGRADE_FORBIDDEN:
        if marker in text:
            errors.append(f"{rel} 重新引入 Host 私有 update contract：{marker}")

    if "codex plugin update " in text:
        errors.append(f"{rel} 不得宣告不存在的 Codex plugin-specific update 子命令")

    return errors


def check_plan_verify_contract() -> list[str]:
    errors: list[str] = []

    required_files = (
        PLAN_VERIFY,
        PLAN_VERIFY_WORD_REPORT,
        PLAN_VERIFY_MEMORY,
        PLAN_VERIFY_MCP,
        PLAN_VERIFY_PRODUCT_MEMORY,
    )
    for path in required_files:
        if not path.is_file():
            errors.append(f"{path.relative_to(REPO)} 不存在")
    if errors:
        return errors

    skill = PLAN_VERIFY.read_text(encoding="utf-8")
    rel = PLAN_VERIFY.relative_to(REPO)
    for marker in PLAN_VERIFY_REQUIRED:
        if marker not in skill:
            errors.append(f"{rel} 缺 plan-verify convergence marker：{marker}")
    for marker in PLAN_VERIFY_FORBIDDEN:
        if marker in skill:
            errors.append(f"{rel} 重新引入 plan-verify Host/UAT drift：{marker}")

    report = PLAN_VERIFY_WORD_REPORT.read_text(encoding="utf-8")
    report_rel = PLAN_VERIFY_WORD_REPORT.relative_to(REPO)
    for marker in ("CREW_PLUGIN_ROOT", '"$CREW_PLUGIN_ROOT/references/verify-docx-generator.py"', '"$CREW_PLUGIN_ROOT/references/verify-excel-generator.js"'):
        if marker not in report:
            errors.append(f"{report_rel} 缺 portable plugin-root marker：{marker}")
    for marker in (
        "~/.claude/plugins/marketplaces/company-marketplace/plugins/feature-workflow",
        "{plugin_path}/references/",
    ):
        if marker in report:
            errors.append(f"{report_rel} 仍硬編碼 CREW 自身 Host path：{marker}")

    memory = PLAN_VERIFY_MEMORY.read_text(encoding="utf-8")
    memory_rel = PLAN_VERIFY_MEMORY.relative_to(REPO)
    for marker in (
        ".crew/verify-memory.md",
        ".claude/verify-memory.md",
        "新寫入永遠寫 `.crew/verify-memory.md`",
        "state.json.results.verify",
    ):
        if marker not in memory:
            errors.append(f"{memory_rel} 缺 verify-memory contract marker：{marker}")

    mcp = PLAN_VERIFY_MCP.read_text(encoding="utf-8")
    mcp_rel = PLAN_VERIFY_MCP.relative_to(REPO)
    for marker in ("tool_probe", "Codex / 其他 Host", "Local CDP fallback", "CREW_PLUGIN_ROOT"):
        if marker not in mcp:
            errors.append(f"{mcp_rel} 缺 browser adapter marker：{marker}")
    if "codex mcp add" in mcp:
        errors.append(f"{mcp_rel} 不得臆造固定 Codex MCP CLI")

    product_memory = PLAN_VERIFY_PRODUCT_MEMORY.read_text(encoding="utf-8")
    if ".crew/verify-memory.md" not in product_memory:
        errors.append(f"{PLAN_VERIFY_PRODUCT_MEMORY.relative_to(REPO)} 未指向 canonical Layer 2 memory")

    return errors


def main() -> int:
    errors: list[str] = []
    checked = 0

    for skill_md in sorted(REPO.glob(SKILL_GLOB)):
        checked += 1
        text = skill_md.read_text(encoding="utf-8")
        rel = skill_md.relative_to(REPO)
        fm = parse_frontmatter(text)

        # 1. 觸發詞
        err = check_trigger_keyword(fm, rel)
        if err:
            errors.append(err)

        # 2. 內部連結可達性
        errors.extend(check_internal_links(text, skill_md))

    errors.extend(check_crew_upgrade_contract())
    errors.extend(check_plan_verify_contract())

    for e in errors:
        print(f"❌ {e}")

    if errors:
        print(f"\n檢查 {checked} 個 SKILL.md，{len(errors)} 個契約違規")
        return 1

    print(f"✅ 檢查 {checked} 個 SKILL.md，所有契約通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
