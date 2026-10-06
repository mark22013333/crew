# 範例：`.spec/{slug}/.cache/verify.md` 驗證報告

以下展示 `/plan-verify` 的理想產出格式，涵蓋 PASS / WARN / FAIL / BLOCKED / SKIP / MANUAL。
報告本身是 `.cache/` 下的一次性暫存，結論（PASS/WARN/FAIL、Health Score）另由 `crew-state.py result --kind verify` 寫進 `state.json`。

---

# 驗證報告

## 摘要

| 項目 | 值 |
|------|-----|
| 驗證日期 | 2026-03-18 |
| 環境 | localhost:8080 |
| 模式 | 完整 |
| 驗證工具 | Playwright MCP |

## 統計

| 狀態 | 數量 |
|------|------|
| ✅ PASS | 3 |
| ❌ FAIL | 1 |
| 🚧 BLOCKED | 1 |
| ⏭️ SKIP | 1 |
| 👤 MANUAL | 1 |

## 驗證結果

### [1] ✅ 可依日期範圍查詢推播統計

- **類型**：API
- **驗證**：`GET /ap/pushTagQuery/list?startDate=2026-01-01&endDate=2026-03-18&pageNum=1&pageSize=20`
- **結果**：HTTP 200, 回傳 15 筆資料，格式正確
- **證據**：
  ```json
  {
    "code": "0000",
    "data": { "list": [...], "total": 15, "pageNum": 1 }
  }
  ```
- **Evidence**：evidence/verify-1-request.txt, evidence/verify-1-response.json
<!-- human_steps
- 操作：透過系統 API 查詢推播統計（日期範圍：2026-01-01 至 2026-03-18，分頁：第 1 頁，每頁 20 筆）
- 操作：檢查回傳資料格式與筆數
- 預期：系統回傳查詢結果，資料筆數大於 0，格式正確
- 實際：系統成功回傳 15 筆資料，包含推播代碼、發送數、開封數等欄位，格式正確
-->
<!-- evidence
request: |
  GET http://localhost:8080/ap/pushTagQuery/list?startDate=2026-01-01&endDate=2026-03-18&pageNum=1&pageSize=20
  Cookie: JSESSIONID=abc123def456
  Content-Type: application/json
response_status: 200
response_file: evidence/verify-1-response.json
response_lines: 42
-->

### [2] ✅ 日期範圍超過 90 天回傳錯誤

- **類型**：API
- **驗證**：`GET /ap/pushTagQuery/list?startDate=2025-01-01&endDate=2026-03-18`
- **結果**：HTTP 400, 回傳 `DATE_RANGE_EXCEEDED`
- **證據**：
  ```json
  { "code": "DATE_RANGE_EXCEEDED", "message": "查詢區間不可超過 90 天" }
  ```
- **Evidence**：evidence/verify-2-request.txt, evidence/verify-2-response.json
<!-- human_steps
- 操作：透過系統 API 以超過 90 天的日期範圍進行查詢（2025-01-01 至 2026-03-18）
- 預期：系統回傳錯誤訊息，說明查詢區間不可超過 90 天
- 實際：系統正確回傳「查詢區間不可超過 90 天」錯誤訊息
-->
<!-- evidence
request: |
  GET http://localhost:8080/ap/pushTagQuery/list?startDate=2025-01-01&endDate=2026-03-18
  Cookie: JSESSIONID=abc123def456
response_status: 400
response_file: evidence/verify-2-response.json
response_lines: 3
-->

### [3] ✅ 支援分頁顯示

- **類型**：UI
- **驗證**：
  1. `take_snapshot()` — 確認表格顯示 20 筆
  2. `click({ selector: ".pagination .next" })` — 點擊下一頁
  3. `wait_for({ text: "第 2 頁" })` — 等待頁面更新
  4. `take_snapshot()` — 確認表格資料已更新
- **證據**：第一頁顯示 id 1-20，第二頁顯示 id 21-40
- **截圖**：screenshots/verify-3-pagination.png
<!-- human_steps
- 操作：開啟推播統計查詢頁面，確認表格顯示 20 筆資料
- 操作：點擊分頁列的「下一頁」按鈕
- 操作：等待頁面載入完成，確認表格已切換至第 2 頁
- 預期：點擊下一頁後，表格資料更新為第 2 頁內容
- 實際：表格成功切換，第一頁顯示資料 1-20，第二頁顯示資料 21-40
-->

### [4] ❌ 匯出 Excel 功能

