---
name: plan-verify
description: 透過 browser/API/E2E capability 逐條驗證 plan.md 的 AC-n 驗收條件，摘要一行進 plan.md、明細暫存 .cache/，可選 --deep 查 console/network。當使用者提到 /plan-verify、「.spec 驗收條件驗證」、「瀏覽器驗收 spec」時觸發此 Skill。
argument-hint: "[<URL>] [--deep|--manual|--api-only|--recheck|--e2e]"
---

# plan-verify — 驗收條件驗證

逐條驗證 `.spec/{slug}/plan.md`「驗收條件」節的 `AC-n`。先透過 Verification Router 為每條 AC 選擇 browser / API / backend-test / database / manual 等最可靠 verifier；UI 驗證再依 Host Capability Contract 選擇 browser adapter（preferred: Playwright）。也支援 E2E 與 local CDP fallback；產出 Health Score、evidence 與截圖。

`--deep` 可在 chrome-devtools capability 可用時追加 console / network 除錯分析。

> **產物落點（三層，別搞混）**
>
> | 產物 | 位置 | 進版控？ |
> |------|------|---------|
> | 逐條結果全文 | 對話輸出 ＋ `.spec/{slug}/.cache/verify.md`（一次性暫存，供 Word／Excel 報告消費） | ❌ gitignore |
> | 一行摘要 | `plan.md`「檢查報告摘要」節 | ✅ 隨 `/plan-close` 進版控 |
> | 機器可讀結果 | `state.json` 的 `results.verify`（`crew-state.py result`） | ✅ |
> | 截圖／evidence | `.spec/{slug}/screenshots/`、`evidence/` | ❌ gitignore（binary 不進 context） |
>
> `.cache/` 是**暫存**：內容隨時可刪、不可被任何 skill 當成事實來源引用（唯一消費者是可選的報告產出指令）。

---

## 使用方式

```
/plan-verify                    # 完整驗證所有驗收條件（Playwright）
/plan-verify --deep             # + chrome-devtools 查 console/network
/plan-verify --manual           # 互動模式，每步驟等待確認
/plan-verify <URL>              # 指定目標頁面
/plan-verify --api-only         # 只驗證 API（不操作 UI，不需瀏覽器）
/plan-verify --recheck          # 僅重新驗證上次失敗的項目
/plan-verify --e2e              # E2E Runner 模式（優先讀 portable e2e.* contract）
```

**Word／Excel 報告已移出主流程**，改為驗證完成後的獨立可選指令（見『可選指令：Word／Excel 驗收報告』一節）：

```
/plan-verify --word             # 只產 Word 報告（讀 .cache/verify.md，不重跑驗證）
/plan-verify --excel            # 只產 Excel 報告
/plan-verify --word --excel     # 兩份都產
```

---

## 前置條件

### Browser capability（UI 驗證時需要）

Playwright 是 **preferred browser adapter**，不是 CREW workflow 的 Host-specific hard prerequisite。依 `../../references/host-capabilities.md` 使用 `tool_probe(tool_kind=browser)` 判斷目前 session 可用能力；Playwright 不可用時可退到 chrome-devtools 或 plugin 內建 local CDP adapter。

Host-specific 安裝方式與 fallback 見 `../../references/mcp-install.md`。不要在本 Skill 內硬編碼某一家 Host 的 MCP CLI。

### chrome-devtools capability（選配，--deep 除錯增強）

`--deep` 只有在 chrome-devtools capability 可呼叫時追加 console/network/performance 分析；不可用時只略過 deep enhancement，不影響標準 verify。

---

## 紀律護欄

> 紀律護欄：`../../references/discipline-preamble.md`（通用紀律）＋ `../../references/anti-rationalizations.md`「plan-verify 專用」＋ `../../references/boundaries.md`「plan-verify」段；斷點保險改為**進度即寫 `state.json`**（每驗完一條 `AC-n` 就跑 `crew-state.py unit`）；有「可以跳過」「應該夠了」的衝動時，停下查表確認是否為已知偏離模式。

---

## 前置檢查流程

