---
name: bug-setup
description: bug-workflow 首次設定引導 —— 自動偵測 Notion 資料庫、建立設定檔、設定專案對應。當使用者提到 /bug-setup、「設定 bug workflow」、「初始化 bug workflow」時觸發此 Skill。
---

# bug-setup — Bug Workflow 首次設定

互動式引導使用者完成 Bug Workflow Plugin 的初始設定，產出設定檔供其他 Skill 使用。

---

## 前置條件

- 已安裝 Notion MCP Server（Claude Code 可使用 `notion-search`、`notion-fetch` 等工具）
- 擁有 Notion Workspace 存取權限

---

## 流程

### 1. 透過 portable resolver 檢查既有設定並決定寫入位置

不要自行判斷 Host-specific 實體路徑。讀取與寫入都透過 `bug/config` logical key：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"

BUG_CONFIG_READ_PATH="$(python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key bug/config \
  --mode read \
  --format path)"

BUG_CONFIG_WRITE_PATH="$(python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key bug/config \
  --mode write \
  --format path)"
```

- `[ -f "$BUG_CONFIG_READ_PATH" ]` → 讀取既有設定，詢問使用者要「重新設定」還是「更新專案對應」。
- 既有設定可能由 resolver 的 read fallback 找到；它只作為**讀取來源**。若 `BUG_CONFIG_READ_PATH != BUG_CONFIG_WRITE_PATH`，不得修改或搬移該 legacy 檔。
- 既有設定不存在 → 直接進入首次設定。
- 所有本次新建／更新的設定一律寫入 `BUG_CONFIG_WRITE_PATH`；`--mode write` 永遠回 canonical portable path。
- resolver 本身無副作用；實體 root / fallback 規則以 `../../references/config-contract.md` 為權威。

### 2. 偵測 Notion 資料庫

#### 2-0. 決定工作區位置（CREW 工作區頁面）

使用 `notion-search` 搜尋 Workspace 中是否已有「CREW 工作區」頁面。

**情境 A：找到現有工作區頁面**

直接使用，記錄 `workspace_page_id`。

**情境 B：未找到工作區頁面**

詢問使用者一次：

```
請選擇 CREW 工作區的位置：
1. 建立在 Workspace 頂層（推薦）
2. 選擇現有頁面作為 parent
```

使用 `notion-create-pages` 建立「🚀 CREW 工作區」頁面（先建空頁面），icon 設為「🚀」，記錄 `workspace_page_id`。

> 此步驟讓使用者**只需選擇一次位置**，後續所有新建資料庫都自動放在此頁面下。

#### 2-1. 搜尋「任務追蹤工具」

使用 `notion-search` 搜尋 Workspace 中包含「任務追蹤」的資料庫。

**情境 A：找到現有資料庫**

用 `notion-fetch` 取得該資料庫的 data-source URL（`collection://...`），擷取 Data Source ID。

驗證欄位是否齊全（任務名稱、狀態、任務類型、優先順序、環境、根因分類、修復分支、專案資料庫）：
- 齊全 → 記錄 ID，繼續
- 缺少欄位 → 列出缺少的欄位，詢問使用者是否要自動新增（使用 `notion-update-data-source`）

> **不移動既有資料庫**，僅記錄 Data Source ID。

**情境 B：找不到任務追蹤工具**

詢問使用者：
```
未找到「任務追蹤工具」資料庫，請選擇：
1. 建立新的「任務追蹤工具」（推薦，含標準欄位 + 4 個看板 View）
2. 指定一個現有資料庫
3. 跳過（無法使用 Bug Workflow）
```

若選擇建立：
1. **parent 設為工作區頁面**（`workspace_page_id`，不再個別詢問位置）
2. 參照 plugin 根目錄 `references/db-templates.md`（相對 SKILL.md 為 `../../references/`）「B. 任務追蹤工具」模版
3. 使用 `notion-create-database` 建立（**不含 Relation 欄位**，Relation 在『補齊 Relation 欄位』一節統一補齊）
4. **立即使用 `notion-update-data-source` 設定 `is_inline: true`**（否則資料庫會以子頁面模式顯示）
5. 使用 `notion-create-view` 依序建立 4 個 Views：所有任務（table）、依狀態（board）、我的任務（table）、核對清單（list）
6. 記錄 Data Source ID

#### 2-2. 搜尋「Bug 知識庫」

搜尋包含「bug」、「處理方式」的資料庫。

**情境 A：找到現有資料庫**

