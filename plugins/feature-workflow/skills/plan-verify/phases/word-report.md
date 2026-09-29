# plan-verify Phase: Word 驗收報告產出

本檔由 [`../SKILL.md`](../SKILL.md)「可選指令：Word／Excel 驗收報告」段引用。
**不在 `/plan-verify` 主流程**，只有使用者明確下 `--word` / `--excel` 才執行。

呼叫 CREW 內建 generator / CLI 前先依 Host Capability Contract 解析：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
[ -n "$CREW_PLUGIN_ROOT" ] || {
  echo "無法解析 plugin root"
  exit 1
}
```

不得猜 Claude/Codex marketplace cache 路徑。

- **輸入**：`.spec/{slug}/.cache/verify.md`（`/plan-verify` 留下的一次性暫存，本階段唯一資料來源，不重跑驗證）
- **輸出**：`build/{功能}-驗收報告.docx` / `.xlsx`（專案根目錄 `build/`，🔴 不寫進 `.spec/`）

```bash
mkdir -p build            # 輸出目錄；build/ 通常已在 .gitignore
```

`.cache/verify.md` 不存在 → 提示先跑一次 `/plan-verify`，🔴 不得憑對話記憶或印象生報告。

---

### 10. 報告產出（Word 驗收報告）

依序詢問報告風格和引擎：

#### 10.0c 環境偵測（在 10.0a 選風格之前執行）

執行以下偵測決定 `report_engine`：

```bash
# 偵測 .NET SDK
if ! command -v dotnet &>/dev/null; then
  report_engine="python-docx-pending"
elif [ "$(dotnet --version | cut -d. -f1)" -lt 8 ]; then
  report_engine="python-docx-pending"
else
  # 偵測 minimax-skills Core（verify-docx-cli 透過 ProjectReference 共用其 OpenXML helper）
  # MinimaxCorePath 是 portable override；若未設定，可沿用 Claude adapter 的既有相容 fallback。
  LEGACY_MINIMAX_CORE="$HOME/.claude/plugins/marketplaces/minimax-skills/skills/minimax-docx/scripts/dotnet/MiniMaxAIDocx.Core/MiniMaxAIDocx.Core.csproj"
  CORE_PATH="${MinimaxCorePath:-}"
  if [ -z "$CORE_PATH" ] && [ -f "$LEGACY_MINIMAX_CORE" ]; then
    CORE_PATH="$LEGACY_MINIMAX_CORE"
  fi
  if [ -z "$CORE_PATH" ] || [ ! -f "$CORE_PATH" ]; then
    report_engine="minimax-skills-missing"
  else
    report_engine="minimax-docx"
  fi
fi
```

依偵測結果分流：

- `report_engine = minimax-docx`：進入 10.0a 選風格，產出走 **10.4a**（verify-docx-cli）。
- `report_engine = minimax-skills-missing`：dotnet 就緒但缺 minimax-skills Core，依 `ask_user` capability 詢問：

  | 選項 | 動作 |
  |-----|------|
  | A) 安裝 minimax-skills plugin | 提示在 Claude Code 內執行 `/plugin install minimax-skills`，確認後重跑本偵測 |
  | B) 已從別處安裝 | 詢問 `MinimaxCorePath` 路徑，設定 env var 後重跑本偵測 |
  | C) 改用 python-docx fallback | 設 `report_engine="python-docx"`，產出走 10.4b |
  | D) 跳過 Word 報告 | 結束流程 |

- `report_engine = python-docx-pending`：沿用下方 10.0b 的 A/B/C 選項。

#### 10.0a 選擇報告風格

使用 `ask_user` capability 讓使用者選擇風格：

**問題**：「請選擇驗收報告風格」

| 選項 | `--style` 值 | 說明 | 需要 Logo |
|------|-------------|------|----------|
| Intumit Brand（預設） | `intumit` | 藍+橘企業風，Logo 封面，橘色裝飾線 | ✅ |
| Tech Dark | `tech-dark` | 深藍科技風，青綠強調色，code 風格封面 | ✅ |
| Swiss Minimal | `swiss` | 黑灰極簡，無 Logo，大留白，靠字體層次 | ❌ |

選擇結果傳入報告產出引擎的 `--style` 參數。
三種風格在 minimax-docx 和 python-docx 引擎中均可使用。

#### 10.0b 選擇報告引擎

##### report_engine = minimax-docx 時

進入 step 10.4a（verify-docx-cli）產出（含 TOC + OpenXML 結構驗證）。

##### report_engine = python-docx 或 python-docx-pending 時

```
⚠️ .NET 未安裝，有以下選項：
  A) 使用 python-docx 產出（品牌排版，含封面、Logo、頁眉頁腳，不含 TOC）
  B) 安裝 .NET SDK 後使用 minimax-docx（+ TOC + XSD 驗證）
  C) 跳過 Word 報告