執行前先解析 plugin root，再依模式決定 adapter：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
[ -n "$CREW_PLUGIN_ROOT" ] || {
  echo "無法解析 plugin root；請確認 Host adapter 提供 plugin_root capability"
  exit 1
}
```

1. `--api-only`
   → 跳過 browser probe，只需 API/curl 能力。

2. 一般 UI verify
   → `tool_probe(tool_kind=browser, preferred_names=[playwright])`
   → 可用：使用 Playwright adapter。

3. Playwright 不可用
   → `tool_probe(tool_kind=browser, preferred_names=[chrome-devtools])`
   → 可用：使用 chrome-devtools adapter。

4. 兩種 browser tool 都不可用
   → 檢查 `node --version` 是否 ≥ 22、`$CREW_PLUGIN_ROOT/scripts/cdp.mjs` 是否可讀，以及本機 Chrome 是否開啟 remote debugging。
   → 條件成立：使用 local CDP adapter。
   → 條件不成立：browser verification unavailable；依 `../../references/mcp-install.md` 顯示目前 Host 適用的安裝/整合指引，不要臆造另一家 Host CLI。

   `--deep` 額外 probe chrome-devtools：有則追加 console/network/performance；沒有則略過 deep enhancement 並提示。

5. Word 報告工具偵測（**僅 `--word` 時執行**；決定 report_engine，詳見 phases/word-report.md step 10.0c）
   → 檢查 dotnet --version 是否 ≥ 8.0
     → 有 → 檢查 MiniMaxAIDocx.Core.csproj 是否存在
              （$MinimaxCorePath env var override 優先；其他 Host-specific fallback 必須明確標成 adapter compatibility）
       → 有 → report_engine = minimax-docx
       → 沒有 → report_engine = minimax-skills-missing
     → 沒有 → 檢查 python3 -c "import docx" 是否成功
       → 有 → report_engine = python-docx
       → 沒有 → report_engine = python-docx-pending
   此結果只在 `--word` 模式使用；主流程不偵測、不提示

偵測完成後顯示摘要：

```
🔧 驗證工具：{Playwright / chrome-devtools / local CDP / API-only}
🔍 除錯工具：{chrome-devtools（--deep 可用） / unavailable}
{📄 報告工具：{minimax-docx / python-docx / python-docx（需安裝）} ← 僅 --word 模式顯示}
```

報告工具偵測結果說明：
- `minimax-docx`：.NET 已安裝，可產出專業排版報告
- `python-docx`：.NET 未安裝，python-docx 已就緒，可產出基礎排版報告
- `python-docx（需安裝）`：兩者皆未安裝，到 step 10 時引導安裝

> **前置檢查**：參照 plugin 根目錄 `references/prerequisites.md`（相對 SKILL.md 為 `../../references/`）檢查專案指令是否存在。

---

## 流程

### 1. 定位活躍任務

參照 plugin 根目錄 `references/plan-common.md`（相對 SKILL.md 為 `../../references/`）的「定位活躍任務」（`crew-state.py list`），流程位置一律以 `state.json` 為準。

`type`（feature/bug）與任務名稱從 `.spec/{slug}/plan.md` 的 frontmatter 讀取。

### 1.5 產品偵測

讀取 `projects/{repo-id}.md` 的 `product_id` 欄位（見 plugin 根目錄 `references/plan-common.md`，相對 SKILL.md 為 `../../references/`，第 4 層）。

Resolution precedence：
1. 專案 repo `.crew/products/{product_id}.md`
2. plugin `products/{product_id}.md`
3. 都不存在 → 通用模式

產品級 memory 亦採 project-local 優先：`.crew/products/{product_id}-memory.md` → plugin `products/{product_id}-memory.md`。

- **有 product_id 且找到 knowledge** → 🟢 產品模式，注入頁面導航、Selector、i18n、Recipe、API 格式與產品記憶。
- **有 product_id 但找不到 knowledge** → 🟡 WARN 後降為通用模式；不得猜私有產品細節。
- **無 product_id** → 🔵 通用模式。

公司／客戶私有知識優先留在 project-local `.crew/products/`；公開 plugin bundle 不要求承載私有路由、帳密、內部 repo 或一次性測試資料。

### 2. 讀取驗收條件（`AC-n`）

讀 `.spec/{slug}/plan.md`「驗收條件」節（`<!-- crew:ac owner=spec -->`）的條目：

```text
- [ ] AC-1 可依日期範圍查詢推播紀錄
- [ ] AC-2 列表支援分頁，每頁上限 100 筆
```

- **編號 `AC-n` 是 join key**，後續所有輸出（逐條結果、摘要行、`state.json`、截圖檔名）一律沿用同一個編號，🔴 不要自己重新編號。
- 同時讀「已知取捨與風險」節：列為 Out of Scope 或已接受的取捨，對應項目標 `⏭️ SKIP` 並註明理由，不要報成 FAIL。
- 決策紀錄 `D-n` 提供「為什麼這樣做」，判斷實際行為是刻意還是缺陷時用。
- 🔴 plan.md 的 checkbox **不由本 skill 勾選**（那是規格的狀態，不是驗證結果）；驗證結果寫在摘要行與 `state.json`。

「驗收條件」節為空（尚未跑 `/plan spec`）→ 提示先執行 `/plan spec`，或請使用者當場口述條件（此時在回報中標「本次驗收條件未進 plan.md，下次無法比對」）。

### 2.5 載入驗證記憶

完整 storage / precedence / migration contract 見 `../../references/verify-memory.md`。

依序載入，後者覆蓋前者：

1. **Layer 3 產品級記憶**
   → project-local `.crew/products/{product_id}-memory.md`
   → 若不存在，再讀 plugin `products/{product_id}-memory.md`
2. **Layer 2 專案級記憶**
   → canonical：專案 repo `.crew/verify-memory.md`
   → legacy read fallback：只有 canonical 不存在時才讀 `.claude/verify-memory.md`
   → **新寫入一律寫 canonical，不再寫 legacy path**
3. **Layer 1 任務級記憶**
   → `.spec/{slug}/.cache/verify-memory.md`（gitignore 暫存）

#### 時效性檢查（last_verified）

每筆記憶條目應包含 `last_verified`（YYYY-MM-DD）：

| 距今 | 狀態 | 處理 |
|------|------|------|
| ≤ 30 天 | 🟢 新鮮 | 直接使用 |
| 31-90 天 | 🟡 需確認 | 使用但標示；仍有效時刷新日期 |
| > 90 天 | 🔴 過期 | 不使用舊值，重新探索 |
| 無欄位 | 🟡 需確認 | 同 31-90 天 |

- Selector 記憶：優先有效 selector，過期值不採用。
- 頁面操作/等待策略：可覆蓋預設策略，但過期需重新探索。
- 踩坑紀錄：advisory，永久保留。
- Shared memory 不得寫 Cookie、Token、密碼或一次性測試資料。

### 3. 建構驗證計畫

> 📄 **先讀全文**：[`phases/route-verification.md`](./phases/route-verification.md)
> 每條 AC 先選「最有證明力的 verifier」，不是看到驗收就一律丟給 Playwright。

AI 分析每條驗收條件，先分類成 browser / api / backend-test / database / manual / skip，再規劃驗證方式：

**MCP 模式工具對照：**

| 類型 | MCP 工具 | 範例 |
|------|---------|------|
| API | curl + Bash | 「可依日期範圍查詢」→ `curl GET /api/xxx?startDate=...&endDate=...` |
| UI 操作 | `browser_click` / `browser_type` / `browser_fill_form` / `browser_snapshot` / `browser_take_screenshot` | 「支援分頁」→ 點擊下一頁按鈕，確認表格更新 |
| UI 檢查 | `browser_snapshot` → AI 分析 | 「表格顯示正確欄位」→ 讀取無障礙樹檢查欄位 |
| 等待非同步 | `browser_wait_for` | 「搜尋結果載入」→ 等待文字出現 |
| 表單填寫 | `browser_fill_form` | 「表單驗證」→ 批次填入所有欄位 |
| 前端錯誤 | `browser_console_messages` | 「頁面無 JS 錯誤」→ 檢查 console |
| 資料驗證 | API + UI 交叉比對 | 「統計數據一致」→ API 回傳值與頁面顯示比對 |

> 上表工具名為 playwright plugin 提供之短名，實際完整工具名前綴為 `mcp__plugin_playwright_playwright__`（如 `mcp__plugin_playwright_playwright__browser_click`）。

**Bash 模式工具對照：**（Playwright MCP、chrome-devtools-mcp 皆未安裝時的退回方案，見前置檢查流程）

> `$CDP` 是本文所有 Bash 範例對 plugin 內建 `scripts/cdp.mjs` 的別名，使用前需先設定：
> ```bash
> CDP="node ${CREW_PLUGIN_ROOT}/scripts/cdp.mjs"
> ```
> `CREW_PLUGIN_ROOT` 由 `plugin_root` capability 解析；不得猜 Host marketplace/cache path。需 Node.js 22+。

| 類型 | 工具 | 範例 |
|------|------|------|
| API | curl + Bash | 同 MCP 模式 |
| UI 操作 | `$CDP click` / `$CDP type` / `$CDP snap` / `$CDP shot` | 同上 |
| UI 檢查 | `$CDP snap` → AI 分析 | 同上 |
| 資料驗證 | API + UI 交叉比對 | 同上 |

API 路徑與頁面 URL 從 plan.md「指路」節的錨點（`@code:`）**指向的程式碼本身**讀取（Controller 的 `@RequestMapping`、路由設定），不從文件敘述推斷 —— 文件會過期，程式碼不會。

**產品模式增強**：有 product_id 時，驗證計畫建構可參考：
- 頁面導航地圖 → 精確的 URL 路徑和選單路徑
- 常用 Selector → 優先使用已知穩定的 selector
- i18n 對照表 → 用翻譯文字定位元素（見 plugin 根目錄 `references/verify-i18n.md`，相對 SKILL.md 為 `../../references/`）
- 特殊操作 Recipe → CKEditor、SweetAlert2 等元件的操作方式
- API 格式 → 精確驗證回傳格式（如 Spring Page 的 content/totalElements/size/number）

### 3.5 前置條件 Gate

> 📄 **執行前必讀全文**：[`phases/preconditions.md`](./phases/preconditions.md)

每個 scenario 在驗 AC 前先確認登入、fixture、必要服務、profile 與 cleanup/safety 等前置條件。前置不成立時標 `BLOCKED`，**不得誤報產品 FAIL**。

展示計畫給使用者確認：

```
即將驗證 {N} 條驗收條件：

