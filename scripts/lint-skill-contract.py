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
PLAN_VERIFY_ROUTE = PLAN_VERIFY.parent / "phases" / "route-verification.md"
PLAN_VERIFY_PRECONDITIONS = PLAN_VERIFY.parent / "phases" / "preconditions.md"
PLAN_VERIFY_E2E_RUNNER = PLAN_VERIFY.parent / "phases" / "e2e-runner.md"
PLAN_VERIFY_E2E_AUTHORING = PLAN_VERIFY.parent / "phases" / "e2e-authoring.md"
PLAN_VERIFY_E2E_PROMOTION = PLAN_VERIFY.parent / "phases" / "e2e-promotion.md"
PLAN_VERIFY_FROM_E2E = PLAN_VERIFY.parent / "phases" / "from-e2e.md"
PLAN_VERIFY_IR = REPO / "plugins" / "feature-workflow" / "references" / "verification-ir.md"
PLAN_VERIFY_E2E_CONTRACT = REPO / "plugins" / "feature-workflow" / "references" / "e2e-contract.md"
PLAN_VERIFY_E2E_CI_POLICY = REPO / "plugins" / "feature-workflow" / "references" / "e2e-ci-policy.md"
PLAN_VERIFY_E2E_RESULT = REPO / "plugins" / "feature-workflow" / "references" / "e2e-result-schema.md"
PLAN_VERIFY_E2E_REPORTER = REPO / "plugins" / "feature-workflow" / "references" / "playwright" / "crew-reporter.js"
PLAN_VERIFY_E2E_RESULTS_TOOL = REPO / "plugins" / "feature-workflow" / "scripts" / "crew-e2e-results.py"
PLAN_VERIFY_E2E_LINTER = REPO / "plugins" / "feature-workflow" / "scripts" / "lint-playwright-e2e.py"
PLAN_VERIFY_GENERIC_ADAPTER = REPO / "plugins" / "feature-workflow" / "adapters" / "generic-playwright.md"
PLAN_COMMON = REPO / "plugins" / "feature-workflow" / "references" / "plan-common.md"

PLAN_VERIFY_REQUIRED = (
    "CREW_PLUGIN_ROOT",
    "tool_probe(tool_kind=browser",
    ".crew/verify-memory.md",
    "../../references/verify-memory.md",
    "Human UAT 在 /plan-close 內取得",
    "local CDP",
    "phases/route-verification.md",
    "phases/preconditions.md",
    "BLOCKED",
    "../../references/verification-ir.md",
    "../../references/e2e-contract.md",
    "--e2e-draft",
    "--e2e-promote",
    "--from-e2e",
    "phases/e2e-runner.md",
    "phases/e2e-authoring.md",
    "phases/e2e-promotion.md",
    "phases/from-e2e.md",
)
PLAN_VERIFY_FORBIDDEN = (
    'python3 "${CLAUDE_PLUGIN_ROOT}/',
    "~/.claude/plugins/marketplaces/company-marketplace/plugins/feature-workflow",
    "{plugin_path}",
    "review 完成後由使用者做 UAT 決策",
    "Playwright MCP（必要",
    "claude mcp add playwright",
)

PLAN_START = REPO / "plugins" / "feature-workflow" / "skills" / "plan-start" / "SKILL.md"
PLAN_SYNC = REPO / "plugins" / "feature-workflow" / "skills" / "plan-sync" / "SKILL.md"
PLAN_CLOSE = REPO / "plugins" / "feature-workflow" / "skills" / "plan-close" / "SKILL.md"
PLAN_SETUP = REPO / "plugins" / "feature-workflow" / "skills" / "plan-setup" / "SKILL.md"
INTAKE_AGENT = REPO / "plugins" / "feature-workflow" / "agents" / "feature-intake-refiner.md"
INTAKE_CONTRACT = REPO / "plugins" / "feature-workflow" / "references" / "intake-refinement.md"
NOTION_TEMPLATE = REPO / "plugins" / "feature-workflow" / "references" / "notion-page-template.md"