選擇？[A/B/C]
```

- **選 A**：
  - 若 `report_engine = python-docx-pending`，先安裝：
    ```bash
    python3 -m pip install --target /tmp/crew-docx-env python-docx
    ```
  - 進入 python-docx 報告產出流程（步驟 10.4b）
- **選 B**：顯示安裝指引，等待安裝完成後繼續
  ```
  請安裝 .NET SDK 8.0+：

  macOS：    brew install dotnet-sdk
  Ubuntu：   sudo apt install dotnet-sdk-8.0
  Windows：  winget install Microsoft.DotNet.SDK.8

  安裝完成後，執行 minimax-skills 的 setup：
    bash {minimax-skills-path}/scripts/setup.sh

  安裝好了嗎？[Y]
  ```
  使用者確認後 → 進入 step 10.4a（verify-docx-cli）產出
- **選 C**：跳過，結束流程

#### 10.1 收集封面資訊

依以下優先順序取得每項封面資訊：

| 欄位 | 自動來源（優先順序） | 最終 fallback | 存檔位置 |
|------|-------------------|-------------|---------|
| 專案名稱 | `projects/{id}.md` 的 `notion_name` → `report-config.md` | 詢問使用者 | `report-config.md` |
| 功能名稱 | `.spec/{slug}/plan.md` frontmatter 的 `name` | 詢問使用者 | — |
| 驗證日期 | `.cache/verify.md` 的驗證日期 | 當天日期 | — |
| 版本號 | `report-config.md` 的 `version` | 詢問使用者（如 `v1.0`） | `report-config.md` |
| 承辦單位 | `report-config.md` 的 `company_name` | `Intumit`（硬編碼預設值） | `report-config.md` |
| 製作人 | `report-config.md` 的 `author` | OS 使用者名稱（`whoami` 或 `$USER`） | `report-config.md` |

**預設值邏輯**：
- 承辦單位：若 `report-config.md` 無值，預設帶入 `Intumit`，不詢問直接使用
- 製作人：若 `report-config.md` 無值，取 `whoami` 結果作為預設值，不詢問直接使用
- 使用者可在確認流程中覆寫任何預設值

**`report-config.md` 位置**：`~/.claude/feature-workflow/report-config.md`

**確認流程**：

1. 自動帶入所有能找到的欄位值
2. 展示給使用者確認：
   ```
   📋 報告封面資訊：
     專案名稱：{自動帶入或待填}
     功能名稱：{自動帶入}
     驗證日期：{自動帶入}
     版本號：{自動帶入或待填}
     承辦單位：{自動帶入或待填}
     製作人：{自動帶入或待填}

   確認？[Y/n] 或輸入欄位名稱修改（如「版本號 v2.0」）
   ```
3. 使用者確認後，將 `company_name` 和 `author` 存入 `report-config.md`（若不存在則建立）

#### 10.2 收集測試環境資訊

| 欄位 | 自動來源 | 備用來源 |
|------|---------|---------|
| 測試 URL | `.cache/verify.md` 摘要的「環境」欄位 | 詢問使用者 |
| 瀏覽器 | 自動偵測 | Chromium |
| 測試帳號角色 | 詢問使用者 | 「系統管理員」 |
| 測試資料說明 | 詢問使用者（可選） | 「使用測試環境既有資料」 |
| 前置條件 | `.spec/{slug}/plan.md` 的「目標與範圍」節 | 詢問使用者 |

展示後一次確認：

```
🔧 測試環境：
  URL：{自動帶入}
  瀏覽器：Chromium
  測試帳號角色：（請輸入，如「系統管理員」）
  測試資料說明：（請輸入，或 Enter 跳過）
  前置條件：{自動帶入或待填}