| AC | 驗收條件 | 類型 | 驗證方式 | 截圖 |
|----|---------|------|---------|------|
| AC-1 | 可依日期範圍查詢 | API | GET /api/xxx | — |
| AC-2 | 支援分頁顯示 | UI | 點擊下一頁 | 自動 📸 |
| AC-3 | 後台可查詢紀錄 | API | GET /admin/xxx | 後台 📸 |
| AC-4 | 支援匯出 Excel | UI | 點擊匯出按鈕 | 自動 📸 |

驗證模式：{MCP 工具 / Bash cdp.mjs}
{--api-only: 將跳過 UI 類型驗證}
{--manual: 每步驟等待確認}

截圖欄說明：
  —      純 API 驗證，無對應頁面
  自動 📸  UI 操作自動截圖
  後台 📸  API 驗證完後額外開啟後台頁面截圖（AI 從「指路」錨點指向的 Controller 推斷）

使用者可在確認時覆寫（如「第 1 項也加截圖」或「第 3 項不需要截圖」）。

確認開始？[Y/n]
```

### 4. 連接 Chrome（非 --api-only 時）

#### MCP 模式

> `--autoConnect` 旗標僅 **chrome-devtools-mcp**（退回模式）適用，安裝指令見 `references/mcp-install.md`；啟用後會自動連接本機 Chrome，不需手動處理連線。**Playwright MCP**（預設）由 `browser_tabs` 自行管理分頁，不需此旗標。

使用 `browser_tabs`（`action: list`）列出所有開啟的分頁，智慧匹配目標 URL：

1. 使用者透過參數指定的 URL
2. 從「指路」錨點指向的 Controller／路由設定讀到的頁面路徑（如 `/admin/xxx`）
3. 包含 `localhost` 的分頁

匹配後使用 `browser_tabs`（`action: select`）切換到目標分頁。

找不到 → 提示使用者在 Chrome 開啟目標頁面，然後重新 `browser_tabs`（`action: list`）。

#### Bash 模式

```bash
$CDP list
```

從 tab 清單中智慧匹配目標頁面，優先順序同上。

記錄匹配到的 `target_id` 供後續操作。

找不到 → 提示使用者在 Chrome 開啟目標頁面，然後重新 `$CDP list`。

### E2E Runner 模式（--e2e，Phase 3）

**前提**：優先使用 `../../references/e2e-contract.md` 的 portable `e2e.*` + `e2e_adapter` 設定；舊 `e2e_repo` / `e2e_profile` 僅作 read compatibility，不得再產生使用者家目錄絕對路徑的新設定。

1. 解析 E2E workspace / adapter；project-local `.crew/adapters/{id}.md` 優先於 plugin adapter
2. 若既有 E2E repo 尚使用 `tests/verify-map.json`，可讀取作 legacy mapping；新 mapping 應使用 `{slug}#AC-n` 穩定 join key
3. 對每個驗收條件，嘗試匹配既有 E2E coverage
4. 有匹配 → 依 adapter / e2e.command 執行 Playwright 測試
5. 無匹配 → 退回 Verification Router 所選 verifier；browser 類才使用 MCP 模式
6. 收集 JSON 結果 + 截圖；新整合應依 `../../references/e2e-result-schema.md` 產生機器可讀結果，再轉換成 verify.md 條目