BUG_START = REPO / "plugins" / "bug-workflow" / "skills" / "bug-start" / "SKILL.md"
BUG_INVESTIGATE = REPO / "plugins" / "bug-workflow" / "skills" / "bug-investigate" / "SKILL.md"
BUG_UPDATE = REPO / "plugins" / "bug-workflow" / "skills" / "bug-update" / "SKILL.md"
BUG_CLOSE = REPO / "plugins" / "bug-workflow" / "skills" / "bug-close" / "SKILL.md"
BUG_SETUP = REPO / "plugins" / "bug-workflow" / "skills" / "bug-setup" / "SKILL.md"
BUG_INTAKE_AGENT = REPO / "plugins" / "bug-workflow" / "agents" / "bug-intake-refiner.md"
BUG_INTAKE_CONTRACT = REPO / "plugins" / "bug-workflow" / "references" / "intake-refinement.md"


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
        PLAN_VERIFY_ROUTE,
        PLAN_VERIFY_PRECONDITIONS,
        PLAN_VERIFY_E2E_RUNNER,
        PLAN_VERIFY_E2E_AUTHORING,
        PLAN_VERIFY_E2E_PROMOTION,
        PLAN_VERIFY_FROM_E2E,
        PLAN_VERIFY_IR,
        PLAN_VERIFY_E2E_CONTRACT,
        PLAN_VERIFY_E2E_CI_POLICY,
        PLAN_VERIFY_E2E_RESULT,
        PLAN_VERIFY_E2E_REPORTER,
        PLAN_VERIFY_E2E_RESULTS_TOOL,
        PLAN_VERIFY_E2E_LINTER,
        PLAN_VERIFY_GENERIC_ADAPTER,
        PLAN_COMMON,
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

    route = PLAN_VERIFY_ROUTE.read_text(encoding="utf-8")
    for marker in ("browser", "backend-test", "database", "證明力優先", "一條 AC 一個主要 verifier"):
        if marker not in route:
            errors.append(f"{PLAN_VERIFY_ROUTE.relative_to(REPO)} 缺 verification router marker：{marker}")

    preconditions = PLAN_VERIFY_PRECONDITIONS.read_text(encoding="utf-8")
    for marker in ("BLOCKED", "前置條件失敗不等於產品功能失敗", "不計入 FAIL"):
        if marker not in preconditions:
            errors.append(f"{PLAN_VERIFY_PRECONDITIONS.relative_to(REPO)} 缺 precondition marker：{marker}")

    e2e_runner = PLAN_VERIFY_E2E_RUNNER.read_text(encoding="utf-8")
    for marker in ("{slug}#AC-n", "legacy `verify-map.json`", "BLOCKED", "crew-results.json"):
        if marker not in e2e_runner:
            errors.append(f"{PLAN_VERIFY_E2E_RUNNER.relative_to(REPO)} 缺 E2E runner marker：{marker}")

    e2e_authoring = PLAN_VERIFY_E2E_AUTHORING.read_text(encoding="utf-8")
    for marker in ("maturity = draft", "Verification IR", "test.step", "ci_eligible=false"):
        if marker not in e2e_authoring:
            errors.append(f"{PLAN_VERIFY_E2E_AUTHORING.relative_to(REPO)} 缺 E2E authoring marker：{marker}")

    e2e_promotion = PLAN_VERIFY_E2E_PROMOTION.read_text(encoding="utf-8")
    for marker in ("ci-ready", "retries=0", "repeat-each=3", "FLAKY"):
        if marker not in e2e_promotion:
            errors.append(f"{PLAN_VERIFY_E2E_PROMOTION.relative_to(REPO)} 缺 E2E promotion marker：{marker}")

    from_e2e = PLAN_VERIFY_FROM_E2E.read_text(encoding="utf-8")
    for marker in ("--from-e2e", "crew-results.json", "blocked", "crew-state.py"):
        if marker not in from_e2e:
            errors.append(f"{PLAN_VERIFY_FROM_E2E.relative_to(REPO)} 缺 from-e2e marker：{marker}")

    ir = PLAN_VERIFY_IR.read_text(encoding="utf-8")
    for marker in ("schema_version", ".cache/verification-ir.json", "{slug}#AC-{n}", "forbid_request"):
        if marker not in ir:
            errors.append(f"{PLAN_VERIFY_IR.relative_to(REPO)} 缺 Verification IR marker：{marker}")

    e2e = PLAN_VERIFY_E2E_CONTRACT.read_text(encoding="utf-8")
    for marker in (".crew/adapters/{e2e_adapter}.md", "generic-playwright", "workspace", "不得要求某位工程師的絕對家目錄"):
        if marker not in e2e:
            errors.append(f"{PLAN_VERIFY_E2E_CONTRACT.relative_to(REPO)} 缺 portable E2E marker：{marker}")

    ci_policy = PLAN_VERIFY_E2E_CI_POLICY.read_text(encoding="utf-8")
    for marker in ("draft", "ci-ready", "retries=0", "cleanup", "ci_eligible=false"):
        if marker not in ci_policy:
            errors.append(f"{PLAN_VERIFY_E2E_CI_POLICY.relative_to(REPO)} 缺 CI promotion marker：{marker}")

    result_schema = PLAN_VERIFY_E2E_RESULT.read_text(encoding="utf-8")
    for marker in ("crew-results.json", "flaky", "blocked", "CI 不直接寫"):
        if marker not in result_schema:
            errors.append(f"{PLAN_VERIFY_E2E_RESULT.relative_to(REPO)} 缺 E2E result marker：{marker}")

    reporter = PLAN_VERIFY_E2E_REPORTER.read_text(encoding="utf-8")
    for marker in ("crew-ac", "crew-blocked", "schema_version", "flaky", "module.exports = CrewReporter"):
        if marker not in reporter:
            errors.append(f"{PLAN_VERIFY_E2E_REPORTER.relative_to(REPO)} 缺 Playwright reporter marker：{marker}")

    results_tool = PLAN_VERIFY_E2E_RESULTS_TOOL.read_text(encoding="utf-8")
    for marker in ("STATUS_PRIORITY", "blocked 必須有 reason", "expected_git_sha", "never writes state.json"):
        if marker not in results_tool:
            errors.append(f"{PLAN_VERIFY_E2E_RESULTS_TOOL.relative_to(REPO)} 缺 E2E result tool marker：{marker}")

    e2e_linter = PLAN_VERIFY_E2E_LINTER.read_text(encoding="utf-8")
    for marker in ("TEST_ONLY", "UNRESOLVED_MARKER", "MISSING_AC", "MISSING_ASSERTION", "--strict-review"):
        if marker not in e2e_linter:
            errors.append(f"{PLAN_VERIFY_E2E_LINTER.relative_to(REPO)} 缺 E2E promotion linter marker：{marker}")

    plan_common = PLAN_COMMON.read_text(encoding="utf-8")
    for marker in (".crew/products/{product_id}.md", "e2e_adapter", "e2e.workspace", "舊欄位 `e2e_repo` / `e2e_profile`"):
        if marker not in plan_common:
            errors.append(f"{PLAN_COMMON.relative_to(REPO)} 缺 project-local E2E/product resolution marker：{marker}")

    return errors