確認？[Y/n]
```

#### 10.3 組裝報告內容

AI 依以下七段式結構組裝 Markdown 報告內容（作為報告產出引擎的輸入，minimax-docx 和 python-docx 共用同一份 Markdown）：

**1. 封面**

```markdown
# {專案名稱}

## {功能名稱} — 驗收報告

| 項目 | 值 |
|------|-----|
| 驗證日期 | {YYYY-MM-DD} |
| 版本號 | {vX.Y} |
| 承辦單位 | {公司全名} |
```

**2. 簽核欄位**

```markdown
## 簽核

| 角色 | 姓名 | 簽章 | 日期 |
|------|------|------|------|
| 製作人 | {author} | | |
| 審核人 | | | |
| 客戶確認 | | | |
```

**3. 測試環境說明**

```markdown
## 測試環境

| 項目 | 說明 |
|------|------|
| 測試 URL | {URL} |
| 瀏覽器 | {瀏覽器} |
| 測試帳號角色 | {角色} |
| 測試資料說明 | {說明} |
| 前置條件 | {前置條件} |
```

**4. 驗收摘要**

```markdown
## 驗收摘要

| 狀態 | 數量 |
|------|------|
| 通過 | {N} |
| 未通過 | {N} |
| 略過 | {N} |
| 待人工確認 | {N} |

**結論**：{AI 依統計生成一句話結論}
```

結論生成規則：
- 全部 PASS → 「共 N 項驗收條件全數通過，建議進入正式上線流程。」
- 有 FAIL → 「共 N 項驗收條件，M 項未通過，需修正後重新驗證。」
- 有 MANUAL 無 FAIL → 「共 N 項驗收條件，M 項通過、K 項待人工確認。」

**5. 驗收明細**（每條一個段落，使用 `<!-- human_steps -->` 和 `<!-- evidence -->` 中的內容）

```markdown
### 驗收項目 {N}：{驗收條件名稱}

**結果：{通過/未通過/略過/待人工確認}** {✅/❌/⏭️/🔍}

**操作步驟**：
1. {人話操作步驟 1}
2. {人話操作步驟 2}
...

**預期結果**：{人話預期}

**實際結果**：{人話實際}

**測試紀錄**：（API 類型必填，UI 類型若有 curl 呼叫也須附上）

  請求：
    GET http://localhost:8080/ap/pushTagQuery/list
        ?startDate=2026-01-01
        &endDate=2026-03-18
        &pageNum=1&pageSize=20
    Headers:
      Cookie: JSES****f456

  回應（HTTP 200）：
    {
      "code": "0000",
      "data": {
        "list": [
          {"pushCode": "P001", "sendCount": 5000, "openCount": 1230},
          {"pushCode": "P002", "sendCount": 3200, "openCount": 890},

          ... （省略 5 筆，共 15 筆）

          {"pushCode": "P014", "sendCount": 210, "openCount": 58},
          {"pushCode": "P015", "sendCount": 100, "openCount": 22}
        ],
        "total": 15
      }
    }

  > 完整回應請見：evidence/verify-{N}-response.json