Profile 選擇由 framework adapter 決定。若 legacy adapter 明確宣告以 `tests/config/profile-*.js` 掃描 profile，才使用該方式；generic core 不硬編碼 profile 檔案結構。

verify-map.json 格式：
```json
{
  "rob0027": {
    "describe": "一般問答完整測試",
    "mappings": [
      { "condition": "QA 新增", "steps": "1-12", "key_screenshot": "step-10-save" }
    ]
  }
}
```

### 5. 逐條驗證

> 📄 **執行前必讀全文**：[`phases/run-verification.md`](./phases/run-verification.md)
> 本段僅是入口摘要，**不可只依摘要執行**；MCP 模式工具對照、Bash 模式 cdp.mjs、
> Selector Fallback 6 級、stability 截圖、API+UI 交叉比對等細節都在 phases/run-verification.md 內。

摘要（僅供 AI 確認自己在做什麼，實際步驟必須讀 phases 全文）：
- 依序對每條 `AC-n` 執行 Verification Router 選定的 verifier，結果沿用同一個 `AC-n` 編號
- browser / API / backend-test / database / manual 各走自己的 evidence path
- precondition 失敗標 `BLOCKED`，不計為產品 FAIL
- Selector 失敗走 6 級 fallback 並記錄到 Layer 1 記憶
- 每步驟後判斷是否值得記憶（見『記憶記錄判斷』一節）
- **每驗完一條就寫進度**（中斷後可續跑，不必從頭再驗一遍）：
  ```bash
  python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" unit --slug {slug} \
    --skill plan-verify --done {已驗條數} --total {AC 總數} --label 條 \
    --remaining "{未驗的 AC 編號，逗號分隔}"
  ```