- **類型**：UI
- **驗證**：
  1. `take_snapshot()` — 尋找匯出按鈕
  2. 未找到匹配的匯出按鈕元素
- **失敗原因**：snap 中未找到匯出按鈕（`#exportBtn` 不存在於無障礙樹中）。頁面上可能使用了不同的 selector 或按鈕尚未實作。
- **預期**：頁面應有「匯出 Excel」按鈕，點擊後下載 .xlsx 檔案
- **實際**：無障礙樹中無任何包含「匯出」文字的可點擊元素
- **截圖**：screenshots/verify-4-export-missing.png
<!-- human_steps
- 操作：在推播統計頁面尋找「匯出 Excel」按鈕
- 預期：頁面應有「匯出 Excel」按鈕，點擊後下載 .xlsx 檔案
- 實際：頁面上未找到「匯出」相關按鈕，功能尚未實作
-->

### [5] ⏭️ 標籤模糊搜尋即時反應

- **類型**：UI
- **跳過原因**：前端頁面尚未實作搜尋框（spec 中 `FRONTEND_REQUIRED: false`，本期僅做 API）

### [6] 👤 統計數據與 LINE 後台一致

- **類型**：資料驗證
- **說明**：需人工登入 LINE Official Account Manager 比對推播統計數據
- **手動驗證步驟**：
  1. 登入 LINE Official Account Manager (manager.line.biz)
  2. 進入「分析」>「訊息」
  3. 選擇與 API 相同的日期範圍（2026-03-01 ~ 2026-03-18）
  4. 比對「發送數」、「開封數」欄位是否與系統查詢結果一致
  5. 允許 ±1% 的誤差（LINE 後台統計有延遲）
- **截圖**：screenshots/verify-6-manual-guide.png

### [7] 🚧 後台登入前置條件未成立

- **類型**：UI 前置條件
- **阻擋原因**：登入 helper 執行後仍無法存取受保護頁面；目前無法判定 AC 功能本身是否正確
- **證據**：受保護頁面回到登入流程，未取得必要資料表
- **處理**：修正 profile / credential / session 後重新執行本項，不得把此結果記成產品 FAIL

---

# 範例：Word 驗收報告結構

以下展示 `/plan-verify` 產出 Word 報告時的 Markdown 原始碼，作為報告產出引擎（minimax-docx 或 python-docx）的輸入。

---

# 範例專案 Push API(微服務)-ORG01P2401

## 推播標籤查詢統計 — 驗收報告

| 項目 | 值 |
|------|-----|
| 驗證日期 | 2026-03-18 |
| 版本號 | v1.0 |
| 承辦單位 | 英特內軟體股份有限公司 |

## 簽核

| 角色 | 姓名 | 簽章 | 日期 |
|------|------|------|------|
| 製作人 | Mark Cheng | | |
| 審核人 | | | |
| 客戶確認 | | | |

## 測試環境

| 項目 | 說明 |
|------|------|
| 測試 URL | http://localhost:8080 |
| 瀏覽器 | Chromium |
| 測試帳號角色 | 系統管理員 |
| 測試資料說明 | 使用測試環境既有推播紀錄 |
| 前置條件 | 已登入後台管理系統 |

## 驗收摘要

| 狀態 | 數量 |
|------|------|
| 通過 | 3 |
| 未通過 | 1 |
| 前置阻擋 | 1 |
| 略過 | 1 |
| 待人工確認 | 1 |

**結論**：共 7 項驗收條件，3 項通過、1 項未通過、1 項前置阻擋、1 項待人工確認（1 項因範圍限制略過）；FAIL 需修正，BLOCKED 則先排除環境／登入前置條件再重新驗證。

## 驗收明細

### 驗收項目 1：可依日期範圍查詢推播統計

**結果：通過** ✅

**操作步驟**：
1. 透過系統 API 查詢推播統計（日期範圍：2026-01-01 至 2026-03-18，分頁：第 1 頁，每頁 20 筆）
2. 檢查回傳資料格式與筆數

**預期結果**：系統回傳查詢結果，資料筆數大於 0，格式正確

**實際結果**：系統成功回傳 15 筆資料，包含推播代碼、發送數、開封數等欄位，格式正確

**測試紀錄**：

請求：

```
GET http://localhost:8080/ap/pushTagQuery/list
    ?startDate=2026-01-01
    &endDate=2026-03-18
    &pageNum=1&pageSize=20
Headers:
  Cookie: JSES****f456
  Content-Type: application/json
```

回應（HTTP 200）：