**截圖**：
![{描述}](screenshots/verify-{N}-{desc}.png)
```

**測試紀錄截斷規則**：

| 回應行數 | 處理方式 | evidence 檔案 |
|---------|---------|--------------|
| ≤ 20 行 | 完整顯示於報告 | 不產出（報告即完整內容） |
| > 20 行 | 前 10 行 + 省略提示 + 後 10 行 | 產出 `evidence/verify-{N}-response.json` |

省略提示格式：`... （省略 {M} 行，共 {total} 行）`

若單條驗收項目涉及**多次 API 呼叫**（如先查詢再更新），每次呼叫各自記錄為獨立的請求/回應區塊，evidence 檔案命名加上子序號：`verify-{N}-a-response.json`、`verify-{N}-b-response.json`。

**敏感資訊遮蔽規則**（僅 Word 報告，evidence 原始檔不遮蔽）：

| Header / 值 | 遮蔽方式 | 範例 |
|-------------|---------|------|
| Cookie | 保留名稱前 4 字元 + `****` + 後 4 字元 | `JSES****f456` |
| Authorization | 保留 scheme + 前 4 字元 + `****` | `Bearer eyJh****` |
| X-API-Key / Token | 前 4 字元 + `****` | `sk-l****` |

原則：讓讀者知道「有帶認證」但無法還原實際值。

**6. 待處理事項**（僅 FAIL / MANUAL 時）

```markdown
## 待處理事項

| # | 驗收條件 | 狀態 | 建議處理方式 |
|---|---------|------|------------|
| {N} | {條件} | {未通過/待人工確認} | {建議} |
```

**7. 附錄**

```markdown
## 附錄

### 版本紀錄

| 日期 | 版本 | 說明 |
|------|------|------|
| {日期} | {版本} | 初次驗收 |

### 參考文件

- 規劃文件：.spec/{slug}/plan.md
- 驗證技術紀錄：.spec/{slug}/.cache/verify.md（一次性暫存）
```

#### 10.4a 使用 minimax-docx 產出（report_engine = minimax-docx）

呼叫 plugin 內建的 verify-docx-cli .NET 子專案（它透過 ProjectReference 共用 minimax-docx Core 的 OpenXML helper）：

```bash
# 1. 由 plugin_root capability 取得本 plugin 路徑
CLI_DIR="$CREW_PLUGIN_ROOT/references/dotnet/verify-docx-cli"

# 2. 解析 Logo；使用者明確覆寫優先，否則使用 plugin 內建 asset
if [ -n "$USER_LOGO" ]; then
  LOGO="$USER_LOGO"
else
  LOGO="$CLI_DIR/assets/intumit-logo.png"
fi

# 3. 首次執行 UX 提示（dotnet restore + build 約 1-2 分鐘）
if [ ! -d "$CLI_DIR/bin" ]; then
  echo "⏳ 首次產出 Word 報告需要 build .NET 子專案（約 1-2 分鐘）..."
fi

# 4. 跑 verify-docx-cli
#    --framework net8.0：multi-target 專案 dotnet run 必須指定 TFM；net8.0 是下限，
#    搭配專案的 RollForward=LatestMajor，可在僅安裝較新 runtime（net9/net10）的機器上 roll-forward 執行。
dotnet run --framework net8.0 --project "$CLI_DIR" -- \
  --verify .spec/{slug}/.cache/verify.md \
  --screenshots .spec/{slug}/screenshots/ \
  --evidence .spec/{slug}/evidence/ \
  --output build/{功能}-驗收報告.docx \
  --style {style} \
  --logo "$LOGO" \
  --cover '{"project":"{project}","feature":"{feature}","author":"{author}","date":"{date}","company":"{company}","version":"{version}"}'
