# Browser / MCP Adapter 安裝與整合

> 供 plan-setup、plan-verify 等 Skill 引用。核心 workflow 只要求 browser/tool capability；產品 CLI 只是 Host adapter 範例。

## Capability 優先序

`/plan-verify` UI 模式：

1. `tool_probe(tool_kind=browser, preferred_names=[playwright])`
2. fallback：chrome-devtools browser capability
3. fallback：plugin 內建 `scripts/cdp.mjs`（Node.js 22+ + Chrome remote debugging）
4. 都不可用 → 顯示目前 Host 的 browser/MCP 安裝方式；不要臆造另一家 Host CLI

Playwright 是 preferred adapter，不是 workflow hard prerequisite。

## Claude Code adapter

### Playwright MCP

```bash
claude mcp add playwright --scope user -- \
  npx @playwright/mcp@latest
```

### chrome-devtools-mcp

```bash
claude mcp add chrome-devtools --scope user -- \
  npx chrome-devtools-mcp@latest --autoConnect
```

安裝後重啟 Claude Code，再以實際 tool availability 驗證；CLI listing 只能做輔助證據。

## Codex / 其他 Host

使用目前 Host 正式支援的 MCP / plugin / browser integration 方式提供 Playwright 或等價 browser capability。

CREW **不在此文件臆造固定 Codex MCP CLI**。完成整合後，以 `tool_probe` 確認目前 session 真的能呼叫 browser tools；查不到就走 chrome-devtools / local CDP fallback。

## Local CDP fallback

不需要 MCP，但需要：

- Node.js 22+
- 可讀的 `$CREW_PLUGIN_ROOT/scripts/cdp.mjs`
- Chrome/Chromium 啟用 remote debugging，能找到 `DevToolsActivePort`

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
CDP="node ${CREW_PLUGIN_ROOT}/scripts/cdp.mjs"
$CDP list
```

plugin root 空值時明確報錯，不猜 marketplace/cache path。

> Playwright 適合 QA 驗收；chrome-devtools 適合 console/network/performance 診斷；local CDP 是沒有 Host browser tool 時的 deterministic fallback。