```json
{
  "code": "0000",
  "data": {
    "list": [
      {"pushCode": "P001", "sendCount": 5000, "openCount": 1230},
      {"pushCode": "P002", "sendCount": 3200, "openCount": 890},
      {"pushCode": "P003", "sendCount": 1800, "openCount": 520},
      {"pushCode": "P004", "sendCount": 1500, "openCount": 410},
      {"pushCode": "P005", "sendCount": 1200, "openCount": 380},

      ... （省略 5 筆，共 15 筆）

      {"pushCode": "P011", "sendCount": 600, "openCount": 180},
      {"pushCode": "P012", "sendCount": 450, "openCount": 120},
      {"pushCode": "P013", "sendCount": 380, "openCount": 95},
      {"pushCode": "P014", "sendCount": 210, "openCount": 58},
      {"pushCode": "P015", "sendCount": 100, "openCount": 22}
    ],
    "total": 15
  }
}
```

> 完整回應請見：evidence/verify-1-response.json

### 驗收項目 2：日期範圍超過 90 天回傳錯誤

**結果：通過** ✅

**操作步驟**：
1. 透過系統 API 以超過 90 天的日期範圍進行查詢（2025-01-01 至 2026-03-18）
2. 檢查系統是否正確攔截

**預期結果**：系統回傳錯誤訊息，說明查詢區間不可超過 90 天

**實際結果**：系統正確回傳「查詢區間不可超過 90 天」錯誤訊息

**測試紀錄**：

請求：

```
GET http://localhost:8080/ap/pushTagQuery/list
    ?startDate=2025-01-01
    &endDate=2026-03-18
Headers:
  Cookie: JSES****f456
```

回應（HTTP 400）：

```json
{ "code": "DATE_RANGE_EXCEEDED", "message": "查詢區間不可超過 90 天" }
```

### 驗收項目 3：支援分頁顯示

**結果：通過** ✅

**操作步驟**：
1. 開啟推播統計查詢頁面，確認表格顯示 20 筆資料
2. 點擊分頁列的「下一頁」按鈕
3. 等待頁面載入完成，確認表格已切換至第 2 頁

**預期結果**：點擊下一頁後，表格資料更新為第 2 頁內容

**實際結果**：表格成功切換，第一頁顯示資料 1-20，第二頁顯示資料 21-40

**截圖**：
![分頁功能](screenshots/verify-3-pagination.png)

### 驗收項目 4：匯出 Excel 功能

**結果：未通過** ❌

**操作步驟**：
1. 在推播統計頁面尋找「匯出 Excel」按鈕

**預期結果**：頁面應有「匯出 Excel」按鈕，點擊後下載 .xlsx 檔案

**實際結果**：頁面上未找到「匯出」相關按鈕，功能尚未實作

**測試紀錄**：（UI 驗證，無 API 呼叫）

**截圖**：
![匯出功能缺失](screenshots/verify-4-export-missing.png)

### 驗收項目 5：標籤模糊搜尋即時反應

**結果：略過** ⏭️

**略過原因**：本期僅驗證 API 功能，前端頁面尚未實作搜尋框

### 驗收項目 6：統計數據與 LINE 後台一致

**結果：待人工確認** 🔍

**說明**：此項目需人工登入外部系統比對數據，無法自動化驗證。

**手動驗證步驟**：
1. 登入 LINE Official Account Manager (manager.line.biz)
2. 進入「分析」>「訊息」
3. 選擇與系統相同的日期範圍（2026-03-01 至 2026-03-18）
4. 比對「發送數」、「開封數」欄位是否一致（允許 ±1% 誤差）

## 待處理事項

| # | 驗收條件 | 狀態 | 建議處理方式 |
|---|---------|------|------------|
| 4 | 匯出 Excel 功能 | 未通過 | 開發完成後重新驗證 |
| 6 | 統計數據與 LINE 後台一致 | 待人工確認 | 請相關人員手動比對數據 |
| 7 | 後台登入前置條件未成立 | 前置阻擋 | 修正 profile / credential / session 後重新驗證 |

## 附錄

### 版本紀錄

| 日期 | 版本 | 說明 |
|------|------|------|
| 2026-03-18 | v1.0 | 初次驗收 |

### 參考文件

- 規劃文件（目標與範圍／驗收條件／決策紀錄）：.spec/push-tag-query/plan.md
- 部署 SQL（表結構事實來源）：.spec/push-tag-query/deploy.sql
- 驗證技術紀錄：.spec/push-tag-query/.cache/verify.md
- API 測試原始記錄：.spec/push-tag-query/evidence/