def check_plan_start_intake_contract() -> list[str]:
    errors: list[str] = []

    required_files = (
        PLAN_START,
        PLAN_SYNC,
        PLAN_CLOSE,
        PLAN_SETUP,
        INTAKE_AGENT,
        INTAKE_CONTRACT,
        NOTION_TEMPLATE,
    )
    for path in required_files:
        if not path.is_file():
            errors.append(f"{path.relative_to(REPO)} 不存在")
    if errors:
        return errors

    start = PLAN_START.read_text(encoding="utf-8")
    start_rel = PLAN_START.relative_to(REPO)
    start_required = (
        "role=`feature-intake-refiner`",
        "task=`requirement_analysis`",
        "profile=`STANDARD`",
        "ORIGINAL_REQUEST",
        "REFINED_REQUEST",
        "CONFIRMED_TITLE",
        "Human intake confirmation",
        "零 side effect",
        ".cache/intake.md",
        "notion_page_id",
        "Gitignore safeguard + intake recovery cache",
        "第一個 task artifact",
        "Persistence security preflight",
        "REUSE_PENDING_TASK",
        "../../references/intake-refinement.md",
    )
    for marker in start_required:
        if marker not in start:
            errors.append(f"{start_rel} 缺 intake marker：{marker}")

    confirm_at = start.find("#### 1-4. Human intake confirmation")
    notion_at = start.find("### 6. 建立 Notion 條目")
    spec_at = start.find("### 7. 建立 .spec/{slug}/")
    branch_at = start.find("### 8. 建立 Git branch")
    if min(confirm_at, notion_at, spec_at, branch_at) < 0:
        errors.append(f"{start_rel} 缺 intake/side-effect 章節，無法驗證順序")
    elif not (confirm_at < notion_at < spec_at < branch_at):
        errors.append(f"{start_rel} Human confirmation 必須早於 Notion/.spec/Git side effects")

    agent = INTAKE_AGENT.read_text(encoding="utf-8")
    agent_rel = INTAKE_AGENT.relative_to(REPO)
    for marker in (
        "name: feature-intake-refiner",
        "model: sonnet",
        "不產正式 spec",
        "全程唯讀",
        "blocking_questions",
    ):
        if marker not in agent:
            errors.append(f"{agent_rel} 缺 intake agent marker：{marker}")

    contract = INTAKE_CONTRACT.read_text(encoding="utf-8")
    contract_rel = INTAKE_CONTRACT.relative_to(REPO)
    for marker in (
        "raw user request",
        "Human confirms intent",
        "ORIGINAL_REQUEST",
        "REFINED_REQUEST",
        ".cache/intake.md",
        "不得猜原文",
        "Plan pending-task recovery",
        "notion_page_id",
        "Persistence security preflight",
        ".gitignore",
        "Notion unavailable / pending sync 時一律保留 cache",
        "## 🔍 調查過程",
        "## 🧠 根因分析",
        "## ✅ 修復方案",
        "## 🧪 驗證",
        "## 📝 經驗教訓",
    ):
        if marker not in contract:
            errors.append(f"{contract_rel} 缺 intake contract marker：{marker}")

    template = NOTION_TEMPLATE.read_text(encoding="utf-8")
    for marker in ("### 原始需求", "### 確認後任務描述", "### 目標與範圍", "### 驗收條件"):
        if marker not in template:
            errors.append(f"{NOTION_TEMPLATE.relative_to(REPO)} 缺 intake/template marker：{marker}")

    sync = PLAN_SYNC.read_text(encoding="utf-8")
    sync_rel = PLAN_SYNC.relative_to(REPO)
    for marker in (
        "Intake prefix immutable",
        "### 原始需求",
        "### 確認後任務描述",
        "### 原始通報",
        "### 確認後問題描述",
        ".cache/intake.md",
        "不得猜原文",
        "cache page ID",
        "state 的 `notion.page_id` 與本輪 page ID 一致",
    ):
        if marker not in sync:
            errors.append(f"{sync_rel} 缺 intake preservation marker：{marker}")

    for portable_skill in (PLAN_START, PLAN_SYNC, PLAN_CLOSE):
        portable_text = portable_skill.read_text(encoding="utf-8")
        if '${CLAUDE_PLUGIN_ROOT}/scripts/' in portable_text:
            errors.append(
                f"{portable_skill.relative_to(REPO)} intake lifecycle 不得直接使用 "
                "${CLAUDE_PLUGIN_ROOT}/scripts/；請先解析 CREW_PLUGIN_ROOT"
            )

    close = PLAN_CLOSE.read_text(encoding="utf-8")
    close_rel = PLAN_CLOSE.relative_to(REPO)
    for marker in (
        "intake prefix 永久保留",
        "### 原始需求",
        "### 確認後任務描述",
        ".cache/intake.md",
        "不得猜原始 prompt",
        "cache 的 `notion_page_id`",
        "BLOCK",
    ):
        if marker not in close:
            errors.append(f"{close_rel} 缺 intake close marker：{marker}")

    setup = PLAN_SETUP.read_text(encoding="utf-8")
    for marker in ("Agent availability", "feature-intake-refiner", "不是 Slash Skills", "inline / sequential fallback"):
        if marker not in setup:
            errors.append(f"{PLAN_SETUP.relative_to(REPO)} 缺 Host-dependent Agent marker：{marker}")

    return errors


