# plan-verify Phase: 逐條驗證執行

本檔由 [`../SKILL.md`](../SKILL.md) Step 5 引用。
詳細的 MCP 模式工具對照、Bash 模式 cdp.mjs、Selector Fallback 6 級、
stability 截圖、API+UI 交叉比對等驗證執行細節。

---

### 5. 逐條驗證

依序對 `plan.md`「驗收條件」節的每條 `AC-n` 執行 `route-verification.md` 選定的 verifier，結果沿用同一個 `AC-n` 編號。進入 scenario 前先依 `preconditions.md` 執行 precondition gate；前置不成立時記 `BLOCKED`，不要繼續把環境問題量成產品 FAIL。

**截圖穩定化**：每次截圖前，執行 `references/verify-stability.md` 定義的 6 步前置流程（ESC×2 → 關閉面板 → 回到頂部 → networkidle → 等動畫 → 截圖）。失敗時最多重試 3 次。

**元素定位策略**（嘗試順序）：

| 優先級 | 策略 | 範例 | 適用 |
|--------|------|------|------|
| 1 | 記憶 Selector | 驗證記憶中的「有效 Selector」 | 有記憶時 |
| 2 | 穩定 Selector（ID/name/class） | `#searchKeyword`, `input[name="code"]` | 通用 |
| 3 | 產品知識 Selector | products/{id}.md 的常用 Selector 表 | 產品模式 |
| 4 | Role + 翻譯文字 | `getByRole('link', { name: '{i18n}' })` | 有 i18n 對照時 |
| 5 | CSS 屬性 Selector | `a[href*="/push/stat"]` | 連結類 |
| 6 | 直接 URL 導航 | `browser_navigate({ url })` | 最終 fallback |

每次 fallback 觸發時，記錄到驗證記憶（見步驟 5.5）。

多語系定位指引見 `references/verify-i18n.md`。

#### API 驗證

**MCP 模式：**
```
# 若需登入態，從 Chrome 取 cookie
evaluate_script({ expression: "document.cookie" })

# 呼叫 API（仍用 curl）
curl -s "http://localhost:8080/api/xxx" -H "Cookie: {cookie}" | head -100
```

**Bash 模式：**
```bash
$CDP eval {target} "document.cookie"
curl -s "http://localhost:8080/api/xxx" -H "Cookie: {cookie}" | head -100
```

檢查：HTTP 狀態碼、回應格式、資料筆數、欄位完整性。

#### Backend test 驗證

當 Verification Router 選擇 `backend-test`：

1. 從 plan.md 錨點與實際 build 設定確認可執行的測試命令，不從文件猜 command。
2. 優先執行能直接覆蓋該 AC 的單元／整合測試；不要為了「看起來像 E2E」強迫改走瀏覽器。
3. 保存 command、exit code、失敗測試名稱與關鍵輸出到 evidence。
4. build tool / fixture / test DB 不可用 → `BLOCKED`；測試確實執行且 assertion 失敗 → `FAIL`。

Evidence 建議：

```text
.spec/{slug}/evidence/verify-AC-{n}-backend-test.txt
```

#### Database 驗證

只有在 Verification Router 判定資料狀態本身就是最可靠 evidence，且有安全的 DB capability 時使用：

- 預設唯讀。
- query 必須能從 schema / code anchor 證明，不猜 table / column。
- DB capability 不可用 → `BLOCKED` 或改走已規劃的 secondary verifier。
- 不因方便而在 production / shared DB 建立破壞性 fixture。

#### 記錄 Evidence 檔案（API 驗證時必做）

每次 curl 呼叫完成後，**立即**將完整請求與回應寫入 evidence 目錄：

```bash
mkdir -p .spec/{slug}/evidence

# 寫入完整請求（含 method、URL、headers）
cat > .spec/{slug}/evidence/verify-{AC 編號}-request.txt << 'EOF'
GET http://localhost:8080/ap/pushTagQuery/list?startDate=2026-01-01&endDate=2026-03-18&pageNum=1&pageSize=20
Headers:
  Cookie: JSESSIONID=abc123def456
  Content-Type: application/json
EOF

# 寫入完整回應 body（JSON 用 .json，其餘用 .txt）
curl -s "..." | python3 -m json.tool > .spec/{slug}/evidence/verify-{AC 編號}-response.json
# 若非 JSON：
curl -s "..." > .spec/{slug}/evidence/verify-{AC 編號}-response.txt
```

此檔案為**原始內容、不遮蔽**，供內部技術驗證用。Word 報告中引用時會自動遮蔽敏感資訊（見步驟 10.3）。

#### 後台頁面截圖（API 有對應後台頁面時）

若驗證計畫中標記為「後台 📸」的 API 項目，curl 驗證完成後**額外**執行：

**MCP 模式：**
```
# 開啟對應後台頁面
browser_navigate({ url: "http://localhost:8080/admin/xxx" })

# 等待頁面載入
browser_wait_for({ text: "{關鍵文字}" })

# 截圖存證
browser_take_screenshot()
```