### 5.5 記憶記錄判斷（每步驟後）

每個驗證操作完成後，AI 判斷是否值得記錄到 Layer 1 記憶：

| 觸發條件 | 記錄內容 |
|---------|---------|
| Selector 第 1 次嘗試失敗 | 有效/無效 Selector 對照 |
| 等待策略調整過（如 networkidle 不夠，多等了 2s） | 最終有效的等待策略 |
| 使用 evaluate_script 做特殊操作（如 CKEditor API） | 特殊步驟 recipe |
| 發現環境差異（如某欄位在此環境不存在） | 環境差異描述 |
| **既有🟡記憶條目重新驗證仍有效** | 刷新該條目的 `last_verified` 為今日（不新增） |
| 順利完成（未觸發 fallback，無既有記憶） | **不記錄** |

每筆寫入記憶**必須包含 `last_verified: YYYY-MM-DD` 欄位**（當天日期）。
若覆寫既有條目（值改變），仍刷新 `last_verified`。

暫存在 `.spec/{slug}/.cache/verify-memory.md`（Layer 1，gitignore）。欄位格式見本文件『2.5 載入驗證記憶』（`last_verified` 時效性欄位）與『5.5 記憶記錄判斷』（各觸發條件對應的記錄內容），無獨立 schema 文件。跨任務資產請走『記憶升級判斷』一節升級到 canonical `.crew/verify-memory.md`（Layer 2）—— `.cache/` 隨時會被清掉。

### 6. 收集截圖與 Evidence

```bash
mkdir -p .spec/{slug}/screenshots
mkdir -p .spec/{slug}/evidence
```

將驗證過程中的截圖複製到 `.spec/{slug}/screenshots/`，API 測試的完整請求/回應存入 `.spec/{slug}/evidence/`：

**MCP 模式**：`browser_take_screenshot` 回傳截圖內容，直接儲存。

**Bash 模式**：
```bash
# cdp.mjs 截圖預設輸出至 ~/.cache/cdp/ 或目前目錄
cp {screenshot_path} .spec/{slug}/screenshots/verify-{N}-{desc}.png
```

截圖命名規則：`verify-{AC 編號}-{簡述}.png`，如 `verify-AC-1-query-result.png`。
Evidence 命名規則：`verify-{AC 編號}-request.txt`、`verify-{AC 編號}-response.json`（非 JSON 用 `.txt`）。

### 7. 逐條結果（對話輸出 ＋ `.cache/` 暫存）

完整逐條結果**輸出在對話**，同一份內容另寫到 `.spec/{slug}/.cache/verify.md`：

```bash
mkdir -p .spec/{slug}/.cache
```

- `.cache/verify.md` 的**唯一用途**是給可選的 Word／Excel 報告當輸入（見『可選指令』一節）。它是一次性暫存：不進版控、不同步 Notion、不被其他 skill 當事實來源、`/plan-close` 不讀它。
- 🔴 **不要**寫 `.spec/{slug}/verify.md`（舊路徑，已廢除）。