同樣擷取 Data Source ID 並驗證欄位。不移動既有資料庫。

**情境 B：找不到 Bug 知識庫**

詢問使用者：
```
未找到「Bug 知識庫」資料庫，請選擇：
1. 建立新的「Bug 知識庫」（推薦，含標準欄位）
2. 指定一個現有資料庫作為知識庫
3. 跳過知識庫（/bug-close 結案時不同步知識庫）
```

若選擇建立：
1. **parent 設為工作區頁面**（`workspace_page_id`，不再個別詢問位置）
2. 參照 plugin 根目錄 `references/db-templates.md`（相對 SKILL.md 為 `../../references/`）「C. Bug 知識庫」模版
3. 使用 `notion-create-database` 建立（**不含 Relation 欄位**）
4. **立即使用 `notion-update-data-source` 設定 `is_inline: true`**（否則資料庫會以子頁面模式顯示）
5. 記錄 Data Source ID

#### 2-3. 偵測或建立「專案資料庫」

使用 `notion-search` 搜尋包含「專案」的資料庫。

**情境 A：找到現有資料庫**

用 `notion-fetch` 取得資料庫結構，驗證並補齊欄位。

完整欄位清單、型態與 Select/Multi-Select 選項參照 plugin 根目錄 `references/db-templates.md`（相對 SKILL.md 為 `../../references/`）「A. 專案資料庫」Schema（權威來源）。以此對照時的必要性分級：

- **必要**（Name、Git Repo）：缺少 → 自動新增（使用 `notion-update-data-source`）
- **建議**（技術棧、狀態）：缺少 → 詢問使用者是否新增
- **選用**（其餘欄位：程式版本、SIT/UAT/正式環境主機、部署方式、本機路徑、JIRA、地址、說明、Created、上次編輯時間）：缺少 → 列出可新增的欄位讓使用者勾選

> 不移動既有資料庫。

**情境 B：找不到專案資料庫**

詢問使用者：
```
未找到專案資料庫，請選擇：
1. 建立新的「專案資料庫」（推薦，含標準欄位）
2. 指定一個現有資料庫
3. 跳過（無法自動關聯專案，需手動操作）
```

若選擇建立：
1. **parent 設為工作區頁面**（`workspace_page_id`，不再個別詢問位置）
2. 參照 plugin 根目錄 `references/db-templates.md`（相對 SKILL.md 為 `../../references/`）「A. 專案資料庫」模版
3. 使用 `notion-create-database` 建立資料庫，名稱為「專案資料庫」，包含該模版 Schema 所有欄位
4. **立即使用 `notion-update-data-source` 設定 `is_inline: true`**（否則資料庫會以子頁面模式顯示）
5. 使用 `notion-create-view` 建立 2 個 Views：預設 Table View（Name 降序 + 狀態篩選）、List View
6. 記錄 Data Source ID

#### 2-4. 補齊 Relation 欄位

若本次有**新建**任何資料庫，需在所有資料庫建立完成後補上跨庫 Relation。

參照 plugin 根目錄 `references/db-templates.md`（相對 SKILL.md 為 `../../references/`）「第二輪：補上 Relation 欄位」，使用 `notion-update-data-source` 執行：

1. **任務追蹤工具** → 專案資料庫：若任務追蹤工具缺少「專案資料庫」Relation
   ```
   ADD COLUMN "專案資料庫" RELATION({專案DS_ID})
   ```
2. **Bug 知識庫** → 專案資料庫：若 Bug 知識庫缺少「專案資料庫」Relation
   ```
   ADD COLUMN "專案資料庫" RELATION({專案DS_ID})
   ```
3. **專案資料庫** → 任務追蹤工具：雙向 Relation
   ```
   ADD COLUMN "任務追蹤工具" RELATION({任務DS_ID}, DUAL)
   ```
4. **專案資料庫** → Bug 知識庫：雙向 Relation
   ```
   ADD COLUMN "bug處理方式" RELATION({BugDS_ID}, DUAL)
   ```

> **注意**：僅對本次新建的資料庫補 Relation。若資料庫是既有的且已有 Relation 欄位，跳過該步驟。
> 若某個資料庫被跳過（使用者選擇「跳過」），則不建立與該資料庫的 Relation。

