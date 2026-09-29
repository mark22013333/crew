# CREW 前置條件與系統需求

CREW 6 的核心流程不綁單一 Host。前置條件分成「核心必要」、「依功能需要」與「Host adapter 選配」；不要把某一家 Host 的 team/MCP CLI 當成全域必要條件。

## 核心必要

| 依賴 | 用途 | 備註 |
|------|------|------|
| **Git** | repo-id、分支、diff、commit/evidence | 核心 workflow 需要 |
| **Python 3** | `crew-state.py`、`crew-config.py`、`crew-model-route.py` 等 deterministic runtime | 兩個 plugin 都需要 |
| **一個已安裝 CREW plugins 的 Host** | 執行 Skill | 目前正式驗證 Claude Code + Codex |
| **project_instructions** | 專案規範與架構上下文 | 接受 `AGENTS.md`、`CLAUDE.md`；兩者衝突時保留歧義 |
| **Notion capability** | 建立/同步 Notion-backed task/project | 需要 Notion 的流程才要求；純本地閱讀/部分驗證不應因它缺失而假裝其他 capability 也不可用 |

> 不確定環境是否完整時可跑 `/crew-doctor`。Doctor 會診斷 capability/config/project registration，但不自行建立 CREW-owned config storage。

## 不再是核心必要條件

### Multi-agent / Agent Teams

平行 delegation 是最佳化，不是 workflow correctness 的前置：

- Host 有 subagent/multi-agent → 可以平行互不衝突的工作。
- Host 沒有 → inline / sequential fallback。
- 不能因為某個 team env var 沒開就阻擋 `/plan-build` 或 `/plan-review`。

完整規則見 [Host Capability Contract](../plugins/bug-workflow/references/host-capabilities.md)。

### Provider model 名稱

Workflow 只選 `NONE / FAST / STANDARD / DEEP` profile。實際 provider model / reasoning effort 由 Host adapter 決定，不要用全域環境變數把所有 worker 強制鎖成同一模型。

詳見 [Model Policy](../plugins/bug-workflow/references/model-policy.md)。

---

## 依功能需要的工具

| 工具 | 何時需要 | 沒有時 |
|------|---------|--------|
| **Maven / Gradle / 專案 build tool** | `/plan-build`、`/bug-fix` 驗證 | 無法完成對應 build/test proof |
| **Browser automation capability** | UI `/plan-verify`、前端 Bug 驗證 | 改走 API/manual evidence 或明確標記不可驗證 |
| **DB capability（例如 DBHub）** | 真實 schema/query 探索 | 走 no-DB fallback，不猜 schema |
| **minimax-skills / .NET** | Word 報告 | 可改用其他報告路徑或跳過 |
| **Node.js / npm** | Node-based MCP、ExcelJS、部分外部工具 | 只影響使用到它的功能；版本需求以該工具 upstream 為準 |
| **curl / shell search tools** | API probe、機械搜尋 | 依 Host/OS 使用等價工具 |

外部工具的可用性由 `tool_probe` 判斷「目前 session 是否真的可呼叫」，不要只靠某家的 CLI listing。

---

## Notion Workspace

Notion-backed 流程使用：

- **任務追蹤工具**：Bug / Feature lifecycle
- **專案資料庫**：repo/project metadata
- **Bug 知識庫**（選配）
- **功能設計庫**（選配）

詳細 schema 見 [notion-schema.md](./notion-schema.md)。

### Claude Code adapter

可用 Notion plugin 或 Host 支援的 MCP 設定方式。Claude CLI / settings 只屬 Claude adapter，不是 portable workflow contract。

### Codex / 其他 Host

使用 Host 當下可提供的 Notion/MCP capability。CREW 不要求存在 `claude mcp list` 之類特定產品命令；能實際呼叫對應工具才算 available。

---

## 瀏覽器與 DB 工具

- Browser 驗證：以目前 Host 可用的 Playwright / browser tooling 為主；沒有時走明確 fallback。
- DB：DBHub 是選配方案，詳見 [dbhub.md](./dbhub.md)。
- Windows / shell 差異：見 [windows.md](./windows.md)。

---

## Portable Config

CREW-owned config root：

1. `CREW_CONFIG_HOME`
2. `$XDG_CONFIG_HOME/crew`
3. `~/.config/crew`

Skill 透過 `plugins/*/scripts/crew-config.py` 存取 `bug/config`、`bug/learning`、`feature/config`、`feature/project`、`feature/stack`。Host marketplace、plugin cache、settings/rules 不屬此 contract。
