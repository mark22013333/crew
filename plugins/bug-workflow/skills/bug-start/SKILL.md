---
name: bug-start
description: 在 Notion 任務追蹤工具建立 Bug 條目並建立最小 .spec/{slug}/state.json（不建立 plan.md、不建立新 Git branch）。當使用者提到 /bug-start、「建立 bug 條目」、「記錄 bug 到 Notion」、「bug 通報」時觸發此 Skill。
argument-hint: "<問題簡述> [環境] [優先順序]"
---

# Bug Start — 建立 Bug 條目與最小 Runtime State

在 Notion「任務追蹤工具」資料庫建立一筆 Bug 條目，自動填入標準化頁面模板並關聯對應專案；同時建立最小 `.spec/{slug}/state.json` 作為 Bug lifecycle 的 runtime 斷點。**不建立 `plan.md`、不建立新 Git branch。**

---

## 流程

> **前置檢查**：參照 plugin 根目錄 `references/prerequisites.md`（相對 SKILL.md 為 `../../references/`）執行完整前置檢查（專案指令 + 設定檔 + 專案註冊）。

### 1. 解析使用者輸入

使用者會以以下格式觸發：

```
/bug-start <問題簡述>
```

從使用者輸入中擷取：
- **問題簡述**（必填）：作為「任務名稱」

### 2. 偵測環境資訊（自動專案對應）

取得 branch 名稱、當前工作目錄與 Git Repo 識別碼：

```bash
# 分支名稱
git branch --show-current 2>/dev/null || echo ""

# 當前工作目錄
pwd

# Git 遠端 URL（用於自動對應 Notion 專案）
git remote get-url origin 2>/dev/null || echo ""
```

**Git Repo 識別碼解析規則**：

從 `git remote get-url origin` 取得遠端 URL 後，解析為識別碼：
- Git host 含 `intumit`（公司 GitLab）→ 只取 `{group}/{repo}`，例如 `ORG01P2401/PushAPIService`
- 其他（GitHub 等）→ 加上 host：`{host}/{group}/{repo}`，例如 `github.com/mark22013333/crew`
- 解析時去掉 `.git` 後綴，支援 HTTPS / SSH 格式

**自動專案對應邏輯**：

1. 執行 `git remote get-url origin` 取得 Git 遠端 URL
2. 解析為 Git Repo 識別碼（host 含 `intumit` → `{group}/{repo}`，其他 → `{host}/{group}/{repo}`，去除 `.git` 後綴）
3. 讀取設定檔中「專案對應」表，精確匹配「Git Repo」欄位
4. 若匹配成功 → 自動選定該專案，不再詢問
5. 若不在 Git repo 或匹配失敗 → 進入互動式選擇

若設定檔中無對應，也可用 `notion-search` 搜尋 Notion「專案資料庫」（Data Source ID 見設定檔），找「Git Repo」欄位與識別碼匹配的專案。

### 3. 互動式補充資訊

若使用者未在初始輸入中提供以下資訊，依序詢問：

1. **所屬專案**（若自動偵測失敗）：搜尋 Notion「專案資料庫」，列出「進行中」的專案供選擇
2. **環境**（預設「正式」）：`測試` / `UAT` / `正式`
3. **優先順序**（預設「中」）：`高` / `中` / `低`

使用者可在初始輸入中直接指定，例如：
```
/bug-start SSO登入找不到使用者 正式 高
```

### 3.5 產生 runtime slug

沿用 `/plan-start` 的 slug 規則，從問題簡述產生可重現的英文 slug：

- 中文 → 翻譯為簡短英文
- 已經是英文 → 轉為 kebab-case
- 確認 `.spec/{slug}/` 不存在；若存在則加數字後綴
- 🔴 不使用 Notion page ID 當 slug
- 🔴 不使用 `crew-state.py init --force` 覆蓋既有任務

這個 slug 只用於最小 runtime state；本 skill **不建立 `plan.md` 或新 branch**。

### 4. 偵測負責人

在建立 Notion 條目前，自動偵測負責人以填入「負責人」（people 類型）欄位：

1. 取得 Git 提交 email：
   ```bash
   git config user.email 2>/dev/null || echo ""
   ```
2. 呼叫 `notion-get-users` 取得 Notion 工作區使用者列表
3. 比對 Git email 與 Notion 使用者的 email 欄位（case-insensitive）
4. 若匹配成功 → 記錄該使用者的 Notion user ID，後續填入「負責人」欄位
5. 若匹配失敗或 API 呼叫失敗 → 跳過，不阻塞流程，在回傳結果中提示「負責人未自動設定，請至 Notion 手動指派」

> **注意**：`notion-get-users` 回傳的使用者物件包含 `id`、`name`、`person.email` 等欄位。比對時使用 `person.email`。

### 5. 建立 Notion 條目

使用 `notion-create-pages` 在「任務追蹤工具」資料庫建立新條目：

**Data Source ID**：從設定檔的「任務追蹤工具」取得

**Properties**：

