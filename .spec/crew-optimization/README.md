# CREW 深層優化

- **type**: feature
- **name**: crew-deep-optimization
- **status**: 規格設計
- **branch**: feat/crew-deep-optimization
- **created**: 2026-04-24
- **slug**: crew-optimization

## 需求描述

> **歷史 v1 規劃 artifact**：本檔保留 2026-04-24 當時的需求、status、branch 與「不包含」範圍，不代表 CREW 6 現行 contract；例如當時尚未進行的 portability 已由後續版本完成。現行使用方式以根 README 與各 plugin README 為準。

參考 [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) 的設計理念，對 CREW（feature-workflow plugin）進行深層優化，涵蓋：

1. **AI 紀律護欄**：反合理化表、退出驗證門檻、三層邊界系統
2. **安全左移**：新增 plan-security Skill，安全檢查從 review 階段提前到 build 後
3. **脈絡工程**：改善 Agent Teams delegate 的脈絡傳遞策略
4. **漸進式揭露**：拆分過長的 SKILL.md，按需載入 references/
5. **智慧團隊組成**：根據任務類型（feature/adjustment/bugfix）動態調整團隊規模
6. **技術棧陷阱**：在 stacks/{id}.md 新增「技術棧陷阱」段落

## 不包含

- P3 可攜性層（跨平台支援）— 留待後續版本
- bug-workflow plugin 的修改 — 本次只動 feature-workflow
- Notion MCP 整合變更 — plan-close/plan-sync 不在範圍內
