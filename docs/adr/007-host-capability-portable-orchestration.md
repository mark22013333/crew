# ADR-007：Host Capability Contract 取代 Host-specific orchestration

- 日期：2026-09-29
- 狀態：已採用
- 取代：[ADR-002](./002-agent-teams-leader-delegate.md) 中「特定 Host team API 是 workflow 前置」的部分

## 背景

CREW 6 的目標是讓同一套 Bug/Feature workflow 可由 Claude Code 與 Codex 執行。兩個 Host 對 project instructions、subagent、multi-agent、parallel delegation、tool discovery 與 per-worker model routing 的支援不同。

若 Skill 直接要求某個產品工具：

- Host 沒有同名工具就會被錯誤判定為不能執行。
- workflow correctness 與平行效能被混在一起。
- provider model 名稱會滲透到核心流程。
- 測試難以區分「缺 capability」與「adapter 實作不同」。

## 決策

核心 workflow 只依賴 capability，不依賴產品工具名稱：

- `project_instructions`
- `delegate_readonly`
- `delegate_write`
- `parallel_delegate`
- `tool_probe`
- `ask_user`

Model routing 先選 `NONE / FAST / STANDARD / DEEP` profile，再由 Host adapter 做實際 provider mapping。

### 降級規則

| 缺少能力 | 正確 fallback |
|---|---|
| 無 subagent | 主 Agent inline 執行同一唯讀/可寫工作單元 |
| 無 multi-agent | sequential delegation |
| 無 parallel execution | 保持 DAG 順序，失去效能但不失去功能 |
| 無 per-worker model selection | 保留 role/write boundary，標記 routing degraded |
| 無 tool listing | probe 目前 session 真正可呼叫的能力 |
| 無結構化問答 UI | 一般對話取得 Human decision |

平行是最佳化，不是 correctness 的 hard prerequisite。

## 後果

**正面**：
- 同一套 Skill 可以在不同 Host 上維持相同 workflow 語意。
- Host-specific 行為集中在 adapter/reference，README 不再教使用者把某個產品功能當成核心。
- 可用 deterministic lint 阻擋新的 Host coupling。
- model policy 可以獨立於 provider 名稱演進。

**負面**：
- 不同 Host 的效能與隔離程度可能不同。
- adapter 需要誠實回報 degraded capability，不能宣稱不存在的能力已生效。
- 部分歷史文件與 README 需要遷移到 capability/profile 用語。

**中性**：
- Claude Code 仍可使用其原生 delegation/parallel 能力。
- Codex 有 multi-agent 時可以使用；沒有時 sequential/inline 仍是合法路徑。
- workflow 的 Human approval、state transition、write scope、verification 不因 Host 而改變。

## 驗證

- `scripts/lint-host-portability.py --strict`：核心 Skill/reference 不重新引入 Host-specific orchestration。
- `scripts/lint-model-routing.py`：profile/router contract。
- `scripts/lint-readme-architecture.py`：主要 README 不再宣告舊 Host/provider/config contract。
