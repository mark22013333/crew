# plan-verify Phase: 驗證路由

本檔由 [`../SKILL.md`](../SKILL.md) Step 3 引用。目標不是「所有 AC 都用 Playwright 驗」，而是為每條 `AC-n` 選出**最可靠、可重現、可產 evidence** 的驗證方式。

## Verification Router

每條 AC 在執行前必須先分類成一種主要驗證方式：

| type | 適用情境 | 主要 evidence |
|---|---|---|
| `browser` | 使用者可見 UI 行為、互動、可及性、前端狀態 | screenshot / snapshot / trace |
| `api` | request / response contract、狀態碼、payload | request / response |
| `backend-test` | UI 無法可靠證明的服務層、資料隔離、交易、權限邏輯 | test command + test result |
| `database` | 必須直接驗證資料狀態，且已有安全的唯讀查詢路徑 | query + result |
| `manual` | 視覺品質、外部人工判斷、無可自動化 evidence | human steps |
| `skip` | Out of Scope、已接受取捨、不適用 | reason |

### 選擇原則

1. **證明力優先，不是工具偏好優先**：Playwright 是 preferred browser adapter，但不是所有 AC 的 preferred verifier。
2. **不要用 UI 證明 UI 看不出的事**：若修前修後在目前環境畫面相同，browser 驗證沒有判別力，改走 backend-test / API / database。
3. **優先沿用既有自動化資產**：若 `@code:` 指向的模組已有針對該邏輯的單元/整合測試，且能直接覆蓋 AC，可選 `backend-test`。
4. **一條 AC 一個主要 verifier**；可有 secondary cross-check，但結果判定以主要 verifier 為準，避免兩套 truth。
5. **驗證方式必須可說明原因**：任何非 browser 路由都要記錄 `reason`。

## 計畫輸出格式

驗證計畫至少要有：

```text
| AC | 驗收條件 | verifier | 前置條件 | evidence | 理由 |
|----|---------|----------|----------|----------|------|
| AC-1 | ... | browser | 已登入 | screenshot | UI 可直接觀察 |
| AC-2 | ... | backend-test | 測試 DB | junit xml | UI 無法區分多租戶資料隔離 |
```

## 路由來源

依序參考：

1. `plan.md` 的 AC、風險、Out of Scope、決策紀錄
2. `@code:` / `@sql:` 錨點指到的真實程式碼
3. 專案 `.crew/verify-memory.md`
4. product / adapter knowledge
5. 既有 E2E / unit / integration test 資產

文件敘述只能當線索，路由所依賴的 endpoint、測試命令、程式行為要回到實際程式碼或可執行資產確認。
