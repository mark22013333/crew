# ADR-002：為何採 Agent Teams leader-delegate 而非單 agent

- 日期：2026-04-25（plan-build 4.10.0 同期）
- 狀態：**已由 ADR-007 取代（保留為 Claude adapter 的歷史設計）**

> 本 ADR 記錄 CREW 5 時期的原始決策。CREW 6 不再把任何單一 Host 的 team/subagent API 當成核心 workflow contract；新的跨 Host 決策見 [ADR-007](./007-host-capability-portable-orchestration.md)。

## 背景

`/plan-build` 要產出可用程式碼，覆蓋面從 DB migration、POJO、Mapper、Service、Controller、DTO、前端到測試。
單一 AI agent 接到完整任務有兩個明顯缺點：

1. **上下文過載**：所有 reference + spec + db + arch + 現有程式碼學習範本一次塞給 agent，注意力分散。
2. **角色串味**：DBA、後端、API、前端、測試的責任在同一 prompt 內互相干擾。

## 當時決策

CREW 5 採 leader-delegate 模式：

- Leader 讀設計文件、判斷角色、準備分層脈絡。
- 實作角色各自只接收需要的 context 與 write scope。
- 有平行能力時，同時執行互不衝突的角色。
- 透過 Host-native team/subagent 工具做 delegation。

這個「角色隔離 + scope boundary」本身仍有效；被取代的是「必須依賴特定 Host team API 才能完成 workflow」的部分。

## 為什麼被取代

CREW 6 要同時支援 Claude Code 與 Codex。不同 Host 對 subagent、multi-agent、parallel execution、per-worker model selection 的能力不同。

因此核心流程改為 [Host Capability Contract](../../plugins/bug-workflow/references/host-capabilities.md)：

- `delegate_readonly`
- `delegate_write`
- `parallel_delegate`
- sequential / inline fallback
- provider-neutral model routing

沒有 multi-agent 能力時，workflow 仍必須正確完成；差異只應是效能與隔離程度，而不是功能可不可用。

## 歷史後果

**正面**：
- 證明角色隔離能降低上下文混雜。
- 建立 allowed scope、handoff 與角色責任分界的實務基礎。
- 為後來的 capability contract 提供可重用的語意。

**限制**：
- 把一個 Host 的 team lifecycle 誤當成 workflow prerequisite。
- 平行能力缺失時缺少正式 fallback contract。
- provider model / team 工具名稱容易滲透到 Skill 與 README。

## 現行決策

以 ADR-007 為準。Claude adapter 仍可使用其原生平行/子代理能力做最佳化，但它只是 adapter 實作，不是 CREW 核心 API。