> **格式與完整範例見 [`examples/verify-report-sample.md`](./examples/verify-report-sample.md)**。逐項 outcome 支援 PASS / WARN / FAIL / BLOCKED / SKIP / MANUAL；`BLOCKED` 表示前置條件不成立、沒有資格判定產品功能。
> WARN 用途：功能已被證明通過，但環境差異、selector 或 evidence 穩定性有疑慮。

### 8. 落檔的兩件事（摘要一行 + 狀態）

**8a. plan.md「檢查報告摘要」節 append 一行**

依 `references/plan-common.md`「寫入紀律」用 **Edit** 對 `<!-- crew:rep  append-only -->` 那一整行插入，格式固定：

```text
- [{YYYY-MM-DD}] verify {PASS|WARN|FAIL}｜✅{N} ⚠️{N} ❌{N} 🚧{N} ⏭️{N} 👤{N}｜Health {分數}
```

🔴 只寫這一行：逐條結果不進 plan.md（該節上限 6 行），🔴 不得整節取代、不得動別節。
日期用 `date +%F` 的實際輸出。結論詞：無 ❌、無 ⚠️、無 🚧 → `PASS`；有 ⚠️ 或 🚧 且無 ❌ → `WARN`；有 ❌ → `FAIL`。

**8b. 寫回 state.json（唯一狀態權威）**

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" result --slug {slug} \
  --kind verify --status {PASS|WARN|FAIL} \
  --set health_score={分數} --set passed={N} --set failed={N} --set blocked={N} --set skipped={N} \
  --set manual={N} --set mode={full|api-only|manual|recheck|e2e}
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" unit --slug {slug} --clear
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" set --slug {slug} \
  --step verify --status done --phase verify
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" validate --slug {slug} --expect-phase verify
```

`results.verify` 取代舊流程「解析 verify.md 文字」的做法 —— 下游（`/plan-review`、`/plan-next`、`/plan-close`）一律讀這裡。

> **UAT 邊界**：本 skill 的 PASS/WARN/FAIL 是機器驗證結果，**不是人類 UAT 決策**。
> 完整契約見 `../../references/uat-gate.md`。本 skill 不得寫 `gates.uat`，
> 即使全部 PASS、即使使用 `--manual` 模式，也不得宣稱「UAT 已通過」。

### 9. 回傳結果

```
驗收驗證完成！

📋 逐條結果：見上方對話全文（暫存 .spec/{slug}/.cache/verify.md）
📝 已寫入：plan.md 摘要一行 + state.json results.verify
📸 截圖：.spec/{slug}/screenshots/ ({N} 張)
📊 統計：✅ {PASS} / ⚠️ {WARN} / ❌ {FAIL} / 🚧 {BLOCKED} / ⏭️ {SKIP} / 👤 {MANUAL}
🔧 工具：Playwright MCP{，chrome-devtools-mcp（--deep）}

{若有 FAIL}
⚠️  發現 {N} 個驗收條件未通過，建議修復後執行 /plan-verify --recheck

{若全部 PASS}
🎉 所有驗收條件通過！

後續可使用：
  • /plan-verify --recheck — 重新驗證失敗項目
  • /plan-verify --word    — 產 Word 驗收報告（可選，讀 .cache/）
  • /plan-review          — 多角色程式碼審查
  • review 完成後執行 /plan-close；Human UAT 在 /plan-close 內取得，verify PASS 不等於 UAT approved