5. **任務追蹤工具** → 自我關聯（self-relation）：若任務追蹤工具缺少「相關任務」欄位
   ```
   ADD COLUMN "相關任務" RELATION({任務DS_ID}, DUAL)
   ```
   > DUAL 自動產生反向欄位「被關聯任務」。建立後用 `notion-fetch` 確認反向欄位名稱正確，若 Notion 自動命名不符預期，使用 RENAME COLUMN 修正為「被關聯任務」。
   > 此欄位用於 Bug ↔ Feature / Bug ↔ Bug 的任務間關聯，供 `/bug-start` 自動關聯來源 Feature 使用。

#### 2-5. 建立/更新工作區總覽頁面

所有資料庫建立完成後，更新工作區頁面內容，將所有資料庫以 inline linked view 嵌入。

參照 plugin 根目錄 `references/db-templates.md`（相對 SKILL.md 為 `../../references/`）「E. CREW 工作區頁面」模板，使用 `notion-update-page` 的 `replace_content` 寫入：

```markdown
<database data-source-url="collection://{任務DS_ID}" inline="true" icon="✅">任務追蹤工具</database>

<database data-source-url="collection://{BugKB_DS_ID}" inline="true" icon="🐛">Bug 知識庫</database>

<database data-source-url="collection://{專案DS_ID}" inline="true" icon="📂">專案資料庫</database>
```

**注意**：
- 將模板中的 `{任務DS_ID}`、`{BugKB_DS_ID}`、`{專案DS_ID}` 替換為實際的 Data Source ID
- 若某個資料庫被跳過，則不包含該資料庫的 linked view
- 無論資料庫是既有的（情境 A）還是新建的（情境 B），都使用 `data-source-url` 建立 linked view
- 功能設計庫的位置預留在任務追蹤工具與 Bug 知識庫之間（由 plan-setup 追加）

### 3. 設定專案資訊

取得 Git 遠端 URL 並解析為識別碼：

```bash
# Git remote URL（自動偵測）
git remote get-url origin 2>/dev/null || echo ""

# 分支名稱
git branch --show-current 2>/dev/null || echo ""

# 當前工作目錄（備用，非 Git repo 時使用）
pwd
```

**Git Repo 識別碼解析規則**：
1. 執行 `git remote get-url origin`
2. 解析為 Git Repo 識別碼：
   - host 含 `intumit`（公司 GitLab）→ `{group}/{repo}`（如 `ORG01P2401/PushAPIService`）
   - 其他（GitHub 等）→ `{host}/{group}/{repo}`（如 `github.com/org/repo`）
   - 自動去除 `.git` 後綴，支援 HTTPS / SSH 格式
3. 在設定檔「專案對應」表中精確匹配「Git Repo」欄位
4. 若不在 Git repo 或匹配失敗 → 進入互動式選擇

搜尋專案資料庫中的所有專案，檢查是否已有對應的專案條目。

**情境 A：專案資料庫中已有匹配的專案**（Git Repo 欄位精確匹配識別碼）

```
偵測到 Git Repo：ORG01P2401/sample-app
已匹配到 Notion 專案：範例機關-ORG01P2401

是否更新專案資訊？[Y/n]
```

若選擇更新 → 進入專案資訊填寫流程（僅更新空白欄位）。

**情境 B：專案資料庫中有專案但未匹配**

```
偵測到 Git Repo：ORG01P2401/sample-app

請選擇要對應的 Notion 專案（或輸入 0 建立新專案）：
0. 建立新專案
1. 專案 A（Git Repo：未設定）
2. 專案 B（Git Repo：ORG01P2401/PushAPIService）
3. 專案 C（Git Repo：未設定）
```

選擇現有專案 → 將識別碼寫入「Git Repo」欄位，並進入專案資訊填寫流程。
選擇建立新專案 → 進入情境 C。

**情境 C：建立新專案條目**

使用 `notion-create-pages` 在專案資料庫建立新條目，引導填寫：

```
建立新專案，請填寫以下資訊：

  專案名稱：（必填）
  Git Repo：ORG01P2401/sample-app（已自動偵測，Enter 確認或修改）
  狀態：進行中（預設）
```

其餘欄位（SIT 主機／UAT 主機／正式環境主機／部署方式／說明）為通用欄位引導，參照 plugin 根目錄 `references/project-page-templates.md`（相對 SKILL.md 為 `../../references/`）「建立新專案條目－通用欄位引導」一節。

自動偵測的欄位：
- **Git Repo**：從 `git remote get-url origin` 解析為識別碼
- 使用者可直接 Enter 確認或手動修改

選用欄位允許留空，使用者可稍後在 Notion 頁面直接編輯。

### 4. 產出設定檔