**Bash 模式：**
```bash
$CDP navigate {target} "http://localhost:8080/admin/xxx"
$CDP snap {target}
$CDP shot {target}
```

截圖命名：`verify-{AC 編號}-admin-{desc}.png`，存入 `screenshots/`。

#### UI 驗證

**MCP 模式：**
```
# 步驟 1：了解頁面結構
take_snapshot()

# 步驟 2：操作（點擊、輸入等）
click({ selector: "{selector}" })
type_text({ text: "{text}" })
# 或批次填入表單
fill({ selector: "{selector}", value: "{value}" })
fill_form({ fields: [{ selector: "...", value: "..." }, ...] })

# 步驟 3：等待載入完成（MCP 獨有）
wait_for({ text: "搜尋結果" })

# 步驟 4：操作後快照，確認結果
take_snapshot()

# 步驟 5：截圖存證
take_screenshot()

# 額外：偵測前端錯誤（MCP 獨有）
list_console_messages()
```

**Bash 模式：**
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

AI 分析 snapshot 輸出（無障礙樹）來判斷：
- 元素是否存在
- 內容是否正確
- 操作是否成功

#### `--manual` 模式

每個驗證步驟前後都詢問使用者確認：

```
[2/5] 驗證 AC-2「支援分頁顯示」
  → 即將點擊下一頁按鈕：#nextPage
  確認執行？[Y/n/skip]
```

#### 記錄結果

每條記錄：

| 欄位 | 說明 |
|------|------|
| 狀態 | `PASS` / `WARN` / `FAIL` / `BLOCKED` / `SKIP` / `MANUAL` |
| 證據 | API 回應摘要 / snap 關鍵節點 / 截圖路徑 |
| 失敗／阻擋原因 | FAIL / BLOCKED 時記錄；BLOCKED 要指出哪個 precondition 不成立 |
| 操作敘述 | 人話描述的操作步驟清單（用於 Word 報告） |
| evidence 檔案 | API 類型時記錄：`evidence/verify-{AC 編號}-request.txt`、`evidence/verify-{AC 編號}-response.json` |

- `PASS`：驗證通過
- `WARN`：通過但有疑慮（環境差異、selector 不穩定）
- `FAIL`：前置條件成立，受測功能明確不符合 AC
- `BLOCKED`：登入、fixture、profile、依賴服務、測試 DB 等前置不成立，沒有資格判定產品功能
- `SKIP`：`--api-only` 跳過 UI 驗證，或使用者手動跳過
- `MANUAL`：需人工確認的項目（如視覺效果）

#### 操作敘述記錄

每條驗證項目執行時，AI **同步**產生一份「人話操作步驟」。此敘述：
- 用非技術人員可讀的語言撰寫
- 描述「做了什麼」而非「用了什麼指令」
- 包含預期結果與實際結果的比對

此資料暫存於 AI 工作記憶中，寫入 `.spec/{slug}/.cache/verify.md` 的 `<!-- human_steps -->` 註解區塊，
供可選指令 `/plan-verify --word` 產出 Word 報告時使用（不在主流程）。

**翻譯對照表**：

| Playwright 操作 | 人話敘述 |
|----------------|---------|
| `browser_navigate({ url })` | 開啟「{頁面名稱}」頁面 |
| `browser_click({ element })` | 點擊「{元素描述}」按鈕/連結 |
| `browser_type({ element, text })` | 在「{欄位名稱}」欄位輸入 {值} |
| `browser_fill_form({ fields })` | 依序填入表單：{欄位1}={值1}、{欄位2}={值2} |
| `browser_select_option({ element, value })` | 在「{欄位名稱}」下拉選單選擇「{選項}」 |
| `browser_snapshot()` | 觀察頁面內容 |
| `browser_take_screenshot()` | 截取畫面存證 |
| `browser_wait_for({ text })` | 等待頁面顯示「{文字}」 |
| `browser_press_key({ key })` | 按下 {按鍵} 鍵 |
| `curl GET /api/xxx?params` | 透過系統 API 查詢{功能描述}（參數：{參數說明}） |
| `curl POST /api/xxx` | 透過系統 API 新增{功能描述} |
| HTTP 狀態碼回傳 | 系統回應{狀態描述} |

**翻譯原則**：
1. 不出現程式碼（selector、URL path、HTTP method）
2. 使用頁面上的實際文字（「查詢」不是 `#queryBtn`）
3. 合併連續操作（`click` → `wait_for` → `snapshot` → 「點擊 XX 按鈕，等待頁面載入完成」）
4. 結果用白話（「HTTP 200, 15 rows」→「系統成功回傳 15 筆資料」）
5. 省略技術診斷操作（`evaluate_script`、`list_console_messages` 不納入）
6. `<!-- evidence -->` 區塊不翻譯，原樣保留（供 Word 報告「測試紀錄」段落使用）
