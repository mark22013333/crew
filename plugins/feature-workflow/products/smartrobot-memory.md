---
product: smartrobot
last_updated: 2026-05-15
---

# SmartRobot 產品級驗證記憶（Layer 3）

> 此文件存放跨專案通用的驗證經驗，由 plugin 維護者從各專案的 Layer 2 萃取。
> 載入順序：此文件（Layer 3）→ 專案 `.crew/verify-memory.md`（Layer 2；舊 `.claude/verify-memory.md` 僅 read fallback）→ 任務 `.spec/{slug}/.cache/verify-memory.md`（Layer 1）。完整 contract 見 `references/verify-memory.md`。

## 頁面操作記憶

（初始為空，由 Layer 2 升級填入）

> 時效性：所有記憶條目應含 `last_verified`（YYYY-MM-DD）。
> 載入時依時效分級：≤30 天 🟢 / 31-90 天 🟡 / >90 天 🔴（不採用，重新探索）。
> 詳見 plan-verify SKILL.md「2.5 載入驗證記憶 → 時效性檢查」段落。

## Selector 記憶

| 元素 | 有效 Selector | 無效（別再試） | 備註 | last_verified |
|------|--------------|---------------|------|--------------|

（初始為空，使用中自動累積）

## API 回傳格式記憶

> 初始引用 smartrobot.md 的 API 格式定義。
> 若實際回傳格式與文件定義不同，記錄在此，並附 `last_verified`。

## 截圖策略記憶

- 全站 modal 關閉: ESC×2（SweetAlert2 + Bootstrap Modal） — `last_verified: 2026-05-15`
- sidebar 收合後截圖更完整: 點擊 `.sidebar-toggle` — `last_verified: 2026-05-15`

## 踩坑紀錄

| 日期 | 情境 | 問題 | 解法 |
|------|------|------|------|

（踩坑紀錄為 advisory 性質，不受時效機制影響，永久保留）
