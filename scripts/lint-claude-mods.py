#!/usr/bin/env python3
"""CREW Cockpit Mod guard（規格書 §18 / §23）：確保 Claude Code Mod 永遠唯讀、最小能力面。

既有 lint 只掃 md，不掃 .ts Mod，所以由本腳本守門。兩層：

  主層（需要 claude CLI）：
    跑 `claude plugin validate --json <plugin dir>`，解析 hooks / calls / state 清單，
    與 `tests/mod-capabilities.baseline.txt` 比對。
      - validate 出現 baseline 沒有的項目 → FAIL（新能力）
      - baseline 有但 validate 沒有       → 只提示（能力縮小不算錯）
      - validate 回報 errors              → FAIL
    validate 依「實際呼叫」回報，所以抓得到 `const f = $.fs; f.write(...)` 這類別名。
    claude CLI 不存在時印「SKIP（無 claude CLI）」，只跑輔層，並明確標示主層未執行。

  輔層（純 Python、不需 claude CLI）— 規格 §23 五條：
    R1 hooks.json 的 modules 路徑存在
    R2 Mod source 的 `$.<noun>` 採 allowlist：noun 只准 session/fs/ui/state/store/command/prompt/clock，
       fs 只准 read/list/exists/stat、prompt 只准 fill/read；另保留接收者不限的 denylist
       （fs.write、model.*、tool.*、process.*、http.*、mcp.*、prompt.submit/edit …，規格 §18 全部禁止能力）
    R3 Mod source 不含 $.fs / $.process / $.model / $.tool 的整體賦值或解構，也不含對 `$` 的
       轉型（`$ as`、`<T>$`）、computed 存取（`$[`、`($)[`）、Reflect／Object 反射（別名繞過的前置動作）
    R4 既有 SessionStart hook 仍在 hooks.json
    R5 manifest 沒有重複宣告標準 hooks/hooks.json
    R6 同一檔內，接收 `$`（或 EngineInterface）的函式，其名稱不可被宣告第二次（不論作用域）——
       Claude Code 2.1.289 會以「declared more than once in this file」拒載整個 Mod（2.1.291 容許，故本機難測到）

  輔層是字串比對，抓不到「$ 先傳進別的函式、在裡面用別名」的寫法——那是主層的工作。
  注意：R2/R3 不剝註解，註解裡寫出禁止字串也會被擋（刻意保守；註解請改用中文描述）。

baseline 格式（純文字、一行一項、排序、`#` 開頭為註解）：
    <module> hook <spec>          例：./register.tsx hook command.run{command=tool-calls}
    <module> call <$.x.y>         例：./register.tsx call $.ui.open
    <module> state-write <key>    例：./register.tsx state-write tool-calls.calls
    <module> state-read <key>
  由 `--write-baseline` 產生；Mod 能力變動時重新產生並在 PR 說明理由。
  validate 的 `gating hook without .catch:` 行不進 baseline，只在輸出提示（AC-15 參考）。

用法：
  python3 scripts/lint-claude-mods.py                  # 主層（有 claude 才跑）＋輔層
  python3 scripts/lint-claude-mods.py --no-validate    # 只跑輔層（CI 用）
  python3 scripts/lint-claude-mods.py --require-validate  # 無 claude CLI 視為失敗（release 前用）
  python3 scripts/lint-claude-mods.py --write-baseline    # 依 validate 結果產生 baseline
  python3 scripts/lint-claude-mods.py --self-test

退出碼：0 = 通過；1 = 有違規；2 = 用法或環境錯誤
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_PLUGIN = Path("plugins/feature-workflow")
BASELINE_NAME = "tests/mod-capabilities.baseline.txt"  # 規格 §18：放在 plugin 的 tests/ 下
FIXTURE_DIR = REPO / "scripts" / "fixtures" / "claude-mods"
STANDARD_HOOKS = "hooks/hooks.json"

# --- R2：禁止呼叫 ------------------------------------------------------------
# 接收者不限 `$`（`ctx.fs.write(` 之類改名也擋），但必須有接收者——
# 這樣 `on('tool.call', …)` 這種訂閱 hook 事件的字串不會被誤擋。容許空白、換行與 `?.`。
# key = 規格列出的禁止字串（報錯時顯示），value = 對應 regex。
_RECV = r"[\w$)\]]\s*\??\.\s*"
FORBIDDEN_CALLS = {
    "$.fs.write(": _RECV + r"fs\s*\??\.\s*write\b",
    "$.model.complete(": _RECV + r"model\s*\??\.\s*complete\b",
    "$.tool.call(": _RECV + r"tool\s*\??\.\s*call\b",
    "$.tool.check(": _RECV + r"tool\s*\??\.\s*check\b",
    "$.prompt.submit(": _RECV + r"prompt\s*\??\.\s*submit\b",
    "$.process.run(": _RECV + r"process\s*\??\.\s*run\b",
    "$.process.spawn(": _RECV + r"process\s*\??\.\s*spawn\b",
    # 規格 §18「不應出現」補齊（原本漏掉的）：
    "$.http.fetch(": _RECV + r"http\s*\??\.\s*fetch\b",
    "$.mcp.call(": _RECV + r"mcp\s*\??\.\s*call\b",
    "$.model.fork(": _RECV + r"model\s*\??\.\s*fork\b",
    "$.model.classify(": _RECV + r"model\s*\??\.\s*classify\b",
    "$.prompt.edit(": _RECV + r"prompt\s*\??\.\s*edit\b",
    "$.tool.register(": _RECV + r"tool\s*\??\.\s*register\b",
}

# allowlist：`$.<noun>` 只准這些 noun（MVP 唯讀面）。比 denylist 穩——
# 型別新增任何 noun／method（EngineInterface 擴充）預設就被擋，不必追著補清單。
ALLOWED_NOUNS = {"session", "fs", "ui", "state", "store", "command", "prompt", "clock"}
ALLOWED_METHODS = {"fs": {"read", "list", "exists", "stat"}, "prompt": {"fill", "read"}}
NOUN_RE = re.compile(r"(?<![\w$.])\$\s*\??\.\s*([A-Za-z_]\w*)(?:\s*\??\.\s*([A-Za-z_]\w*))?")
FORBIDDEN_RE = {name: re.compile(rx) for name, rx in FORBIDDEN_CALLS.items()}

# --- R3：整體賦值／解構／動態存取 --------------------------------------------
BANNED_NS = r"(?:fs|process|model|tool|http|mcp|agent)"
ALIAS_RULES = {
    # `$.fs` 後面不是成員存取（`.read`、`?.read`、`['x']`；用運算子判斷，避免換行 ASI 漏判）→ 整體取用（= $.fs、f($.fs)、return $.fs …）
    "整體取用 $.fs/$.process/$.model/$.tool": re.compile(
        r"\$\s*\??\.\s*" + BANNED_NS + r"\b(?!\s*(?:\?\.|\.|\[))"
    ),
    # 解構：{ fs } = $、{ fs, ui } = $、{ ui, fs: f } = $
    "解構取出 fs/process/model/tool": re.compile(
        r"\{[^{}]*\b" + BANNED_NS + r"\b[^{}]*\}\s*=\s*\$(?![\w$])"
    ),
    # 函式第一個參數直接解構（({ fs }, e, next) =>）
    "參數解構取出 fs/process/model/tool": re.compile(
        r"\(\s*\{[^{}]*\b" + BANNED_NS + r"\b[^{}]*\}\s*(?::[^,)]*)?,\s*[A-Za-z_$]"
    ),
    # 把整個 $ 存成別的名字：const api = $;
    "別名整個 $": re.compile(r"(?:\b(?:const|let|var)\s+[A-Za-z_$][\w$]*|[A-Za-z_$][\w$]*)\s*=\s*\$\s*(?:[;,)\n]|$)"),
    # 動態存取：$['fs']、$.fs['write']、$[name]
    "動態存取 $[...]": re.compile(r"\$\s*\??\.?\s*\["),
    "動態存取 $.fs[...]": re.compile(r"\$\s*\??\.\s*" + BANNED_NS + r"\s*\??\.?\s*\["),
    # 轉型後存取：($ as any)[k]、($ as X).fs、$ as unknown、$ satisfies
    "轉型 $ as／satisfies": re.compile(r"(?<![\w$])\$\s+(?:as|satisfies)\b"),
    # 泛型斷言：<any>$、<Record<string, any>>$
    "轉型 <T>$": re.compile(r"(?<![=\-])<\s*[A-Za-z_][\w\s,.\[\]|&<>]*(?<![=\-])>\s*\$(?![\w$])"),
    # 非 null 斷言後再存取：$![k]
    "非 null 斷言 $!": re.compile(r"(?<![\w$])\$!"),
    # 括號包住的 $ 再存取：($)[k]、($).fs
    "括號包 $ 後存取": re.compile(r"(?<![\w$)\]>])\(\s*\$\s*\)\s*(?:\?\.|\.|\[)"),
    # 反射：Reflect.get($,'process')、Object.entries($)、Object.assign({}, $) 等把 $ 交給內建反射函式
    "Reflect/Object 反射 $": re.compile(r"\b(?:Reflect|Object)\s*\.\s*\w+\s*\([^)]*(?<![\w$.])\$(?![\w$.])"),
    # 展開：{ ...$ }、[...$]
    "展開 $": re.compile(r"\.\.\.\s*\$(?![\w$])"),
}
DESTRUCT_DOLLAR = re.compile(r"\{([^{}]*)\}\s*=\s*\$(?![\w$]|\s*\??\.)")
RULE_FORBIDDEN = "forbidden-call"
RULE_ALIAS = "alias"
RULE_NOUN = "forbidden-noun"
RULE_DUP = "dup-decl"


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def strip_comments(text: str) -> str:
    """把 // 與 /* */ 註解換成空白（保留換行，行號不變）。

    只在字串（' " `）之外才認註解起點，所以 `"//"; $.http.get()` 這種把程式碼藏在
    「看起來像註解」之後的寫法不會被吃掉。template 的 `${ … }` 內視為程式碼。
    regex literal 內含引號時可能誤判——那種殘餘風險由主層負責。
    """
    out: list[str] = []
    i, n = 0, len(text)
    stack: list[str] = []  # 目前所在：'\'' '"' '`'（字串）或 '{'（template 的 ${ } 程式碼區）
    brace_depth: list[int] = []
    while i < n:
        c = text[i]
        top = stack[-1] if stack else None
        if top in ("'", '"', "`"):
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == top:
                stack.pop()
            elif top == "`" and c == "$" and i + 1 < n and text[i + 1] == "{":
                out.append("{")
                stack.append("{")
                brace_depth.append(0)
                i += 2
                continue
            i += 1
            continue
        # 程式碼區（含 ${ } 內）
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("".join("\n" if ch == "\n" else " " for ch in text[i:j]))
            i = j
            continue
        if c in ("'", '"', "`"):
            stack.append(c)
        elif top == "{":
            if c == "{":
                brace_depth[-1] += 1
            elif c == "}":
                if brace_depth[-1] == 0:
                    stack.pop()
                    brace_depth.pop()
                else:
                    brace_depth[-1] -= 1
        out.append(c)
        i += 1
    return "".join(out)


# --- R6：$-taking 函式名稱重複宣告 ------------------------------------------------

_IDENT = r"[A-Za-z_$][\w$]*"
_DECL_KW_RE = re.compile(r"(?<![\w$.])(?:const|let|var|function\s*\*?|class)\s+(" + _IDENT + r")")
_DECL_PATTERN_RE = re.compile(r"(?<![\w$.])(?:const|let|var)\s*([{\[])")
_FUNC_DECL_RE = re.compile(r"(?<![\w$.])function\s*\*?\s*(" + _IDENT + r")\s*(?:<[^()]*>)?\s*\(")
_FUNC_EXPR_RE = re.compile(
    r"(?<![\w$.])(?:const|let|var)\s+(" + _IDENT + r")\s*(?::[^=;]*?)?=\s*(?:async\s+)?"
    r"(?:function\b[^(]*\(|\(|(" + _IDENT + r")\s*=>)"
)
_TRAILING_WORD_RE = re.compile(r"([A-Za-z_$][\w$]*)\s*$")
_PARAM_OK_WORDS = {"return", "await", "yield", "async", "else", "do", "typeof", "void", "case", "in", "of", "new"}


def strip_strings(code: str) -> str:
    """把字串字面值的內容換成空白（保留引號與換行）；template 的 `${ }` 內視為程式碼。輸入須已去註解。"""
    out: list[str] = []
    i, n = 0, len(code)
    stack: list[str] = []
    depth: list[int] = []
    while i < n:
        c = code[i]
        top = stack[-1] if stack else None
        if top in ("'", '"', "`"):
            if c == "\\" and i + 1 < n:
                out.append("  ")
                i += 2
                continue
            if c == top:
                stack.pop()
                out.append(c)
            elif top == "`" and c == "$" and i + 1 < n and code[i + 1] == "{":
                out.append("${")
                stack.append("{")
                depth.append(0)
                i += 2
                continue
            else:
                out.append("\n" if c == "\n" else " ")
            i += 1
            continue
        if c in ("'", '"', "`"):
            stack.append(c)
        elif top == "{":
            if c == "{":
                depth[-1] += 1
            elif c == "}":
                if depth[-1] == 0:
                    stack.pop()
                    depth.pop()
                else:
                    depth[-1] -= 1
        out.append(c)
        i += 1
    return "".join(out)


def _match_close(code: str, i: int) -> int:
    """code[i] 是 ( { [ 之一，回傳對應收尾符號的位置；找不到回 -1。"""
    pairs = {"(": ")", "{": "}", "[": "]"}
    o = code[i]
    c = pairs[o]
    d = 0
    for j in range(i, len(code)):
        if code[j] == o:
            d += 1
        elif code[j] == c:
            d -= 1
            if d == 0:
                return j
    return -1


def _split_items(s: str) -> list[tuple[int, str]]:
    """依頂層逗號切分，回傳 [(起點偏移, 片段)]；型別標註內的 <…, …> 逗號不切。"""
    items: list[tuple[int, str]] = []
    depth = angle = 0
    in_type = False
    start = 0
    for k, ch in enumerate(s):
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth = max(0, depth - 1)
        elif depth == 0:
            if ch == ":" :
                in_type = True
            elif in_type and ch == "<":
                angle += 1
            elif in_type and ch == ">" and (k == 0 or s[k - 1] != "="):
                angle = max(0, angle - 1)
            elif ch == "," and angle == 0:
                items.append((start, s[start:k]))
                start = k + 1
                in_type = False
    items.append((start, s[start:]))
    return items


def _pattern_names(s: str, base: int, is_object: bool | None = None) -> list[tuple[str, int]]:
    """解構樣式（不含外層括號）內宣告的名稱，回傳 [(name, 在原文的偏移)]。"""
    names: list[tuple[str, int]] = []
    for off, item in _split_items(s):
        m = re.match(r"\s*(?:\.\.\.)?\s*", item)
        lead = m.end() if m else 0
        body = item[lead:]
        pos = base + off + lead
        if not body:
            continue
        if is_object and ":" in body.split("=")[0] and body[0] not in "{[":
            # { key: target } → 宣告的是 target
            colon = body.index(":")
            body, pos = body[colon + 1:], pos + colon + 1
            lead2 = len(body) - len(body.lstrip())
            body, pos = body.lstrip(), pos + lead2
        if body and body[0] in "{[":
            end = _match_close(body, 0)
            if end > 0:
                names += _pattern_names(body[1:end], pos + 1, body[0] == "{")
            continue
        m = re.match(_IDENT, body)
        if m:
            names.append((m.group(0), pos))
    return names


def _param_names(params: str, base: int) -> list[tuple[str, int]]:
    names: list[tuple[str, int]] = []
    for off, item in _split_items(params):
        lead = len(item) - len(item.lstrip())
        body = item[lead:]
        pos = base + off + lead
        body = re.sub(r"^(?:\.\.\.|(?:public|private|protected|readonly)\s+)+", "", body)
        pos += len(item[lead:]) - len(body)
        if not body:
            continue
        if body[0] in "{[":
            end = _match_close(body, 0)
            if end > 0:
                names += _pattern_names(body[1:end], pos + 1, body[0] == "{")
            continue
        m = re.match(_IDENT, body)
        if m and re.match(r"\s*\??\s*(?::|=|$)", body[m.end():]):
            names.append((m.group(0), pos))
    return names


def _takes_dollar(params: str) -> bool:
    return bool(re.search(r"(?<![\w$.])\$[\w$]*\s*\??\s*(?::|,|=|$)", params.strip() + " ") or "EngineInterface" in params)


def find_dup_dollar_functions(code: str) -> list[tuple[str, list[int]]]:
    """回傳 [(識別字, [宣告處的偏移…])]：識別字是接收 $ 的函式，且同檔宣告 ≥ 2 次。code 須已去註解、去字串內容。"""
    decls: dict[str, list[int]] = {}

    def add(name: str, pos: int) -> None:
        decls.setdefault(name, []).append(pos)

    for m in _DECL_KW_RE.finditer(code):
        add(m.group(1), m.start(1))
    for m in _DECL_PATTERN_RE.finditer(code):
        o = m.start(1)
        e = _match_close(code, o)
        if e > 0:
            for name, pos in _pattern_names(code[o + 1:e], o + 1, code[o] == "{"):
                add(name, pos)
    dollar_fns: set[str] = set()
    for m in _FUNC_DECL_RE.finditer(code):
        o = m.end() - 1
        e = _match_close(code, o)
        if e > 0 and _takes_dollar(code[o + 1:e]):
            dollar_fns.add(m.group(1))
    for m in _FUNC_EXPR_RE.finditer(code):
        if m.group(2):  # `const f = $ =>` 單參數箭頭
            if m.group(2).startswith("$"):
                dollar_fns.add(m.group(1))
            continue
        o = m.end() - 1
        if code[o] != "(":
            continue
        e = _match_close(code, o)
        if e > 0 and _takes_dollar(code[o + 1:e]):
            dollar_fns.add(m.group(1))
    # 函式／箭頭函式的參數也是宣告
    for m in re.finditer(r"\(", code):
        o = m.start()
        before = code[:o]
        if re.search(r"[\w$.\])]\s*$", before):  # 前面接著識別字／屬性／呼叫：多半是呼叫式，不是參數列
            w = _TRAILING_WORD_RE.search(before)
            fn_like = re.search(r"(?<![\w$.])(?:function\s*\*?|async)\s*(?:" + _IDENT + r")?\s*$", before)
            if not fn_like and not (w and w.group(1) in _PARAM_OK_WORDS and not before.rstrip().endswith(".")):
                continue
        e = _match_close(code, o)
        if e < 0 or not re.match(r"\s*(?::[^;{}=()]*?)?\s*(?:=>|\{)", code[e + 1:]):
            continue
        for name, pos in _param_names(code[o + 1:e], o + 1):
            add(name, pos)
    for m in re.finditer(r"(?<![\w$.])(" + _IDENT + r")\s*=>", code):
        add(m.group(1), m.start(1))
    return sorted((n, sorted(set(p))) for n, p in decls.items() if n in dollar_fns and len(set(p)) >= 2)


def scan_dup_decl(name: str, text: str) -> list[tuple[str, str]]:
    code = strip_strings(strip_comments(text))
    out = []
    for ident, poss in find_dup_dollar_functions(code):
        lines = "、".join(str(line_of(code, p)) for p in poss)
        out.append((RULE_DUP, f"{name}:{line_of(code, poss[1])} 識別字 `{ident}` 是接收 $ 的函式，卻在同檔被宣告 {len(poss)} 次（行 {lines}）；"
                              f"Claude Code 2.1.289 會以 declared more than once in this file 拒載整個 Mod，請把區域變數／參數改名"))
    return out


def scan_source(name: str, text: str) -> list[tuple[str, str]]:
    """回傳 [(rule, 訊息)]。rule ∈ forbidden-call / alias / forbidden-noun / dup-decl。"""
    out: list[tuple[str, str]] = []
    for label, rx in FORBIDDEN_RE.items():
        for m in rx.finditer(text):
            out.append((RULE_FORBIDDEN, f"{name}:{line_of(text, m.start())} 含禁止呼叫 `{label}`"))
    for label, rx in ALIAS_RULES.items():
        for m in rx.finditer(text):
            out.append((RULE_ALIAS, f"{name}:{line_of(text, m.start())} {label}（規避字串比對的前置動作）"))
    # allowlist：`$.<noun>[.<method>]`（先去掉註解，註解裡的 `$.fs.*` 說明文字不算呼叫）
    code = strip_comments(text)
    for m in NOUN_RE.finditer(code):
        noun, method = m.group(1), m.group(2)
        if noun not in ALLOWED_NOUNS:
            out.append((RULE_NOUN, f"{name}:{line_of(code, m.start())} `$.{noun}` 不在 allowlist（只准 {'/'.join(sorted(ALLOWED_NOUNS))}）"))
        elif noun in ALLOWED_METHODS and method not in ALLOWED_METHODS[noun]:
            out.append((RULE_NOUN, f"{name}:{line_of(code, m.start())} `$.{noun}.{method}` 不在 allowlist（{noun} 只准 {'/'.join(sorted(ALLOWED_METHODS[noun]))}）"))
    # 解構 `{ a, b } = $`：任何不在 allowlist 的 noun（或 fs 整包）都擋
    for m in DESTRUCT_DOLLAR.finditer(code):
        for part in m.group(1).split(","):
            key = part.strip().lstrip(".").split(":")[0].split("=")[0].strip()
            if key and key not in ALLOWED_NOUNS:
                out.append((RULE_NOUN, f"{name}:{line_of(code, m.start())} 解構取出 `{key}` 不在 allowlist"))
    out += scan_dup_decl(name, text)  # R6
    return out


# --- R1 / R4 / R5：純函式，吃 dict 方便 self-test --------------------------


def normalize_rel(p: str) -> str:
    p = p.strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def check_modules(hooks_json: dict, exists) -> list[str]:
    """R1：modules 必須存在且每條路徑都解得到檔案。exists(rel_path)->bool，rel 相對 hooks.json 所在目錄。"""
    mods = hooks_json.get("modules")
    if not isinstance(mods, list) or not mods:
        return ["R1 hooks.json 缺 modules 宣告（Cockpit Mod 未掛載）"]
    errs = []
    for m in mods:
        if not isinstance(m, str) or not exists(m):
            errs.append(f"R1 modules 路徑不存在：{m!r}")
    return errs


def check_session_start(hooks_json: dict) -> list[str]:
    """R4：既有 SessionStart brief hook 仍在（含 crew-state.py session-brief 指令）。"""
    entries = (hooks_json.get("hooks") or {}).get("SessionStart")
    if not isinstance(entries, list) or not entries:
        return ["R4 hooks.json 的 hooks.SessionStart 不見了（既有 session brief 被移除）"]
    for entry in entries:
        for h in (entry or {}).get("hooks") or []:
            cmd = str((h or {}).get("command", ""))
            if "crew-state.py" in cmd and "session-brief" in cmd:
                return []
    return ["R4 hooks.SessionStart 存在，但找不到 `crew-state.py session-brief` 指令（brief hook 被改掉）"]


def check_manifest(label: str, manifest: dict) -> list[str]:
    """R5：manifest 的 hooks 不得宣告標準 hooks/hooks.json（否則 Duplicate hooks file detected）。"""
    hooks = manifest.get("hooks")
    entries = [hooks] if isinstance(hooks, str) else [e for e in hooks if isinstance(e, str)] if isinstance(hooks, list) else []
    return [
        f"R5 {label}: manifest 重複宣告標準 `{e}`（會造成 Duplicate hooks file detected）"
        for e in entries
        if normalize_rel(e) == STANDARD_HOOKS
    ]


# --- 主層：validate 解析 ------------------------------------------------------


def split_top_level(s: str) -> list[str]:
    """以逗號切分，但尊重 {} 與 () 內的逗號（例：「(via a, b)」）。"""
    parts, depth, cur = [], 0, []
    for ch in s:
        if ch in "{(":
            depth += 1
        elif ch in "})":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    tail = "".join(cur).strip()
    if tail:
        parts.append(tail)
    return [p for p in parts if p]


NOTE_RE = re.compile(r"^(\S+) (hooks|calls|state writes|state reads|gating hook without \.catch): ?(.*)$")
KIND = {"hooks": "hook", "calls": "call", "state writes": "state-write", "state reads": "state-read"}


VIA_RE = re.compile(r"\s+\(via [^()]*\)$")


def parse_validate(data: dict) -> tuple[set[str], list[str], list[str]]:
    """回傳 (能力項目集合, errors, 無 catch 的 gating hook 提示)。"""
    items: set[str] = set()
    errors: list[str] = []
    gating: list[str] = []
    containers = [data.get("manifest") or {}] + list(data.get("contents") or [])
    for c in containers:
        for e in c.get("errors") or []:
            errors.append(f"{e.get('path', '?')}: {e.get('message', e)}" if isinstance(e, dict) else str(e))
        if c.get("type") != "hooks":
            continue
        for note in c.get("notes") or []:
            m = NOTE_RE.match(note)
            if not m:
                continue
            module, what, rest = m.groups()
            if what in KIND:
                for spec in split_top_level(rest):
                    # validate 對經由 helper 的呼叫會加註「 (via 函式名)」；能力本身與 helper 名稱無關，
                    # 去掉後綴才不會因重新命名 helper 而誤報新能力
                    spec = VIA_RE.sub("", spec)
                    items.add(f"{module} {KIND[what]} {spec}")
            else:
                gating.append(f"{module} {rest}")
    return items, errors, gating


BASELINE_HEADER = (
    "# CREW Cockpit Mod capability baseline（由 scripts/lint-claude-mods.py --write-baseline 產生）\n"
    "# 格式：<module> hook|call|state-write|state-read <項目>；一行一項、已排序。\n"
    "# 新增能力 → lint fail，須重新產生本檔並在 PR 說明為何 MVP 不可避免（規格 §18）。\n"
)


def render_baseline(items: set[str]) -> str:
    return BASELINE_HEADER + "".join(f"{i}\n" for i in sorted(items))


def parse_baseline(text: str) -> set[str]:
    return {ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")}


def compare_baseline(current: set[str], baseline: set[str]) -> tuple[list[str], list[str]]:
    """回傳 (新增能力＝fail, 消失能力＝提示)。"""
    return sorted(current - baseline), sorted(baseline - current)


def run_validate(plugin_dir: Path) -> dict:
    proc = subprocess.run(
        ["claude", "plugin", "validate", "--json", str(plugin_dir)],
        capture_output=True, text=True, timeout=180,
    )
    out = proc.stdout
    start = out.find("{")
    if start < 0:
        raise RuntimeError(f"validate 沒有輸出 JSON（exit={proc.returncode}）：{(proc.stderr or out)[:300]}")
    return json.loads(out[start:])


# --- 輔層：對真實 repo ---------------------------------------------------------


def mod_sources(plugin_dir: Path) -> list[Path]:
    hooks_dir = plugin_dir / "hooks"
    files = []
    for p in sorted(hooks_dir.rglob("*")):
        if p.suffix not in (".ts", ".tsx") or p.name.endswith(".d.ts"):
            continue
        if "tests" in p.relative_to(hooks_dir).parts:
            continue
        files.append(p)
    return files


def aux_layer(root: Path, plugin_rel: Path) -> list[str]:
    plugin_dir = root / plugin_rel
    hooks_path = plugin_dir / "hooks" / "hooks.json"
    errs: list[str] = []
    try:
        hooks_json = json.loads(hooks_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"無法讀取 {hooks_path}：{exc}"]
    errs += check_modules(hooks_json, lambda m: (hooks_path.parent / m).is_file())
    errs += check_session_start(hooks_json)
    for mp in (plugin_dir / ".claude-plugin" / "plugin.json", plugin_dir / "plugin.json"):
        if mp.is_file():
            try:
                errs += check_manifest(str(mp.relative_to(root)), json.loads(mp.read_text(encoding="utf-8")))
            except ValueError as exc:
                errs.append(f"{mp} 不是合法 JSON：{exc}")
    for src in mod_sources(plugin_dir):
        rel = str(src.relative_to(root))
        for rule, msg in scan_source(rel, src.read_text(encoding="utf-8")):
            errs.append(("R6 " if rule == RULE_DUP else "R3 " if rule == RULE_ALIAS else "R2 ") + msg)
    return errs


def main_layer(plugin_dir: Path, baseline_path: Path, write: bool) -> tuple[int, list[str]]:
    """回傳 (exit code, 輸出行)。"""
    lines: list[str] = []
    try:
        data = run_validate(plugin_dir)
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        return 1, [f"❌ 主層：claude plugin validate 失敗：{exc}"]
    items, errors, gating = parse_validate(data)
    for g in gating:
        lines.append(f"⚠️  gating hook 無 .catch（AC-15 參考，不阻擋）：{g}")
    if errors:
        lines += [f"❌ 主層：validate 回報 error：{e}" for e in errors]
        return 1, lines
    if write:
        baseline_path.write_text(render_baseline(items), encoding="utf-8")
        lines.append(f"✅ 已寫入 {baseline_path}（{len(items)} 項）")
        return 0, lines
    if not baseline_path.is_file():
        return 1, lines + [f"❌ 主層：baseline 不存在：{baseline_path}（先跑 --write-baseline）"]
    new, gone = compare_baseline(items, parse_baseline(baseline_path.read_text(encoding="utf-8")))
    for i in gone:
        lines.append(f"ℹ️  baseline 有但 validate 沒有（能力縮小，不算錯）：{i}")
    if new:
        lines += [f"❌ 主層：出現 baseline 沒有的新能力：{i}" for i in new]
        return 1, lines
    lines.append(f"✅ 主層：能力清單與 baseline 一致（{len(items)} 項）")
    return 0, lines


# --- self-test ----------------------------------------------------------------


def self_test() -> int:
    fails: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            fails.append(msg)

    # 1) fixtures：bad-* 必 fail 且命中指定規則；good-* 必 pass
    check(FIXTURE_DIR.is_dir(), f"fixtures 目錄不存在：{FIXTURE_DIR}")
    bad_files = sorted(FIXTURE_DIR.glob("bad-*.ts"))
    good_files = sorted(FIXTURE_DIR.glob("good-*.ts"))
    check(len(good_files) >= 1, "缺 good-* 正對照 fixture")
    covered_labels: set[str] = set()
    for f in bad_files:
        text = f.read_text(encoding="utf-8")
        m = re.search(r"expect:\s*(forbidden-call|alias|forbidden-noun|dup-decl)(?:[ \t]+(\S+))?", text)
        check(m is not None, f"{f.name} 缺 `expect:` 標頭")
        if not m:
            continue
        hits = scan_source(f.name, text)
        rules = {r for r, _ in hits}
        check(m.group(1) in rules, f"{f.name} 應命中規則 {m.group(1)}，實際 {sorted(rules) or '無'}")
        want = (m.group(2) or "").strip()
        if want and m.group(1) == "dup-decl":  # 標頭寫識別字，訊息須指名該識別字與 2.1.289
            check(any(f"`{want}`" in msg and "2.1.289" in msg for _, msg in hits), f"{f.name} 應指名重複識別字 `{want}`：{[x for _, x in hits]}")
            want = ""
        if want:  # 標頭寫 fs/write（避免標頭註解自己命中規則），還原成 $.fs.write(
            want = "$." + want.replace("/", ".") + "("
        if want:
            check(any(want in msg for _, msg in hits), f"{f.name} 應命中 `{want}`，實際訊息：{[x for _, x in hits]}")
            covered_labels.add(want)
    for label in FORBIDDEN_CALLS:
        check(label in covered_labels, f"禁止 pattern 缺反向 fixture：{label}")
    check(len(bad_files) >= len(FORBIDDEN_CALLS) + 4, f"反向 fixture 太少（{len(bad_files)}）")
    for f in good_files:
        hits = scan_source(f.name, f.read_text(encoding="utf-8"))
        check(not hits, f"{f.name} 是正對照卻被擋：{hits}")

    # 2) 輔層純函式
    check(check_modules({"modules": ["./a.tsx"]}, lambda m: True) == [], "modules 存在應 pass")
    check(len(check_modules({"modules": ["./a.tsx"]}, lambda m: False)) == 1, "modules 不存在應 fail")
    check(len(check_modules({}, lambda m: True)) == 1, "缺 modules 應 fail")
    ss_ok = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "python3 crew-state.py session-brief --cwd x"}]}]}}
    check(check_session_start(ss_ok) == [], "SessionStart 在應 pass")
    check(len(check_session_start({"hooks": {}})) == 1, "SessionStart 不見應 fail")
    check(len(check_session_start({"hooks": {"SessionStart": [{"hooks": [{"command": "echo hi"}]}]}})) == 1, "brief 指令被換掉應 fail")
    check(check_manifest("m", {"hooks": "./extra.json"}) == [], "額外 hook 檔應 pass")
    check(len(check_manifest("m", {"hooks": "./hooks/hooks.json"})) == 1, "重複宣告標準 hooks 應 fail")
    check(len(check_manifest("m", {"hooks": ["extra.json", "hooks/hooks.json"]})) == 1, "list 內重複宣告應 fail")
    check(check_manifest("m", {}) == [], "未宣告 hooks 應 pass")

    # 3) 主層：假 validate JSON
    def fake(hooks_spec: str, calls_spec: str, errors=None) -> dict:
        return {
            "manifest": {"errors": []},
            "contents": [{
                "type": "hooks", "errors": errors or [],
                "notes": [
                    f"./register.tsx hooks: {hooks_spec}",
                    f"./register.tsx calls: {calls_spec}",
                    "./register.tsx gating hook without .catch: tool.call",
                    "./register.tsx state writes: tool-calls.calls",
                ],
            }],
        }

    base_data = fake(
        "session.start, command.run{command=tool-calls}, tool.call, ui.render{component=Pane, requestId=tool-calls}",
        "$.command.register, $.state.get, $.ui.open",
    )
    items, errors, gating = parse_validate(base_data)
    check("./register.tsx hook ui.render{component=Pane, requestId=tool-calls}" in items, "大括號內逗號未被正確保留")
    check("./register.tsx hook command.run{command=tool-calls}" in items, "command.run 項解析錯誤")
    check("./register.tsx hook requestId=tool-calls}" not in items and not any(i.endswith(" hook requestId=tool-calls}") for i in items), "大括號內逗號被誤切")
    check(len([i for i in items if " hook " in i]) == 4, f"hook 項數應為 4：{sorted(items)}")
    check("./register.tsx state-write tool-calls.calls" in items, "state writes 未解析")
    check(gating == ["./register.tsx tool.call"], f"gating 提示解析錯誤：{gating}")
    check(errors == [], "無 error 時不應有 errors")
    baseline = parse_baseline(render_baseline(items))
    check(baseline == items, "baseline render/parse 不可逆")
    check(compare_baseline(items, baseline) == ([], []), "相同清單應一致")
    more, _, _ = parse_validate(fake(
        "session.start, command.run{command=tool-calls}, tool.call, ui.render{component=Pane, requestId=tool-calls}",
        "$.command.register, $.state.get, $.ui.open, $.fs.write",
    ))
    new, gone = compare_baseline(more, baseline)
    check(new == ["./register.tsx call $.fs.write"] and gone == [], f"多一項應 fail：{new}/{gone}")
    fewer, _, _ = parse_validate(fake(
        "session.start, command.run{command=tool-calls}, tool.call, ui.render{component=Pane, requestId=tool-calls}",
        "$.command.register, $.ui.open",
    ))
    new, gone = compare_baseline(fewer, baseline)
    check(new == [] and gone == ["./register.tsx call $.state.get"], f"少一項應 pass 且提示：{new}/{gone}")
    _, errs2, _ = parse_validate(fake("session.start", "$.ui.open", errors=[{"path": "p", "message": "boom"}]))
    check(errs2 == ["p: boom"], f"validate errors 應被收集：{errs2}")
    check(split_top_level("a{x=1, y=2}, b") == ["a{x=1, y=2}", "b"], "split_top_level 錯誤")
    check(split_top_level("$.a (via f, g), $.b") == ["$.a (via f, g)", "$.b"], "split_top_level 須尊重 () 內逗號")
    via3, _, _ = parse_validate(fake("session.start", "$.session.repo (via hudStoreKey, portsOf), $.ui.open"))
    check(via3 == {"./register.tsx call $.session.repo", "./register.tsx call $.ui.open",
                   "./register.tsx hook session.start", "./register.tsx state-write tool-calls.calls"},
          f"多個 via 應整段去除：{sorted(via3)}")
    via, _, _ = parse_validate(fake("session.start", "$.fs.read (via portsOf), $.ui.open"))
    check("./register.tsx call $.fs.read" in via and "./register.tsx call $.fs.read (via portsOf)" not in via,
          f"「(via helper)」後綴應被去除：{sorted(via)}")
    via2, _, _ = parse_validate(fake("session.start", "$.fs.write (via helper)"))
    check("./register.tsx call $.fs.write" in via2, f"經 helper 的禁止呼叫仍須以本名列入：{sorted(via2)}")

    if fails:
        for f in fails:
            print(f"❌ self-test：{f}")
        return 1
    print(f"✅ lint-claude-mods self-test passed（反向 fixture {len(bad_files)} 個、正對照 {len(good_files)} 個）")
    return 0


# --- CLI ----------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="CREW Cockpit Mod guard（規格 §23）")
    ap.add_argument("--self-test", action="store_true", help="執行內建 regression tests")
    ap.add_argument("--no-validate", action="store_true", help="只跑輔層（CI 用）")
    ap.add_argument("--require-validate", action="store_true", help="無 claude CLI 時視為失敗")
    ap.add_argument("--write-baseline", action="store_true", help="依 validate 結果產生 baseline 檔")
    ap.add_argument("--root", type=Path, default=REPO, help="repo 根目錄（預設本腳本所在 repo）")
    ap.add_argument("--plugin-dir", type=Path, default=DEFAULT_PLUGIN, help="plugin 目錄，相對 --root")
    ap.add_argument("--baseline", type=Path, default=None, help="baseline 檔路徑（預設 <plugin-dir>/" + BASELINE_NAME + "）")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    plugin_dir = args.root / args.plugin_dir
    baseline_path = args.baseline or (plugin_dir / BASELINE_NAME)
    rc = 0

    if args.write_baseline:
        if args.no_validate or not shutil.which("claude"):
            print("❌ --write-baseline 需要 claude CLI")
            return 2
        code, lines = main_layer(plugin_dir, baseline_path, write=True)
        print("\n".join(lines))
        return code

    if args.no_validate:
        print("ℹ️  主層未執行（--no-validate）；僅輔層。主層列為 release 前本機必跑。")
    elif not shutil.which("claude"):
        print("⏭️  主層 SKIP（無 claude CLI）——主層【未執行】，下方只代表輔層結果")
        if args.require_validate:
            print("❌ --require-validate：無 claude CLI，視為失敗")
            rc = 1
    else:
        code, lines = main_layer(plugin_dir, baseline_path, write=False)
        print("\n".join(lines))
        rc = max(rc, code)

    errs = aux_layer(args.root, args.plugin_dir)
    if errs:
        print(f"❌ 輔層：{len(errs)} 項違規")
        for e in errs:
            print(f"  - {e}")
        rc = 1
    else:
        print("✅ 輔層（R1–R6）通過")
    return rc


if __name__ == "__main__":
    sys.exit(main())