| 欄位 | 值 |
|------|-----|
| 任務名稱 | 使用者提供的問題簡述 |
| 任務類型 | `["🐞 錯誤"]` |
| 狀態 | `進行中` |
| 優先順序 | 使用者選擇（預設「中」） |
| 環境 | 使用者選擇（預設「正式」） |
| 修復分支 | Git branch 名稱（若有） |
| 專案資料庫 | 關聯的專案頁面 URL |
| 負責人 | 「偵測負責人」一節偵測到的 Notion 使用者（若有） |

### 5.5 建立最小 Bug Runtime State

Notion 條目建立後（若 Notion 暫時失敗則 page id 留空），依 `../../references/host-capabilities.md` 的 `plugin_root` 解析 CREW plugin root，然後建立 Bug state。

先取得當前 Git 資訊；不在 Git repo 時留空：

```bash
CURRENT_BRANCH="$(git branch --show-current 2>/dev/null || true)"
CURRENT_COMMIT="$(git rev-parse HEAD 2>/dev/null || true)"
```

再執行：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" init \
  --slug {slug} \
  --name "{問題簡述}" \
  --type bug \
  ${CURRENT_BRANCH:+--branch "$CURRENT_BRANCH"} \
  ${CURRENT_COMMIT:+--commit "$CURRENT_COMMIT"} \
  ${NOTION_PAGE_ID:+--notion-page-id "$NOTION_PAGE_ID"}
```

成功後必須立即驗證：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" validate --slug {slug} --expect-phase start
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" next --slug {slug} --format json
```

exit gate：

- `state.json.type == "bug"`
- `phase == "start"`
- `steps` 只有 `start / investigate / fix / close`
- `next.command == "/bug-investigate"`

任一不成立 → **不要繼續寫初始證據或宣稱 Bug 已建立完成**；依錯誤訊息修正後重跑。

> `init` exit 1 且提示 state 已存在 → 視為 slug collision，回到 3.5 產生數字後綴；**不得使用 `--force`**。
>
> Notion API 失敗不阻擋本地 state 建立：省略 `--notion-page-id`，並在回傳結果提示稍後補同步。

### 6. 填入頁面模板

頁面的 content 使用以下標準模板：

```
## 🔴 問題描述
- **通報來源**：
- **發生時間**：{當前日期時間}
- **重現步驟**：
  1. ...
  2. ...
- **預期行為**：
- **實際行為**：
- **錯誤截圖**：

---

## 🔍 調查過程
### 關鍵 Log

### 相關 SQL 查詢

### 初步判斷

---

## 🧠 根因分析
- **問題根因**：
- **問題檔案**：
- **問題程式碼**：

---

## ✅ 修復方案
- **修改檔案清單**：
- **修改說明**：
- **修改後程式碼**：
- **修復 Commit**：
- **修復分支**：

---

## 🧪 驗證
- [ ] 本地測試通過
- [ ] UAT 驗證通過
- [ ] 正式環境確認
- [ ] 通報者確認問題已解決

---

## 📝 經驗教訓
- **學到什麼**：
- **如何預防**：
```

若使用者在初始輸入中已提供問題描述內容，將其預填入「問題描述」區塊的「實際行為」欄位。

### 7. 初始證據收集（自動，不需使用者介入）

建立 Notion 頁面後，自動收集環境資訊寫入「調查過程」區塊。

#### 收集項目

1. **最近 commit**（bug-start 專屬）：
   ```bash
   git log --oneline -5
   ```
   寫入「調查過程 > 最近變更」

2–4. **環境狀態／知識庫快速搜尋／學習快速搜尋**：與 `/bug-investigate` 共用收集指令，參照 plugin 根目錄 `references/evidence-collection.md`（相對 SKILL.md 為 `../../references/`）「共用收集項目」段。

#### 寫入格式

使用 `notion-update-page` 的 `update_content`，在「調查過程」區塊寫入，標題為「### [HH:mm] 初始環境快照」，先列本 skill 專屬的「最近 5 筆 commit」，再接 `references/evidence-collection.md`「共用 Notion 寫入格式」段的三段共用區塊：

```markdown
### [HH:mm] 初始環境快照

**最近 5 筆 commit**：
- abc1234 fix: 修正推播排程的 cron 表達式
- def5678 feat: 新增推播統計 API
- ...

（接續共用區塊：環境狀態／歷史參考／歷史學習，見 references/evidence-collection.md）
```

#### 不阻擋流程

參照 `references/evidence-collection.md`「不阻擋流程」段。

### 8. 自動關聯來源 Feature

建立 Bug 條目後，嘗試在同一資料庫中找到相關的 Feature 條目，透過「相關任務」self-relation 建立關聯（依 SRS 編號／功能模組名擷取關鍵字，查詢同專案 Feature 並比對標題，成功則 patch「相關任務」欄位）。完整流程細節（關鍵字擷取規則、查詢 filter、標題比對邏輯、不阻擋流程）參照 plugin 根目錄 `references/feature-linking.md`（相對 SKILL.md 為 `../../references/`）「步驟 8」段。

### 9. 偵測來源 Feature Branch