def check_bug_start_intake_contract() -> list[str]:
    errors: list[str] = []
    required_files = (
        BUG_START,
        BUG_INVESTIGATE,
        BUG_UPDATE,
        BUG_CLOSE,
        BUG_SETUP,
        BUG_INTAKE_AGENT,
        BUG_INTAKE_CONTRACT,
    )
    for path in required_files:
        if not path.is_file():
            errors.append(f"{path.relative_to(REPO)} 不存在")
    if errors:
        return errors

    start = BUG_START.read_text(encoding="utf-8")
    start_rel = BUG_START.relative_to(REPO)
    for marker in (
        "role=`bug-intake-refiner`",
        "task=`requirement_analysis`",
        "profile=`STANDARD`",
        "ORIGINAL_REQUEST",
        "REFINED_REQUEST",
        "CONFIRMED_TITLE",
        "Human intake confirmation",
        "zero side effect",
        ".cache/intake.md",
        "notion_page_id",
        "Gitignore safeguard + intake recovery cache",
        "第一個 task artifact",
        "Persistence security preflight",
        "Step 6 completion gate",
        "../../references/intake-refinement.md",
        "### 原始通報",
        "### 確認後問題描述",
    ):
        if marker not in start:
            errors.append(f"{start_rel} 缺 Bug intake marker：{marker}")

    confirm_at = start.find("#### 1-4. Human intake confirmation")
    notion_at = start.find("### 5. 建立／沿用 Notion 條目")
    state_at = start.find("### 5.5 建立最小 Bug Runtime State")
    if min(confirm_at, notion_at, state_at) < 0:
        errors.append(f"{start_rel} 缺 Bug intake/side-effect 章節，無法驗證順序")
    elif not (confirm_at < notion_at < state_at):
        errors.append(f"{start_rel} Human confirmation 必須早於 Notion/state side effects")

    agent = BUG_INTAKE_AGENT.read_text(encoding="utf-8")
    for marker in (
        "name: bug-intake-refiner",
        "model: sonnet",
        "不做根因分析",
        "全程唯讀",
        "blocking_questions",
    ):
        if marker not in agent:
            errors.append(f"{BUG_INTAKE_AGENT.relative_to(REPO)} 缺 Bug intake agent marker：{marker}")

    contract = BUG_INTAKE_CONTRACT.read_text(encoding="utf-8")
    if "若 intake headings 已完整存在 → 刪 cache" in contract:
        errors.append(f"{BUG_INTAKE_CONTRACT.relative_to(REPO)} 不得只驗證 intake headings 就刪 recovery cache；必須同時驗證五個標準 Bug sections")
    for marker in (
        "Feature / Plan:",
        "Bug:",
        "feature-intake-refiner",
        "bug-intake-refiner",
        "ORIGINAL_REQUEST",
        "REFINED_REQUEST",
        ".cache/intake.md",
        "不得猜原文",
        "zero side effect",
        "Recovery cache：第一個 post-confirmation task artifact",
        "Persistence security preflight",
        ".gitignore",
        "Bug intake recovery preflight",
        "notion_page_id",
    ):
        if marker not in contract:
            errors.append(f"{BUG_INTAKE_CONTRACT.relative_to(REPO)} 缺 shared intake contract marker：{marker}")

    investigate = BUG_INVESTIGATE.read_text(encoding="utf-8")
    for marker in (
        "Bug Intake Refiner + Human confirmation",
        "既有 Bug 不重新跑 intake refinement",
        "Bug intake recovery preflight",
        "五個標準 Bug sections",
    ):
        if marker not in investigate:
            errors.append(f"{BUG_INVESTIGATE.relative_to(REPO)} 缺 Bug intake handoff/recovery marker：{marker}")

    update = BUG_UPDATE.read_text(encoding="utf-8")
    for marker in ("Bug intake recovery preflight", "state.notion.page_id == 目前 page id", "CREW_PLUGIN_ROOT", "五個標準 Bug sections"):
        if marker not in update:
            errors.append(f"{BUG_UPDATE.relative_to(REPO)} 缺 Bug intake recovery marker：{marker}")

    close = BUG_CLOSE.read_text(encoding="utf-8")
    for marker in (
        "綁定 Bug Runtime State + intake recovery",
        "state.notion.page_id == 目前 Bug page id",
        "Bug intake recovery preflight",
        "CREW_PLUGIN_ROOT",
        "五個標準 Bug sections",
    ):
        if marker not in close:
            errors.append(f"{BUG_CLOSE.relative_to(REPO)} 缺 Bug close state/recovery marker：{marker}")
    if '${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py' in close:
        errors.append(f"{BUG_CLOSE.relative_to(REPO)} 不得直接用 CLAUDE_PLUGIN_ROOT 呼叫 crew-state.py")

    setup = BUG_SETUP.read_text(encoding="utf-8")
    for marker in ("Agent availability", "bug-intake-refiner", "不是 Slash Skill", "inline"):
        if marker not in setup:
            errors.append(f"{BUG_SETUP.relative_to(REPO)} 缺 Bug Agent availability marker：{marker}")

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
    errors.extend(check_plan_start_intake_contract())
    errors.extend(check_bug_start_intake_contract())

    for e in errors:
        print(f"❌ {e}")

    if errors:
        print(f"\n檢查 {checked} 個 SKILL.md，{len(errors)} 個契約違規")
        return 1

    print(f"✅ 檢查 {checked} 個 SKILL.md，所有契約通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