```

### 9.5 記憶升級判斷

驗證完成後，檢查 Layer 1 `.spec/{slug}/.cache/verify-memory.md` 是否有新記錄：

1. 有新記錄 → 詢問是否升級到專案記憶。
2. 使用者選 YES：
   - canonical destination 一律是 `.crew/verify-memory.md`。
   - 若 canonical 不存在但 legacy `.claude/verify-memory.md` 存在，可讀 legacy 作 merge baseline；完成後寫 canonical，legacy 保持原樣。
   - 建立 `.crew/` 時只建立必要目錄/檔案，不修改 Host 設定。
   - 保留原始 `last_verified`；有重新驗證的條目刷新為今日。
   - frontmatter `last_updated` 更新為今日。
3. 使用者選 NO → 只保留 Layer 1 暫存，不升級。

升級標準：
- ✅ 頁面通用操作、全站 selector、專案統一 API 格式。
- ❌ 一次性操作、測試資料、Bug workaround、任何 secret。

### E2E candidate 產出（Phase 3，可選）

plan-verify 完成後（所有 PASS/WARN，且沒有 BLOCKED），若 portable E2E contract 已設定：

```
本次 runtime 驗證沒有 FAIL / BLOCKED。是否產出 E2E candidate（draft）？[Y/n]
```

YES → 先依 `../../references/verification-ir.md` 產生／讀取 `.cache/verification-ir.json`，再依 `../../references/e2e-contract.md` 的 framework adapter 產出 E2E candidate：
- 預設 maturity = `draft`，不能宣稱 CI-ready
- import / auth / profile / helper 寫法由 adapter 決定，不硬編碼 `@playwright/test`
- Stateful flow 可用單一 scenario + 多個 `test.step("AC-n: ...")`
- TODO/FIXME 標記需人工調整的地方
- Runtime 驗證使用到 `ci_eligible=false` 的 selector / recipe 時，不得無條件寫入 candidate
- 試跑與人工 review 後，仍需 `../../references/e2e-ci-policy.md` 的 E2E promotion gate 才可進 CI

---

## 可選指令：Word／Excel 驗收報告（不在主流程）

Word／Excel 報告是 `.cache/verify.md` 的**重排版衍生品**（零新增資訊），偶爾才需要交付給客戶或主管，
因此**不在 `/plan-verify` 主流程**，改由使用者明確下指令才產出：

```
/plan-verify --word     # Word 驗收報告
/plan-verify --excel    # Excel 驗收報告
```

- **輸入**：`.spec/{slug}/.cache/verify.md`（不重跑驗證）。檔案不存在 → 提示先跑一次 `/plan-verify`，🔴 不要憑印象生報告。
- **輸出**：`build/{功能}-驗收報告.docx` / `.xlsx`（專案根目錄的 `build/`，非 `.spec/`；🔴 交付物不進 `.spec/`，也不進版控）。
- **報告工具偵測**（`report_engine`）只在此模式執行，見『前置檢查流程』第 5 項。

> 📄 **執行前必讀全文**：[`phases/word-report.md`](./phases/word-report.md)
> 本段僅是入口摘要，**不可只依摘要執行**；風格選擇、引擎選擇、minimax-docx / python-docx
> 兩條路徑、報告範本、Logo 處理、降級提示都在 phases/word-report.md 內。

摘要（僅供 AI 確認自己在做什麼，實際步驟必須讀 phases 全文）：
- 先問風格（Intumit Brand / Tech Dark / Swiss Minimal）
- 依 `report_engine` 偵測結果走 minimax-docx 或 python-docx
- 兩者皆無 → 引導安裝 python-docx

---

## --recheck 模式

讀取既有 `.spec/{slug}/.cache/verify.md`，解析其中 `❌ FAIL` 與 `🚧 BLOCKED` 的項目：

1. 重新跑 FAIL + BLOCKED 項目
2. 結果合併回**同一份** `.cache/verify.md`（覆蓋對應 `AC-n` 的狀態）
3. 更新統計區塊
4. `plan.md`「檢查報告摘要」節**再 append 一行**新的 verify 摘要（🔴 不覆蓋前一行；該節 append-only，逼近 6 行上限時壓縮舊條目），並重跑『落檔的兩件事』一節 8b 的 `crew-state.py result`
5. `.cache/verify.md` 不存在（已被清掉）→ 退化為完整驗證，並在回報中說明

---

## --deep 模式（chrome-devtools-mcp 除錯增強）

標準驗證（Playwright）完成後，`--deep` 模式額外使用 chrome-devtools-mcp 做除錯分析：

| 工具 | 用途 | 場景 |
|------|------|------|
| `list_console_messages` | console 完整掃描（含 warning） | 偵測前端錯誤和警告 |
| `list_network_requests` | network 請求分析 | 失敗/慢請求偵測 |
| `performance_start/stop_trace` | 效能追蹤 | 頁面載入效能驗證 |
| `lighthouse_audit` | Lighthouse 稽核 | 效能/可及性報告 |
| `emulate` | 裝置/網路模擬 | 行動裝置驗證 |

結果追加到對話輸出與 `.cache/verify.md` 的「除錯分析」段落。

---

## 何時不用

本 skill 專責「為 plan.md 的 `AC-n` 選擇可靠 verifier 並收集 runtime evidence」，以下情境不屬此範圍：
- 驗證程式改動是否生效（非瀏覽器驗收）→ 改用內建 `/verify`
- 宣稱完成前的一般驗證 → 改用 `superpowers:verification-before-completion`
- 驗證 SQL 語法對不對 → 直接檢查語法，非本 skill 職責
- 審查程式碼品質/邏輯 → 改用 `/plan-review`
- 檢查文件錨點與程式碼是否對得上 → 改用 `/plan-drift`（本 skill 只驗運行時行為）

---

## Gotchas

- **Playwright snapshot 是 accessibility tree**：`browser_snapshot` 回傳的是無障礙樹，隱藏的 `<input type="hidden">`、純裝飾的 `<div>` 不可見。需要查 DOM 時用 `browser_evaluate` 執行 `document.querySelector()`。
- **httpOnly cookie 無法用 document.cookie 取得**：session cookie 常設為 httpOnly。API 驗證若需登入態，用 Playwright 的 `browser_evaluate` 中 `fetch()` 直接發請求。
- **Playwright 和 chrome-devtools 的截圖路徑不同**：Playwright 的 `browser_take_screenshot` 存到指定路徑；chrome-devtools 的 `take_screenshot` 回傳 base64。收集截圖到 `.spec/{slug}/screenshots/` 時需注意。
- **--deep 模式需要 chrome-devtools-mcp**：若未安裝，`--deep` 功能不可用但不影響標準驗證。提示使用者安裝。
- **記憶檔格式演進**：`verify-memory.md` 的格式可能隨版本演進。讀取時做好 fallback（舊格式仍可讀取，缺少的段落視為空）。
- **`.cache/` 會消失，別把它當事實來源**：它在 `.gitignore` 內、清 build 或換機器就沒了。要保留的結論只有兩處：plan.md 的摘要一行與 `state.json` 的 `results.verify`。Word／Excel 報告要留就自己搬出 `build/`。
- **驗證結果不回寫 plan.md 的 checkbox**：`- [ ] AC-n` 的勾選狀態屬規格（spec pass 的 owner），不是驗證結果。驗證通過與否看 `state.json` 的 `results.verify` 與摘要行；勾 checkbox 會讓兩套語意打架。
- **產品知識庫的 i18n 對照表可能不完整**：`products/{id}.md` 只列出高頻操作的翻譯。若驗證時遇到未列出的文字，退回穩定 selector 策略。
- **Layer 2 記憶需 git push 才能共享**：canonical `.crew/verify-memory.md` 需要使用者自行 commit / push；plugin 不會自動操作 git。legacy `.claude/verify-memory.md` 只讀不寫。

> Word/Excel 報告相關 Gotchas（雙引擎切換、python-docx 臨時安裝、截圖嵌入、封面資訊快取、Evidence 遮蔽、回應截斷判斷、多次 API evidence、Excel 需 Node.js）：見 `phases/word-report.md`「Gotchas（報告相關）」段。

---

## 邊界情況

- **plan.md「驗收條件」節為空**：提示先執行 `/plan spec`，或請使用者當場口述（並在回報標「本次條件未進 plan.md」）
- **preferred Playwright adapter 不可用**：先嘗試 chrome-devtools / local CDP fallback；仍不可用時依 `../../references/mcp-install.md` 顯示目前 Host 的整合指引，不在本 Skill 硬編碼 Claude-only 指令
- **Playwright 操作失敗**（如 selector 不存在）：標記該條為 FAIL，記錄錯誤訊息，繼續下一條
- **evidence 檔案寫入失敗**（磁碟空間不足等）：記錄警告，`.cache/verify.md` 中標註 `evidence_error: {原因}`，不阻斷驗證流程
- **--api-only 跳過 UI**：UI 類型標記為 SKIP，不影響其他驗證
- **截圖失敗**：記錄警告，不阻斷流程
- **`.cache/verify.md` 已存在**：直接覆蓋（它是一次性暫存，無保留價值；--recheck 例外，走合併）
- **驗證過程中使用者中斷**：已完成的結果仍寫入 `.cache/verify.md`（部分報告），且 `crew-state.py unit` 已記下斷點，下次可續跑
- **products/{id}.md 不存在**：product_id 指向的檔案不存在時，降為通用模式，顯示 WARN
- **verify-memory.md 格式損壞**：解析失敗時跳過記憶載入，不阻擋驗證流程
- **verify-map.json 不存在**（--e2e 模式）：全部退回 MCP 模式
- **E2E 測試失敗**（--e2e 模式）：前置條件成立且 assertion 失敗才標 FAIL；profile/login/fixture/environment 問題標 BLOCKED
- **共享環境 cleanup 不可靠**：runtime verify 可繼續並標 WARN，但 E2E candidate 不得宣稱 CI-ready

> Word/Excel 報告相關邊界情況（雙引擎皆不可用、python-docx 安裝失敗、report-config.md 不存在、截圖路徑無效、舊版 verify.md 相容、回應非 UTF-8、ExcelJS 安裝失敗）：見 `phases/word-report.md`「邊界情況（報告相關）」段。