若步驟 8 成功關聯到 Feature，進一步讀取該 Feature 的「修復分支」欄位，驗證分支是否存在，並詢問使用者是否切換／改用此分支作為 Bug 修復分支。完整流程細節（分支存在/不存在的處理選項、不阻擋流程）參照 plugin 根目錄 `references/feature-linking.md`（相對 SKILL.md 為 `../../references/`）「步驟 9」段。

### 10. 回傳結果

向使用者回傳：
- Notion 頁面連結（若 Notion 暫時失敗則明確標示未同步）
- 本地 runtime state：`.spec/{slug}/state.json`
- 建立的條目摘要（任務名稱、專案、環境、優先順序）
- 關聯結果（若「自動關聯來源 Feature」成功）：「已關聯來源 Feature：{Feature 標題}」
- 修復分支（若「偵測來源 Feature Branch」調整過）：「修復分支：{branch}（來自關聯 Feature）」
- 提示後續可用指令：
  ```
  Bug 條目與 runtime state 已建立！crew-state.py next：
  • /bug-investigate     — 開始調查根因（推薦下一步）
  • /bug-update <內容>  — 補充調查資訊（Log、SQL、判斷等）
  • /bug-fix             — 確認根因後修復
  • /bug-close          — 修復完成後結案
  ```

---

## 何時不用

start 組 —— 本 skill 建立 Notion Bug + **最小 state.json**；需要完整規劃產物（plan.md）或新 Git branch 時才用 `/plan-start`。

- 需同時建立 `plan.md` + 新 Git branch → 使用 `/plan-start`（type=bug）
- Bug state/條目已存在、要開始調查 → 使用 `/bug-investigate`
- 根因已確認、要開始修 → 使用 `/bug-fix`
- 補充既有 bug 資訊 → 使用 `/bug-update`
- 建立 feature 新任務 → 使用 `/plan-start`

---

## Gotchas

- **專案資料庫 Relation 值是頁面 URL，不是名稱**：`notion-create-pages` 的 Relation 欄位需要填入「被關聯頁面的 URL」（如 `https://www.notion.so/xxx`），不是填專案名稱字串。填錯格式會靜默失敗，條目建立成功但 Relation 為空。
- **任務類型是 Multi-select 不是 Select**：值必須用陣列格式 `["🐞 錯誤"]`，不是字串 `"🐞 錯誤"`。用字串格式不會報錯但會建立新的標籤。
- **emoji 是欄位值的一部分**：「🐞 錯誤」、「💬 功能要求」、「💅 細調」中的 emoji 是必要的，不能省略，否則會建立一個新的 Select 選項。
- **Git Repo 識別碼比對必須精確**：`ORG01P2401/sample-app` 和 `ORG01P2401/sample-App` 是不同的識別碼。比對時使用原始大小寫，不做 case-insensitive matching。
- **相關任務是 self-relation，用 patch 不是 create**：「自動關聯來源 Feature」設定「相關任務」時，Bug 頁面已在「建立 Notion 條目」一節建立，必須用 `notion-update-page`（patch）而非 `notion-create-pages`。`notion-update-page` 的 Relation 欄位使用 `{"relation": [{"id": "..."}]}` 格式，id 是 page ID 不是 URL。
- **同一個 Bug 可能關聯多個 Feature**：「相關任務」relation 是陣列，若標題比對匹配到多個 Feature，可以全部加入 relation 陣列。但建議限制最多 3 個，避免過度關聯。
- **Feature Branch 可能已被刪除**：「偵測來源 Feature Branch」驗證分支存在性時，Feature 可能已 merge 且分支被清理。這是正常情境，不應視為錯誤。
- **修復分支優先順序**：「偵測來源 Feature Branch」取得的 feature branch 會覆蓋「建立 Notion 條目」一節設定的「修復分支」（通常是當前分支）。若使用者不希望在 feature branch 上修復，「偵測來源 Feature Branch」的互動式選擇允許保留原分支。

---

## 邊界情況

- **設定檔不存在**：提示使用者先執行 `/bug-setup` 完成初始設定
- **不在 Git repo 中**：跳過分支與專案自動偵測，修復分支留空；進入互動式選擇專案；「偵測來源 Feature Branch」跳過
- **使用者未指定專案**：列出進行中的專案供選擇；若只有一個專案則自動選定
- **Notion API 失敗**：仍建立本地 `state.json`（`notion.page_id` 留空），顯示錯誤訊息並提示稍後補同步；不要因此讓 Bug lifecycle 沒有 runtime state
- **「相關任務」欄位不存在**（舊版資料庫）：「自動關聯來源 Feature」的 patch-page 會失敗，靜默跳過並提示使用者執行 `/bug-setup` 更新 schema
- **專案無任何 Feature 條目**：「自動關聯來源 Feature」的 query 結果為空，跳過關聯
- **Bug 標題全是停詞**（如「錯誤修復」）：關鍵字擷取為空，跳過「自動關聯來源 Feature」
- **來源 Feature 的「修復分支」為空**：Feature 可能未設定分支（如手動建立的條目），「偵測來源 Feature Branch」跳過
- **來源 Feature 分支已刪除**：「偵測來源 Feature Branch」提供三個選項讓使用者決定修復分支
