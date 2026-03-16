---
name: plan-verify
description: 透過 chrome-cdp 操作使用者已開啟的 Chrome 瀏覽器，逐條驗證 .spec/ 中的驗收條件，產出 verify.md 驗證報告。當使用者提到「plan-verify」、「驗證」、「verify」、「驗收」時觸發此 Skill。
---

# plan-verify — Chrome CDP 驗收驗證

連接使用者**已開啟的 Chrome 瀏覽器**（含登入態），透過 Chrome DevTools Protocol 逐條驗證驗收條件，產出 `.spec/{slug}/verify.md` 驗證報告與截圖。

對需要 SSO/VPN 登入的內部系統特別有價值 — 直接使用已登入的 Chrome session，無需另行驗證。

---

## 使用方式

```
/plan-verify                    # 完整驗證所有驗收條件
/plan-verify --manual           # 互動模式，每步驟等待確認
/plan-verify <URL>              # 指定目標頁面
/plan-verify --api-only         # 只驗證 API（不操作 UI，不需 Chrome）
/plan-verify --recheck          # 僅重新驗證上次失敗的項目
```

---

## CDP 工具路徑

```bash
CDP="node ~/.claude-company/company-marketplace/plugins/feature-workflow/scripts/cdp.mjs"
```

所有 CDP 操作均使用此路徑。以下文件中 `$CDP` 即指此完整指令。

---

## 前置條件

執行前**依序檢查**，任一失敗則停止並顯示對應指引：

| # | 項目 | 檢查方式 | 失敗處理 |
|---|------|---------|---------|
| 1 | cdp.mjs 存在 | `test -f ~/.claude-company/company-marketplace/plugins/feature-workflow/scripts/cdp.mjs` | 提示：`claudec plugin update feature-workflow@company-marketplace` |
| 2 | Node.js 22+ | `node --version`，解析主版本號 ≥ 22 | 提示：`請升級 Node.js 至 22 以上版本（https://nodejs.org/）` |
| 3 | Chrome remote debugging | `$CDP list`，檢查回傳是否包含 tab 清單 | 提示：`請在 Chrome 開啟 chrome://inspect/#remote-debugging 並啟用切換開關` |
| 4 | `--api-only` 模式 | 跳過第 3 項檢查 | 只需 curl 可用 |

---

## 流程

### 1. 定位活躍任務

與 `/plan` 相同邏輯：從 Git branch 或 `.spec/_index.md` 匹配活躍任務。

讀取 `.spec/{slug}/README.md` 取得 `type`（feature/bug）和元資訊。

### 2. 讀取驗收條件

根據任務類型讀取：

| 類型 | 檔案 | 區塊 |
|------|------|------|
| Feature | `.spec/{slug}/spec.md` | 「驗收條件」區塊（通常為 checkbox 清單） |
| Bug | `.spec/{slug}/fix.md` | 「驗證方式」區塊 |

若找不到驗收條件 → 提示使用者手動輸入驗收條件清單。

### 3. 建構驗證計畫

AI 分析每條驗收條件，將其分類並規劃驗證方式：

| 類型 | 工具 | 範例 |
|------|------|------|
| API | curl + Bash | 「可依日期範圍查詢」→ `curl GET /api/xxx?startDate=...&endDate=...` |
| UI 操作 | $CDP click/type/snap/shot | 「支援分頁」→ 點擊下一頁按鈕，確認表格更新 |
| UI 檢查 | $CDP snap → AI 分析 | 「表格顯示正確欄位」→ 讀取無障礙樹檢查欄位 |
| 資料驗證 | API + UI 交叉比對 | 「統計數據一致」→ API 回傳值與頁面顯示比對 |

讀取 `.spec/{slug}/arch.md` 推斷 API 路徑和頁面 URL（若有）。

展示計畫給使用者確認：

```
即將驗證 {N} 條驗收條件：

| # | 驗收條件 | 類型 | 驗證方式 |
|---|---------|------|---------|
| 1 | 可依日期範圍查詢 | API | GET /api/xxx |
| 2 | 支援分頁顯示 | UI | 點擊下一頁 |
| 3 | 支援匯出 Excel | UI | 點擊匯出按鈕 |

{--api-only: 將跳過 UI 類型驗證}
{--manual: 每步驟等待確認}

確認開始？[Y/n]
```

### 4. 連接 Chrome（非 --api-only 時）

```bash
$CDP list
```

從 tab 清單中智慧匹配目標頁面，優先順序：

1. 使用者透過參數指定的 URL
2. 從 `arch.md` 或 `spec.md` 推斷的頁面路徑（如 `/admin/xxx`）
3. 包含 `localhost` 的 tab

匹配邏輯：取 tab URL 與目標路徑的最佳匹配（部分路徑匹配即可）。

找不到 → 提示使用者在 Chrome 開啟目標頁面，然後重新 `$CDP list`。

記錄匹配到的 `target_id` 供後續操作。

### 5. 逐條驗證

依序對每條驗收條件執行驗證。

#### API 驗證

```bash
# 若需登入態（非 --api-only 且有 Chrome 連接），從 Chrome 取 cookie
$CDP eval {target} "document.cookie"

# 呼叫 API
curl -s "http://localhost:8080/api/xxx" -H "Cookie: {cookie}" | head -100
```

檢查：HTTP 狀態碼、回應格式、資料筆數、欄位完整性。

#### UI 驗證