以 plugin 根目錄 `references/config.template.md`（相對 SKILL.md 為 `../../references/`）為模板，填入偵測到的 ID 與對應資訊，寫入 Step 1 的 canonical `BUG_CONFIG_WRITE_PATH`。

寫入前由 Skill 建立 parent directory；resolver 不負責 mkdir：

```bash
mkdir -p "$(dirname "$BUG_CONFIG_WRITE_PATH")"
```

即使 Step 1 是從 legacy fallback 讀到既有設定，更新結果也只寫 canonical portable path，不覆寫 legacy source。

**新增欄位**：在設定檔中填入「CREW 工作區」區段：

```markdown
## CREW 工作區

| 項目 | 值 |
|------|-----|
| 工作區頁面 ID | `{workspace_page_id}` |
| 工作區頁面 URL | `https://www.notion.so/{workspace_page_id}` |
```

### 5. 回傳結果

向使用者顯示：

```
Bug Workflow 設定完成！

已偵測到的資料庫：
  ✅ 任務追蹤工具：1d8a401b-...
  ✅ Bug 知識庫：bd132aa4-...
  ✅ 專案資料庫：f67699b6-...

🚀 CREW 工作區：https://www.notion.so/{workspace_page_id}

已設定的專案對應：
  • 範例機關-ORG01P2401 → ORG01P2401/sample-app

設定檔位置：{BUG_CONFIG_WRITE_PATH}

現在可以使用：
  /bug-start <問題簡述>     — 建立 Bug 條目
  /bug-update <內容>        — 更新調查資訊
  /bug-close                — 結案並同步知識庫
  /bug-investigate <關鍵字> — 假說驅動調查（含比對 Bug 知識庫過往解法）
  /bug-update reopen <Bug>  — 重新開啟已結案 Bug
```

---

## 何時不用

- 想一鍵完成 bug + feature 全部設定 → 用 /crew-init
- 只設定 feature 側 → 用 /plan-setup
- 初始化程式專案 / git repo / 專案指令 → Codex 建立 `AGENTS.md`；Claude Code 可用 `/init`；Git 初始化照常用 git
- 註冊專案到 Notion 專案庫 → 用 /project-add

---

## Gotchas

- **notion-search 回傳多個同名資料庫**：搜尋「任務追蹤」可能命中使用者自建的同名資料庫。務必用 `notion-fetch` 驗證欄位結構（至少含「任務名稱」Title + 「狀態」Status），才能確認是正確的目標資料庫。
- **Relation 不能在 create 時加**：`notion-create-database` 不支援直接建立 Relation 欄位，必須先建好所有資料庫（記錄 Data Source ID），再用 `notion-update-data-source` 的 `ADD COLUMN ... RELATION` 語法補上。忘記這點會導致建庫失敗。
- **data-source-url 格式**：從 `notion-fetch` 取得的 `data-source-url` 是 `collection://` 開頭的 UUID，不是 database ID（database ID 是頁面 URL 中的那串）。兩者不可混用。
- **DUAL Relation 方向**：`RELATION({DS_ID}, DUAL)` 是從「當前資料庫」指向「目標資料庫」建立雙向關聯。如果方向搞反（在專案資料庫建 DUAL 指向任務追蹤工具），雙向欄位名稱會不如預期。
- **notion-create-view 順序敏感**：Views 在 Notion UI 中的顯示順序等於建立順序，第一個建立的會成為預設 View。所以「所有任務」要最先建。
- **資料庫建立後必須設定 inline**：`notion-create-database` 預設 `inline=false`（子頁面模式），資料庫會以連結形式顯示，使用者需要點進去才看得到列表。每個資料庫建立後，必須立即使用 `notion-update-data-source` 設定 `is_inline: true`，才能在父頁面直接展開顯示列表。忘記這步會導致使用者體驗完全不符預期。

---

## 邊界情況

- **Notion MCP 未安裝**：提示使用者先安裝 Notion Plugin（`claude plugin install notion`）
- **Workspace 中有多個類似資料庫**：列出候選讓使用者選擇
- **使用者想新增更多專案對應**：可重複執行 `/bug-setup`，選擇「更新專案對應」
- **設定檔被意外刪除**：重新執行 `/bug-setup` 即可重建
- **專案資料庫已有欄位但名稱不同**（如「Repo」vs「Git Repo」）：列出現有欄位讓使用者選擇對應
- **不在 Git repo 中**：無法自動偵測識別碼，進入互動式選擇流程讓使用者手動指定專案
- **Git remote 不存在**：Git Repo 欄位留空，使用者可稍後補填