```

優於 python-docx 之處：
- **TOC field**：Word 開啟時自動 prompt 更新目錄（已設 `UpdateFieldsOnOpen`）
- **OpenXML 結構驗證**：產出後自動 gate-check（`OpenXmlValidator`），結構不合法即非零退出
- 精確控制 multi-section header/footer 與品牌樣式

**首次執行**：dotnet restore + build 約需 1-2 分鐘（拉 OpenXML / Markdig），後續 incremental build 只需數秒。

#### 10.4b 使用 python-docx 產出（report_engine = python-docx）

呼叫 plugin 內建的 `references/verify-docx-generator.py`：

```bash
# 若 python-docx 未安裝，臨時安裝到隔離目錄
if ! python3 -c "import docx" 2>/dev/null; then
  python3 -m pip install --target /tmp/crew-docx-env python-docx
fi

# 產出 Word 報告
PYTHONPATH=/tmp/crew-docx-env:$PYTHONPATH python3 \
  "$CREW_PLUGIN_ROOT/references/verify-docx-generator.py" \
  --verify .spec/{slug}/.cache/verify.md \
  --screenshots .spec/{slug}/screenshots/ \
  --evidence .spec/{slug}/evidence/ \
  --output build/{功能}-驗收報告.docx \
  --cover '{"project":"{project}","feature":"{feature}","author":"{author}","date":"{date}","company":"{company}","version":"{version}"}'
```

python-docx 產出規格見 `references/verify-docx-template.md`。

**與 minimax-docx 的差異**：

| 維度 | minimax-docx | python-docx |
|------|-------------|-------------|
| 排版品質 | 專業級（XSD 驗證、精確頁面控制） | 基礎（段落、表格、圖片嵌入） |
| 簽核欄位 | 精確格式控制 | 簡易表格 |
| CJK 字體 | 自動偵測 locale | 使用系統預設字體 |
| 安裝成本 | .NET SDK ~500MB | python-docx ~1MB |

#### 10.5 完成提示

**minimax-docx 產出時：**

```
📄 驗收報告已產出：build/{功能}-驗收報告.docx

報告包含：
  • 封面與簽核欄位
  • 測試環境說明
  • {N} 條驗收明細（含操作步驟與截圖）
  • {若有} 待處理事項 {M} 項

提示：可用 Word 開啟後自行調整格式或轉存 PDF。
```

**python-docx 產出時：**

```
📄 驗收報告已產出：build/{功能}-驗收報告.docx

報告包含：
  • 封面與簽核欄位
  • 測試環境說明
  • {N} 條驗收明細（含操作步驟與截圖）
  • {若有} 待處理事項 {M} 項

⚠️ 本次使用 python-docx 產出（基礎排版）。
   如需專業排版，可安裝 .NET SDK 後使用 minimax-docx：
   macOS: brew install dotnet-sdk
```

#### 10.6 Excel 報告產出（--excel 選項）

呼叫 plugin 內建的 `references/verify-excel-generator.js`：

```bash
# 安裝 ExcelJS（臨時，不污染專案；exceljs 無 bin 欄位，不可用 npx 直接執行）
NPM_TMP=$(mktemp -d)
npm install --prefix "$NPM_TMP" exceljs --no-save --silent

# 產出 Excel 報告（透過 NODE_PATH 注入臨時安裝的 exceljs）
NODE_PATH="$NPM_TMP/node_modules" node "$CREW_PLUGIN_ROOT/references/verify-excel-generator.js" \
  --verify .spec/{slug}/.cache/verify.md \
  --screenshots .spec/{slug}/screenshots/ \
  --evidence .spec/{slug}/evidence/ \
  --output build/{功能}-驗收報告.xlsx \
  --cover '{"project":"{project}","feature":"{feature}","author":"{author}","date":"{date}"}'