```bash
# 步驟 1：了解頁面結構
$CDP snap {target}

# 步驟 2：操作（點擊、輸入等）
$CDP click {target} "{selector}"
$CDP type {target} "{text}"

# 步驟 3：操作後快照，確認結果
$CDP snap {target}

# 步驟 4：截圖存證
$CDP shot {target}
```

AI 分析 snap 輸出（無障礙樹）來判斷：
- 元素是否存在
- 內容是否正確
- 操作是否成功

#### `--manual` 模式

每個驗證步驟前後都詢問使用者確認：

```
[2/5] 驗證「支援分頁顯示」
  → 即將點擊下一頁按鈕：#nextPage
  確認執行？[Y/n/skip]
```

#### 記錄結果

每條記錄：

| 欄位 | 說明 |
|------|------|
| 狀態 | `PASS` / `FAIL` / `SKIP` / `MANUAL` |
| 證據 | API 回應摘要 / snap 關鍵節點 / 截圖路徑 |
| 失敗原因 | 僅 FAIL 時記錄 |

- `PASS`：驗證通過
- `FAIL`：驗證失敗（含原因）
- `SKIP`：`--api-only` 跳過 UI 驗證，或使用者手動跳過
- `MANUAL`：需人工確認的項目（如視覺效果）

### 6. 收集截圖

```bash
mkdir -p .spec/{slug}/screenshots
```

將驗證過程中的截圖複製到 `.spec/{slug}/screenshots/`：

```bash
# cdp.mjs 截圖預設輸出至 ~/.cache/cdp/ 或目前目錄
# 找到最新截圖並搬移
cp {screenshot_path} .spec/{slug}/screenshots/verify-{N}-{desc}.png
```

命名規則：`verify-{序號}-{簡述}.png`，如 `verify-1-query-result.png`。

### 7. 產出 verify.md

寫入 `.spec/{slug}/verify.md`：

```markdown
# 驗證報告

## 摘要

| 項目 | 值 |
|------|-----|
| 驗證日期 | {YYYY-MM-DD} |
| 環境 | {localhost:8080 或使用者指定} |
| 模式 | {完整 / api-only / manual / recheck} |

## 統計

| 狀態 | 數量 |
|------|------|
| ✅ PASS | {N} |
| ❌ FAIL | {N} |
| ⏭️ SKIP | {N} |
| 👤 MANUAL | {N} |

## 驗證結果

### [1] ✅ 可依日期範圍查詢
- **類型**：API
- **驗證**：`GET /api/xxx?startDate=2026-01-01&endDate=2026-03-16` → HTTP 200, 15 筆
- **截圖**：screenshots/verify-1-query-result.png

### [2] ❌ 支援匯出 Excel
- **類型**：UI
- **驗證**：點擊匯出按鈕 `#exportBtn`
- **失敗原因**：按鈕不存在（snap 中未找到匹配元素）
- **截圖**：screenshots/verify-2-export.png

### [3] ⏭️ 支援分頁顯示
- **類型**：UI
- **跳過原因**：--api-only 模式

### [4] 👤 報表視覺呈現正確
- **類型**：UI 檢查
- **說明**：需人工確認圖表渲染效果
- **截圖**：screenshots/verify-4-chart.png
```

### 8. 更新 .spec/

1. 更新 `README.md`：`status: 驗證中`
2. 在 `log.md` 追加紀錄：

```markdown
### [{日期}] 驗收驗證
- **模式**：{完整/api-only/manual/recheck}
- **結果**：✅ {N} / ❌ {N} / ⏭️ {N} / 👤 {N}
- **報告**：verify.md
```

### 9. 回傳結果

```
驗收驗證完成！

📋 報告：.spec/{slug}/verify.md
📸 截圖：.spec/{slug}/screenshots/ ({N} 張)
📊 統計：✅ {PASS} / ❌ {FAIL} / ⏭️ {SKIP} / 👤 {MANUAL}

{若有 FAIL}
⚠️  發現 {N} 個驗收條件未通過，建議修復後執行 /plan-verify --recheck

{若全部 PASS}
🎉 所有驗收條件通過！

後續可使用：
  • /plan-verify --recheck — 重新驗證失敗項目
  • /plan-review          — Agent Teams 程式碼審查
  • /plan-close           — 結案並同步 Notion
```

---

## --recheck 模式

讀取既有 `.spec/{slug}/verify.md`，解析其中 `❌ FAIL` 的項目：

1. 只重跑 FAIL 項目
2. 結果合併回**同一份** verify.md（覆蓋對應項目的狀態）
3. 更新統計區塊
4. 在 log.md 追加 recheck 紀錄

---

## 邊界情況

- **無驗收條件**：提示使用者手動輸入，或建議先執行 `/plan spec`
- **Chrome 未啟用 remote debugging**：顯示詳細啟用步驟（`chrome://inspect/#remote-debugging`）
- **Node.js 版本不足**：顯示升級指引
- **目標 tab 找不到**：列出所有可用 tab，請使用者選擇或在 Chrome 開啟目標頁面
- **CDP 操作失敗**（如 selector 不存在）：標記該條為 FAIL，記錄錯誤訊息，繼續下一條
- **--api-only 跳過 UI**：UI 類型標記為 SKIP，不影響其他驗證
- **截圖失敗**：記錄警告，不阻斷流程
- **verify.md 已存在**：詢問覆蓋或追加（--recheck 自動合併）
- **驗證過程中使用者中斷**：已完成的結果仍寫入 verify.md（部分報告）
