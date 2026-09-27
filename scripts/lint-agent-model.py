#!/usr/bin/env python3
"""Lint Agent model 參數使用方式（模型分工政策的 CI 強制檢查）。

政策來源：plugins/*/references/model-policy.md（共用 reference，兩 plugin sha256 一致）
起點 gotcha（plan-common.md「共用 Gotchas」）：
  「prompt 中寫『使用 Opus 模型』只是自然語言指示，不保證生效。
   Capability request 必須帶結構化 `model: opus`；Host adapter 不得假裝已套用。」

七項檢查（對應 model-policy.md）：
  1. STRUCTURED  — 委派 capability／舊式 Agent 呼叫附近必須有結構化 model 標示
  2. AGENT_FM    — agents/*.md frontmatter 必須宣告 model，且已知 agent 的值需符合政策
                   （規格分析 agent 不得 opus；正式實作 agent 不得 sonnet）
  3. ROLE_POLICY — 各 skill 的角色模型對照（plan-spec 只准 sonnet、bug-investigate 預設
                   sonnet、bug-fix 需有 opus 實作者、plan-review --quick 需 sonnet…）
  4. NL_MODEL    — 禁止用自然語言「使用 Opus 模型」指定模型（除了明確在講「這樣不行」的句子）
  5. VAGUE       — 禁止「視情況使用模型」這類沒有具體參數的含糊措辭
  6. 掃描範圍含 references/ 與 agents/，不只 SKILL.md（自然語言模板也會被實際送出去）
  7. 優先檢查結構化宣告：`model: "opus"` / `{"model": "sonnet"}` / `model=opus` 才算數

無法靜態確認 Host runtime 是否真的套用了模型目標，
因此本 lint 的契約是：**指令文字必須以 capability request 明確帶結構化 model 目標**。
Claude adapter 可精準轉成 Agent/subagent model 參數；其他 Host 若無此能力，應依
host-capabilities.md 回報 routing degraded，而不是假裝成功。

用法：
  python3 scripts/lint-agent-model.py            # advisory：列出問題但 return 0
  python3 scripts/lint-agent-model.py --strict   # CI 用：有違規 return 1

退出碼：
  0 = 通過，或 advisory 模式
  1 = --strict 模式下有違規
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

SKILL_GLOB = "plugins/*/skills/*/SKILL.md"
REFERENCE_GLOB = "plugins/*/references/*.md"
AGENT_GLOB = "plugins/*/agents/*.md"

WINDOW = 250
VALID_MODELS = ("opus", "sonnet", "haiku")

# --- 1. 委派 capability／舊式 Agent 呼叫描述 -------------------------------
# 只把「真的在呼叫 delegate」視為 call site。單純在說明 parallel_delegate、
# 降級策略或 capability 名稱，不應被要求附近硬塞一個 model。
AGENT_CALL_RE = re.compile(
    r"(?:capability\s*:\s*(?:delegate_readonly|delegate_write)"
    r"|(?:使用|呼叫|執行|建立)[^\n]{0,120}(?:delegate_readonly|delegate_write)"
    r"|啟動\s*(?:唯讀\s*|實作者\s*)?subagent"
    r"|使用\s*Agent\s*tool"
    r"|Agent\s*tool\s*啟動"
    r"|具名\s*spawn"
    r"|Subagent\s*模式)",
    re.IGNORECASE,
)

# --- 7. 結構化 model 宣告 ---------------------------------------------------
# 同時認以下三種寫法（JSON 形式的 `"model": "opus"` 也要認）：
#   model: opus        model=opus        {"model": "opus"}
STRUCTURED_RE = re.compile(
    r"model[\"']?\s*[:=]\s*[\"'`]?(opus|sonnet|haiku)",
    re.IGNORECASE,
)

# --- 4. 自然語言指定模型（不算結構化）--------------------------------------
NL_MODEL_RE = re.compile(r"(?:可)?使用\s*(Opus|Sonnet|Haiku)\s*模型", re.IGNORECASE)
# 這些字出現在同一行 → 該行是在說明「這樣不行」（政策文件本身要引用反例），不算違規
PROHIBITION_WORDS = ("不可", "不得", "不要", "禁止", "只是", "不算", "不保證", "假裝", "不許")
NL_MODEL_ALLOW_WORDS = PROHIBITION_WORDS

# --- 5. 含糊措辭 -------------------------------------------------------------
VAGUE_RE = re.compile(
    r"(?:視情況|依需求|依情況|看情況)\s*(?:再)?(?:選用|選擇|使用|決定|指定)?\s*(?:適合的)?\s*(?:模型|model)"
    r"|(?:模型|model)\s*(?:視情況|依需求|看情況)",
    re.IGNORECASE,
)

# --- 2. agents/*.md frontmatter 政策 ---------------------------------------
# 規格分析／唯讀探索類 → 不得 opus；正式程式碼實作類 → 不得 sonnet
AGENT_MODEL_POLICY = {
    "feature-spec-analyst.md": ("sonnet", "規格分析（唯讀，產出 .spec/ 文件）不得使用 Opus"),
    "feature-code-generator.md": ("opus", "正式程式碼實作者不得使用 Sonnet"),
    "feature-db-designer.md": ("opus", "DB schema／索引／交易一致性屬複雜架構決策"),
    "feature-backend-designer.md": ("opus", "分層架構決策屬複雜架構決策"),
}

# --- 3. 各 skill 的角色模型政策 --------------------------------------------
# require: 檔案中必須出現的結構化模型；forbid: 全檔禁止出現的結構化模型
# section_rules: (段落標題關鍵字, require, forbid) — 段落 = 該標題到下一個同級或更高級標題
ROLE_POLICY = {
    "plan": {
        "require": ["sonnet", "opus"],
        "why": "spec pass 的唯讀規格分析目標 sonnet；db/arch 複雜設計目標 opus",
    },
    "plan-build": {
        "require": ["sonnet", "opus"],
        "why": "唯讀探索官 sonnet + 正式實作角色 opus，兩者都必須明確標示",
    },
    "plan-review": {
        "require": ["sonnet", "opus"],
        "section_rules": [
            ("快速審查", ["sonnet"], ["opus"], "--quick 為小型變更的單一唯讀審查，應為 Sonnet"),
        ],
        "why": "邏輯／品質 Reviewer sonnet + 效能 Reviewer opus",
    },
    "bug-investigate": {
        "require": ["sonnet"],
        "opus_only_in_sections": ["升級"],
        "why": "bug-investigate 預設 Sonnet；Opus 只允許出現在條件式升級段落",
    },
    "bug-fix": {
        "require": ["sonnet", "opus"],
        "why": "定位／驗證整理 sonnet + 正式修改實作者 opus",
    },
}

HEADING_RE = re.compile(r"^(#{2,6})\s+(.*)$", re.MULTILINE)

# --- 例外清單 ---------------------------------------------------------------
# 命中的「Agent 呼叫描述」其實不是派工指令（而是在講「絕不可以派」）時，標示模型反而誤導。
# 格式：(檔案路徑結尾, 該行必須包含的字串, 豁免理由)
# 維護提醒：比對錨點是「路徑結尾 + 該行含指定字串」。若該行文字被改寫，豁免會失效並回報
# 偽陽性（不會靜默放過），此時請同步更新或刪除對應條目，不要為了消警告而放寬規則。
EXEMPTIONS = [
    (
        "feature-workflow/references/boundaries.md",
        "啟動 Agent Teams 或連線 DB MCP",
        "plan-demo 的 🔴 NEVER 條目：本來就不會派工，標模型會誤導",
    ),
]


def is_exempt(path: Path, line_text: str) -> bool:
    p = rel(path)
    return any(
        p.endswith(suffix) and needle in line_text
        for suffix, needle, _reason in EXEMPTIONS
    )


def rel(path: Path) -> str:
    return str(path.relative_to(REPO))


def parse_frontmatter_model(text: str) -> str | None:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return None
    for line in m.group(1).split("\n"):
        if line.strip().startswith("model:"):
            return line.split(":", 1)[1].strip().strip("\"'").lower()
    return None


def mask_code_fences(text: str) -> str:
    """把 ``` 圍欄內的內容換成等長空白，避免範本裡的 `## 標題` 被當成真標題。

    （offset 保持不變，因此回傳值可直接用來算段落範圍。）
    """
    out_lines = []
    in_fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out_lines.append(" " * len(line))
            continue
        out_lines.append(" " * len(line) if in_fence else line)
    return "\n".join(out_lines)


def sections(text: str) -> list[tuple[str, int, int]]:
    """回傳 [(標題文字, 起始 offset, 結束 offset)]，段落結束於下一個同級或更高級標題。"""
    masked = mask_code_fences(text)
    heads = [(m.group(1), m.group(2), m.start()) for m in HEADING_RE.finditer(masked)]
    out = []
    for i, (hashes, title, start) in enumerate(heads):
        end = len(text)
        for hashes2, _title2, start2 in heads[i + 1:]:
            if len(hashes2) <= len(hashes):
                end = start2
                break
        out.append((title, start, end))
    return out


def line_of(text: str, offset: int) -> int:
    return text[:offset].count("\n") + 1


def check_structured_near_calls(text: str, path: Path) -> list[str]:
    """規則 1 + 7：Agent 呼叫描述附近必須有結構化 model 標示。"""
    findings = []
    for m in AGENT_CALL_RE.finditer(text):
        start = max(0, m.start() - WINDOW)
        end = min(len(text), m.end() + WINDOW)
        if STRUCTURED_RE.search(text[start:end]):
            continue
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_end = text.find("\n", m.end())
        line_text = text[line_start: line_end if line_end != -1 else len(text)]
        if is_exempt(path, line_text):
            continue
        findings.append(
            f"{rel(path)}:{line_of(text, m.start())} [STRUCTURED] 「{m.group(0)}」附近 "
            f"{WINDOW} 字元內未找到 `model: opus/sonnet/haiku` 結構化標示"
        )
    return findings


def check_nl_model(text: str, path: Path) -> list[str]:
    """規則 4：自然語言指定模型不算完成。"""
    findings = []
    for m in NL_MODEL_RE.finditer(text):
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_end = text.find("\n", m.end())
        line_text = text[line_start: line_end if line_end != -1 else len(text)]
        if any(w in line_text for w in NL_MODEL_ALLOW_WORDS):
            continue  # 這行是在說明「不可以這樣做」
        findings.append(
            f"{rel(path)}:{line_of(text, m.start())} [NL_MODEL] 「{m.group(0)}」是自然語言指定，"
            f"不保證生效；改為 capability 結構化標示（例：`delegate_write, role=xxx, model: opus`）"
        )
    return findings


def check_vague(text: str, path: Path) -> list[str]:
    """規則 5：禁止含糊的「視情況使用模型」（政策文件引用反例的行除外）。"""
    findings = []
    for m in VAGUE_RE.finditer(text):
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_end = text.find("\n", m.end())
        line_text = text[line_start: line_end if line_end != -1 else len(text)]
        if any(w in line_text for w in PROHIBITION_WORDS):
            continue  # 這行是在說明「不可以這樣寫」
        findings.append(
            f"{rel(path)}:{line_of(text, m.start())} [VAGUE] 「{m.group(0).strip()}」沒有具體參數；"
            f"寫明「什麼條件 → 哪個 model 值」"
        )
    return findings


def check_agent_frontmatter(path: Path, text: str) -> list[str]:
    """規則 2：agents/*.md 必須宣告 model，已知 agent 需符合政策。"""
    findings = []
    model = parse_frontmatter_model(text)
    if model is None:
        return [f"{rel(path)}:1 [AGENT_FM] frontmatter 缺少 `model` 欄位（不可只靠 prompt 描述模型）"]
    if model not in VALID_MODELS:
        findings.append(
            f"{rel(path)}:1 [AGENT_FM] frontmatter `model: {model}` 不是合法值 {VALID_MODELS}"
        )
    expected = AGENT_MODEL_POLICY.get(path.name)
    if expected and model != expected[0]:
        findings.append(
            f"{rel(path)}:1 [AGENT_FM] `model: {model}` 違反政策，應為 `{expected[0]}`（{expected[1]}）"
        )
    return findings


def check_role_policy(path: Path, text: str) -> list[str]:
    """規則 3：各 skill 的角色模型對照。"""
    skill_name = path.parent.name
    policy = ROLE_POLICY.get(skill_name)
    if not policy:
        return []

    findings = []
    found = {m.group(1).lower() for m in STRUCTURED_RE.finditer(text)}

    for need in policy.get("require", []):
        if need not in found:
            findings.append(
                f"{rel(path)}:1 [ROLE_POLICY] 缺少 `model: {need}` 的結構化標示"
                f"（{policy['why']}）"
            )

    for banned in policy.get("forbid", []):
        for m in STRUCTURED_RE.finditer(text):
            if m.group(1).lower() == banned:
                findings.append(
                    f"{rel(path)}:{line_of(text, m.start())} [ROLE_POLICY] 不得使用 "
                    f"`model: {banned}`（{policy['why']}）"
                )

    # opus 只准出現在指定段落（bug-investigate 的條件式升級）
    allow_keys = policy.get("opus_only_in_sections")
    if allow_keys:
        allowed_ranges = [
            (s, e) for title, s, e in sections(text)
            if any(k in title for k in allow_keys)
        ]
        for m in STRUCTURED_RE.finditer(text):
            if m.group(1).lower() != "opus":
                continue
            if any(s <= m.start() < e for s, e in allowed_ranges):
                continue
            findings.append(
                f"{rel(path)}:{line_of(text, m.start())} [ROLE_POLICY] `model: opus` 只能出現在"
                f"「{'／'.join(allow_keys)}」段落（{policy['why']}）"
            )

    # 段落層級規則（plan-review --quick）
    for key, require, forbid, why in policy.get("section_rules", []):
        matched = [(s, e) for title, s, e in sections(text) if key in title]
        if not matched:
            findings.append(f"{rel(path)}:1 [ROLE_POLICY] 找不到「{key}」段落，無法驗證（{why}）")
            continue
        for s, e in matched:
            body = text[s:e]
            sec_found = {m.group(1).lower() for m in STRUCTURED_RE.finditer(body)}
            for need in require:
                if need not in sec_found:
                    findings.append(
                        f"{rel(path)}:{line_of(text, s)} [ROLE_POLICY] 「{key}」段落缺少 "
                        f"`model: {need}`（{why}）"
                    )
            for banned in forbid:
                if banned in sec_found:
                    findings.append(
                        f"{rel(path)}:{line_of(text, s)} [ROLE_POLICY] 「{key}」段落不得使用 "
                        f"`model: {banned}`（{why}）"
                    )
    return findings


def main() -> int:
    strict = "--strict" in sys.argv
    findings: list[str] = []
    counts = {"skills": 0, "references": 0, "agents": 0, "calls": 0}

    for path in sorted(REPO.glob(SKILL_GLOB)):
        text = path.read_text(encoding="utf-8")
        counts["skills"] += 1
        counts["calls"] += len(AGENT_CALL_RE.findall(text))
        findings += check_structured_near_calls(text, path)
        findings += check_nl_model(text, path)
        findings += check_vague(text, path)
        findings += check_role_policy(path, text)

    for path in sorted(REPO.glob(REFERENCE_GLOB)):
        text = path.read_text(encoding="utf-8")
        counts["references"] += 1
        counts["calls"] += len(AGENT_CALL_RE.findall(text))
        # host-capabilities.md 是 adapter 契約本身，會列出 capability 名稱與
        # 降級範例；它不是實際派工指令，因此不套「附近必須有 model」規則。
        if path.name != "host-capabilities.md":
            findings += check_structured_near_calls(text, path)
            findings += check_nl_model(text, path)
        findings += check_vague(text, path)

    for path in sorted(REPO.glob(AGENT_GLOB)):
        text = path.read_text(encoding="utf-8")
        counts["agents"] += 1
        findings += check_agent_frontmatter(path, text)
        findings += check_vague(text, path)

    marker = "❌" if strict else "⚠️ "
    for f in findings:
        print(f"{marker} {f}")

    scope = (
        f"{counts['skills']} 個 SKILL.md、{counts['references']} 個 reference、"
        f"{counts['agents']} 個 agent 定義、{counts['calls']} 個委派／Agent 呼叫"
    )

    if findings:
        print(f"\n檢查 {scope}，{len(findings)} 個{'違規' if strict else '建議檢查項'}")
        if strict:
            print("政策見 plugins/*/references/model-policy.md")
            return 1
        print("（advisory 模式：不阻擋；CI 以 --strict 執行）")
        return 0

    print(f"✅ 檢查 {scope}，全部符合 model-policy.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