```

封面資訊取得方式同步驟 10.1（Word 報告的封面收集）。

Excel 報告規格見 `references/verify-excel-template.md`。

**--word --excel 同時指定時**：兩份報告從同一個 `.cache/verify.md` 產出，資料一致，格式各取所需。

#### 向下相容：舊版 verify.md

若 verify.md 中無 `<!-- human_steps -->` 註解（舊版產出）：
1. 進入降級模式：AI 從 verify.md 的技術驗證內容反推操作敘述
2. 在報告封面加註：「※ 操作步驟由系統自動轉譯，可能與實際操作有微差異」

若 verify.md 中無 `<!-- evidence -->` 區塊（舊版或 UI-only 驗證）：
1. Word 報告的「測試紀錄」段落顯示：「（本次驗證未記錄測試過程詳情）」
2. 不阻斷報告產出，其餘段落正常生成

---

## Gotchas（報告相關）

> 本節由 [`../SKILL.md`](../SKILL.md)「Gotchas」段引用（下放自 SKILL.md，避免本體過長）。

- **Word 報告雙引擎**：優先使用 minimax-docx（需 .NET SDK ≥ 8.0），fallback 為 python-docx（需 Python 3）。前置檢查時偵測可用引擎，step 10 時讓使用者選擇。兩種引擎共用同一份 Markdown 報告內容。
- **python-docx 臨時安裝**：使用 `pip install --target /tmp/crew-docx-env` 安裝到隔離目錄，不污染使用者的 Python 環境。`PYTHONPATH` 在呼叫時臨時注入。
- **截圖嵌入 Word**：minimax-docx 接受 Markdown 格式的圖片引用（`![](path)`）；python-docx generator 接受 `--screenshots` 目錄參數，自動嵌入。兩者皆使用相對於 `.spec/{slug}/` 的相對路徑。
- **封面資訊快取**：`report-config.md` 儲存於 `~/.claude/feature-workflow/` 下，跨專案共用（公司名稱、作者）。首次產出報告時建立。
- **Evidence 檔案是原始內容**：`evidence/` 目錄下的檔案包含未遮蔽的 Cookie、Token 等敏感資訊，僅供內部技術驗證。Word 報告中的「測試紀錄」段落會自動遮蔽。若報告需交付客戶，不要連同 `evidence/` 目錄一起交付。
- **回應截斷以行數判斷**：使用 `wc -l` 計算回應行數。JSON 先經過 `python3 -m json.tool` pretty-print 後再計算行數，避免單行 JSON 永遠不觸發截斷。
- **多次 API 呼叫的 evidence**：若單條驗收項目涉及多次 curl（如 POST 建立 + GET 查詢驗證），每次呼叫各自產出 evidence 檔案，子序號用 a/b/c 區分。
- **Excel 報告需 Node.js 環境**：`verify-excel-generator.js` 需要 Node.js runtime。若環境無 Node.js，Excel 報告無法產出但不影響其他功能。

## 邊界情況（報告相關）

> 本節由 [`../SKILL.md`](../SKILL.md)「邊界情況」段引用（下放自 SKILL.md，避免本體過長）。`.cache/verify.md` 無 `human_steps`／無 `evidence` 區塊的相容規則見上方「向下相容：舊版 verify.md」段，不重複列出。

- **minimax-docx 和 python-docx 皆不可用**：step 10 提供三選一（安裝 python-docx / 安裝 .NET / 跳過報告），不直接中斷流程
- **python-docx 安裝失敗**（如無 pip、磁碟滿）：顯示錯誤訊息，提示使用者手動安裝 `python3 -m pip install python-docx`，或改選安裝 .NET
- **`report-config.md` 不存在**：首次詢問所有封面欄位，產出後自動建立
- **截圖路徑無效**：報告中標註「（截圖不可用）」，不阻斷報告產出
- **回應非 UTF-8**（如二進位下載）：evidence 檔案存為 `.bin`，Word 報告測試紀錄顯示「（二進位回應，{N} bytes，請見 evidence 檔案）」
- **ExcelJS 安裝失敗**：跳過 Excel 報告產出，顯示安裝指引

---
