---
type: feature
name: plan-verify 進化 — 萃取 E2E 智慧 + 驗證記憶系統
slug: plan-verify-evolution
status: 程式碼審查
notion_url: https://www.notion.so/plan-verify-E2E-361a401be0f581c58decf4789292009e
notion_page_id: 361a401b-e0f5-81c5-8dec-f4789292009e
branch: feature/plan-verify-evolution
tech_stack:
created: 2026-05-15
---

# plan-verify 進化 — 萃取 E2E 智慧 + 驗證記憶系統

> **歷史 v1 規劃 artifact**：本檔保留 2026-05-15 當時的需求、status 與設計決策，不代表目前 `plan-verify` 的完整功能契約。現行行為以 Feature Workflow README 與 active Skill/reference 為準。

## 需求描述

以 SmartRobotE2ETest（Playwright E2E 測試框架，109 個 spec 檔案、32,775 行）為知識來源，對 plan-verify 技能進行三階段優化。核心理念：**萃取 E2E 的成熟策略內建到 plugin，而非在 runtime 依賴外部 repo**。

### 動機

1. plan-verify 每次從零操作瀏覽器 — 不知道怎麼登入、頁面在哪、selector 是什麼
2. 截圖不穩定 — 缺乏系統化的穩定等待策略
3. 報告格式單一 — 只有 Word，客戶也需要 Excel
4. 不會成長 — 每次驗證的經驗不會累積
5. 不支援多語系 — 產品支援 8 語系，驗證時碰到非中文就出問題

### 三階段規劃

| Phase | 名稱 | 核心 | 受益範圍 | 外部依賴 |
|-------|------|------|---------|---------|
| 1 | 萃取 + 內建 | 從 E2E 萃取通用策略嵌入 plugin | 所有專案 | 零 |
| 2 | 產品知識庫 | 內建產品操作知識加速驗證 | 產品專案 | 零 |
| 3 | E2E 橋接 | 可選的 Runner 模式 + 測試骨架產出 | 有 E2E repo 的團隊 | 可選 |

跨階段功能：**驗證記憶系統** — 三層記憶 + 自動升級，讓驗證流程越來越快。

### 關鍵設計決策

1. **Plugin 自給自足** — 所有核心功能不依賴外部 repo，裝了就能用，同事不需要 clone SmartRobotE2ETest
2. **i18n 先支援 4 語系** — zh-TW, zh-CN, en-US, ja-JP
3. **Excel + Word 雙格式** — 從同一個 verify.md 產出，資料一致格式各取所需
4. **JPA/Hibernate 為主** — 產品專案大部分用 spring-boot-jpa，知識庫和 API 格式驗證要反映
5. **E2E 結果映射** — 外部映射檔 verify-map.json，步驟級別映射，無匹配退回 MPC
6. **產品識別** — projects/{id}.md 新增 product_id，指向 plugin 內建的 products/{name}.md
7. **Profile 選擇** — 簡單版：讀 E2E repo 的 profile-*.js 顯示選項，讓使用者選
8. **測試骨架品質** — 定位為 80% 完成度，TODO/FIXME 標記，試跑 + 人工 review 後才 commit

### 不包含

- SmartRobotE2ETest repo 本身的修改
- bug-workflow plugin 的修改
- Notion 同步機制的變更
- 新增語系翻譯（th-TH, vi-VN, id-ID, de-DE 留待後續）
