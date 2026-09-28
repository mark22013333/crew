---
name: plan-start
description: 建立 Notion 條目 + .spec/{slug}/（plan.md 骨架 + state.json）+ Git branch 的統一任務入口（支援 feature 與 bug），含退出驗證確保必填欄位完整。當使用者提到 /plan-start、「開新 CREW 任務」、「建立規劃任務」時觸發此 Skill。
argument-hint: "<任務簡述> [選項]"
---

# plan-start — 統一任務入口（本地規劃模式）

在 Notion「任務追蹤工具」建立條目，同時在專案根目錄建立 `.spec/{slug}/`（`plan.md` 骨架 ＋ `state.json`），並可選建立 Git branch。支援 Feature 和 Bug 兩種類型。

> 本 skill 是 plan.md 骨架的**唯一建立者**。骨架用 Write 寫**一次**，之後所有階段一律用 Edit 對錨點插入 —— 章節契約與寫入紀律見 plugin 根目錄 `references/plan-common.md`（相對 SKILL.md 為 `../../references/`）。
> 紀律護欄：`../../references/discipline-preamble.md`。

---

## 設定目錄

依 plugin 根目錄 `references/config-resolver.md`（相對 SKILL.md 為 `../../references/`）的漸進式載入邏輯讀取設定。本 Skill 需要：
- **第 1 層**：`config.md`（Notion IDs）
- **第 2 層**：`projects/{repo-id}.md`（專案對應、技術棧 ID）

Bug 類型還需讀取 bug-workflow 設定。不要自行判斷 Host 路徑，改用 portable config resolver：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
BUG_CONFIG_FILE="$(python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key bug/config \
  --mode read \
  --format path)"
```

- `[ -f "$BUG_CONFIG_FILE" ]` → 讀取 Bug 任務所需的 bug-workflow 設定。
- 檔案不存在 → 提示使用者先執行 `/bug-setup`；不得自行 fallback 到 Host-specific 實體路徑。
- `--mode read` 的 portable/legacy fallback 由 `config-contract.md` 統一負責。

若設定目錄不存在，提示使用者先執行 `/plan-setup` 或 `/bug-setup`。

---

## 流程

> **前置檢查**：參照 plugin 根目錄 `references/prerequisites.md`（相對 SKILL.md 為 `../../references/`）執行完整前置檢查（專案指令 + 設定目錄 + 專案註冊）。

### 1. 解析使用者輸入

使用者會以以下格式觸發：

```
/plan-start <任務簡述> [選項]
```

**類型推斷**：
- 明確指定：`/plan-start feature 推播標籤查詢` 或 `/plan-start bug SSO 登入錯誤`
- 關鍵字推斷：輸入含「bug」、「錯誤」、「問題」、「修復」、「異常」→ type=bug
- 預設為 feature

**Bug 關聯選項**：
- `--related <feature-slug>`：手動指定關聯的 feature

### 2. 偵測環境資訊（自動專案對應）

自動偵測環境：

```bash
git branch --show-current 2>/dev/null || echo ""
pwd
git remote get-url origin 2>/dev/null || echo ""
```

Git Repo 識別碼解析規則：
- Git host 含 `intumit`（公司 GitLab）→ 只取 `{group}/{repo}`
- 其他（GitHub 等）→ 加上 host：`{host}/{group}/{repo}`
- 去除 `.git` 後綴

自動專案對應：用 Git Repo 識別碼轉換為檔名（`/` → `--`），檢查 `projects/{sanitized-id}.md` 是否存在。匹配失敗則進入互動式選擇。

### 3. 互動式補充資訊

#### Feature 類型

1. **所屬專案**（若自動偵測失敗）
2. **優先順序**（預設「中」）：`高` / `中` / `低`
3. **難度**（預設「中」）：`小` / `中` / `大`

#### Bug 類型

1. **所屬專案**（若自動偵測失敗）
2. **環境**（預設「正式」）：`測試` / `UAT` / `正式`
3. **優先順序**（預設「中」）：`高` / `中` / `低`

### 4. 產生 slug

從任務簡述產生英文 slug：
- 中文 → 翻譯為簡短英文（如「推播標籤查詢」→ `push-tag-query`）
- 已經是英文 → 轉為 kebab-case
- 確認 `.spec/{slug}/` 不存在，若存在則加數字後綴

### 5. 偵測負責人

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

### 6. 建立 Notion 條目

#### Feature 類型

使用 `notion-create-pages` 在「任務追蹤工具」建立，Properties：

| 欄位 | 值 |
|------|-----|
| 任務名稱 | 使用者提供的任務簡述 |
| 任務類型 | `["💬 功能要求"]` |
| 狀態 | `進行中` |
| 優先順序 | 使用者選擇 |
| 難度 | 使用者選擇 |
| 開發階段 | `需求分析` |
| 專案資料庫 | 關聯的專案頁面 URL |
| 負責人 | 「偵測負責人」一節偵測到的 Notion 使用者（若有） |

#### 兩步法建立頁面

**Step A**：使用 `post-page` 建立頁面（僅 properties，不帶 children）。

> **database_id 解析**：`config.md` 中的 Data Source ID 不能直接用於 `post-page` 的 `parent.database_id`。需先依照 plugin 根目錄 `references/plan-common.md`（相對 SKILL.md 為 `../../references/`）的「Notion database_id 解析」邏輯，呼叫 `retrieve-a-data-source` 取得底層 `database_id`。

**Step B**：取得 `page_id` 後，使用 `patch-block-children` 追加 plugin 根目錄 `references/notion-page-template.md`（相對 SKILL.md 為 `../../references/`）的標準 8 區塊模板。

**錯誤處理**：
- Step A 失敗 → 本地 `.spec/` 目錄照常建立，`notion.page_id` 留空
- Step B 失敗 → 頁面已建立（有 properties 無 body），在回傳結果中提示可用 `/plan-sync` 補寫

#### Bug 類型

使用 `notion-create-pages`，Properties 同 `bug-start`：

| 欄位 | 值 |
|------|-----|
| 任務名稱 | 使用者提供的任務簡述 |
| 任務類型 | `["🐞 錯誤"]` |
| 狀態 | `進行中` |
| 優先順序 | 使用者選擇 |
| 環境 | 使用者選擇 |
| 專案資料庫 | 關聯的專案頁面 URL |
| 負責人 | 「偵測負責人」一節偵測到的 Notion 使用者（若有） |

頁面 content 使用以下內嵌標準模板（與 `bug-workflow` plugin 的 `bug-start` 區塊結構一致，若使用者已安裝 `bug-workflow`，可自行比對其 `skills/bug-start/SKILL.md` 是否有更新；本 plugin 為獨立安裝，不跨 plugin 引用，故在此就地維護一份）：

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

建立方式同 Feature 的兩步法（Step A + Step B），但 Step B 追加的是上方內嵌模板，而非 `references/notion-page-template.md`。

### 7. 建立 .spec/{slug}/ 本地任務目錄

#### 7-1. 確保 .gitignore 包含 .spec/

檢查專案根目錄的 `.gitignore`，若不包含 `.spec/` 則追加：

```
# Local spec files (managed by plan-* skills)
.spec/
```

#### 7-2. 建立目錄與 plan.md 骨架

```bash
mkdir -p .spec/{slug}
```

用 **Write** 建立 `.spec/{slug}/plan.md`，內容**就是**下方骨架（六個章節、六個 HTML 錨點註解，各節留空）。
`type` 依步驟 1 的推斷填 `feature` 或 `bug`；`verified_at_commit` 與 `verified_at` **留空**（只有 `/plan-drift` 與 `/plan-close` 能寫）。

```markdown
---
slug: {slug}
name: {任務簡述}
type: {feature|bug}
verified_at_commit:
verified_at:
drift_policy: normal
---

# {任務簡述}

> {使用者提供的一句話需求／問題描述；沒有就留「（待 /plan 補）」}

## 目標與範圍        <!-- crew:goal owner=spec -->

## 驗收條件          <!-- crew:ac   owner=spec -->

## 決策紀錄          <!-- crew:dec  append-only -->

## 已知取捨與風險    <!-- crew:risk append-only -->

## 指路              <!-- crew:map  append-only -->

## 檢查報告摘要      <!-- crew:rep  append-only -->
```

🔴 **本 skill 是唯一能用 Write 碰 plan.md 的地方**。骨架寫完後，本 skill 自己也只能用 Edit 對錨點註解那一行插入內容。
🔴 **不要**在骨架裡塞需求全文、API 表、欄位清單或範例錨點 —— 章節內容由 `/plan` 的三個 pass 依 `references/plan-common.md`「章節契約」填入。
🔴 **不建立**其他任何文件檔；一個任務只有 `plan.md` ＋ `state.json`（＋ DB 階段才產生的 `deploy.sql`）。

#### 7-3. 建立 state.json（唯一權威）

流程狀態不寫進 plan.md，一律由單一寫者 `crew-state.py` 建立與更新：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" init \
  --slug {slug} --name "{任務簡述}" --type {feature|bug} \
  --notion-page-id {Notion 頁面 ID，沒有就省略} \
  --commit "$(git rev-parse HEAD 2>/dev/null)"
```

`init` 會把 `start` 標為 done、`phase` 設為 `start`。exit 1（slug 已存在）→ 確認是否重複建立；exit 3（環境問題）→ 修好再重跑，**不要**改用手寫 JSON。

#### 7-4. Bug 自動關聯 Feature

**本地 `.spec/` 層關聯**：

若使用者指定 `--related <feature-slug>`：
- 驗證 `.spec/{feature-slug}/plan.md` 存在
- 用 `crew-state.py list --all --format json` 取得該 feature 的 `notion.page_id`
- 在 Bug 的 plan.md「指路」節插入一行：`- 來源 feature：{feature-slug}（Notion：{URL}）`（依寫入紀律用 Edit 對 `crew:map` 錨點插入）

若未指定，嘗試智慧匹配：
1. `crew-state.py list --all --format json` 取得所有 `type=feature` 的任務
2. 從 Bug 描述中擷取關鍵字（Controller 名稱、Service 名稱、表名等）
3. 比對各 feature `plan.md` 的「目標與範圍」「決策紀錄」「指路」內容
4. 若匹配成功，提示使用者確認
5. 若無法判斷，跳過（使用者可後續手動指定）

**Notion 層 relation 關聯**：

本地關聯成功後，同步建立 Notion 的「相關任務」self-relation：

1. 從關聯 feature 的 `state.json` 取得 `notion.page_id`（已在本地關聯時讀取）
2. 使用 `notion-update-page` 設定 Bug 頁面的「相關任務」：
   ```json
   {
     "相關任務": {
       "relation": [{"id": "<feature-notion-page-id>"}]
     }
   }
   ```
3. 失敗 → 在回傳結果中提示可手動關聯，不阻擋流程

若本地關聯未成功（`.spec/` 中無匹配 feature），嘗試 Notion 層盲搜（同 `/bug-start`「自動關聯來源 Feature」一節邏輯）：

1. 從 Bug 標題擷取關鍵字（去除停詞）
2. 使用 `API-query-data-source` 查詢同專案的 Feature 條目（任務類型 contains 💬 功能要求）
3. 標題比對，找到最相關的 Feature
4. 匹配成功 → patch-page 設定 relation
5. 匹配失敗 → 跳過，在回傳結果中提示可手動關聯

**Feature Branch 偵測**（同 `/bug-start`「偵測來源 Feature Branch」一節）：

若成功關聯到 Feature（本地或 Notion 層），進一步偵測 Feature 的開發分支：

1. 從 feature 的 `state.json` 取得 `git.branch`，或從 Notion 頁面讀取「修復分支」欄位
2. 驗證分支存在：`git branch -a | grep -F "<branch-name>"`
3. 分支存在 → 設定 Bug 的修復分支為 feature branch，詢問是否切換
4. 分支不存在 → 提示使用者選擇（建新分支 / 當前分支 / 手動指定）
5. 失敗 → 跳過，修復分支保持「建立 Git branch」一節的設定

### 8. 建立 Git branch

從專案設定檔讀取 `prod_branch`（PROD 分支），作為新分支的基準：

```
是否建立 Git branch？
1. 是，建立 {feature|hotfix}/{slug}（從 {prod_branch} 分支）
2. 是，自訂分支名稱
3. 否，稍後再建立
```

若選擇建立：
1. `git checkout {prod_branch} && git pull && git checkout -b {type}/{slug}`
   （feature → `feature/{slug}`，bug → `hotfix/{slug}`，從 PROD 分支建立）
2. 更新 Notion 條目的「修復分支」欄位
3. 寫回狀態（**不要**手寫任何欄位）：
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" set \
     --slug {slug} --branch {分支名} --base {prod_branch}
   ```

> 若 `prod_branch` 未設定（舊專案），回退到從當前分支建立，並提示使用者執行 `/project-add` 補充分支設定。

### 9. 退出驗證（強制，不可跳過）

在回傳結果前，逐項檢查以下退出條件。

#### 驗證方式

- 對 Notion 欄位的驗證，**一律用 `notion-fetch` 讀回頁面確認欄位有值**，不信任 Agent 在「建立 Notion 條目」一節的記憶。
- 對本地狀態的驗證，**一律用 script 判定**，不用肉眼看檔案：

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" validate --slug {slug} --expect-phase start
  ```

#### 自動驗證項目

| # | 檢查項目 | 驗證方式 | 失敗處理 |
|---|---------|---------|---------|
| S1 | Notion 頁面已建立 | `crew-state.py list --slug {slug} --format json` 的 `notion.page_id` 非空 | 若「建立 Notion 條目」一節 Step A 已失敗（走降級路徑）→ 降為 ⚠️ WARN，提示稍後用 `/plan-sync` 補建；否則重試建立 |
| S2 | 專案資料庫已設定 | `notion-fetch` 讀回頁面，確認「專案資料庫」relation 欄位非空 | 從 `projects/{repo-id}.md` 取得 `notion_page_id`，用 `notion-update-page` 補上 relation |
| S3 | 修復分支已設定 | `list` 輸出的 `git.branch` 非空 **且** `notion-fetch` 確認「修復分支」欄位非空 | 見下方 S3 特殊處理 |
| S4 | 開發階段已設定（僅 Feature） | Feature → `notion-fetch` 確認「開發階段」欄位 = `需求分析`；Bug → 跳過此項 | 用 `notion-update-page` 補上 |
| S5 | 負責人已設定 | `notion-fetch` 確認「負責人」欄位非空 | 僅提示「負責人未自動設定，請至 Notion 手動指派」 |
| S6 | plan.md 骨架完整 | `.spec/{slug}/plan.md` 存在，且六個錨點註解（`crew:goal` `crew:ac` `crew:dec` `crew:risk` `crew:map` `crew:rep`）各出現一次 | 缺哪節就用 Edit 補回該節標題行，**不要**重寫整檔 |
| S7 | state.json 已建立且合法 | `crew-state.py validate --slug {slug} --expect-phase start` exit 0 | exit 1 → 依訊息修正後重跑；仍失敗 → `crew-state.py rebuild --slug {slug}` |

> **S1 條件式降級**：「建立 Notion 條目」一節的設計允許 Notion API 不可用時繼續建立本地 `.spec/`（offline-first）。若該節 Step A 已失敗，S1 不應阻擋整個流程，改為 WARN 並記錄。僅在 Step A 成功（頁面應已建立）但頁面 ID 為空時才視為 BLOCK。

#### S3 特殊處理（刻意 friction）

若「建立 Git branch」一節使用者選擇了「否，稍後再建立」，退出驗證時 **必須再次確認**（即使在 auto mode 下，**強制詢問**）：

```
⚠️ 修復分支尚未建立。
   Notion 的「修復分支」欄位將為空，可能影響團隊協作（其他成員無法從 Notion 得知開發分支）。

   確定不建立分支嗎？
   1. 建立分支（回到「建立 Git branch」一節流程）
   2. 確定跳過，我稍後自己建立
```

選 1 → 回到「建立 Git branch」一節的建立流程。
選 2 → S3 標記為 ⚠️ WARN（不阻擋），繼續。

#### 驗證結果分級

- **🔴 BLOCK**（S1, S2, S3, S6, S7）：必須解決後才能回傳結果
- **⚠️ WARN**（S4, S5）：記錄提醒但不阻擋

> S1 在「建立 Notion 條目」一節 Step A 已失敗（Notion 不可用）時，降級為 ⚠️ WARN。
> S3 在使用者明確確認跳過後，降級為 ⚠️ WARN。
> S4 對 Bug 類型自動跳過（Bug 不設定開發階段）。

#### 失敗自動修復

驗證失敗時，Agent **自行修復**（補呼叫 `notion-update-page`、重跑 `crew-state.py` 等），不要求使用者手動操作。僅在自動修復也失敗時才提示使用者。

### 10. 回傳結果

驗證結果只在對話輸出（不落檔；事件流由 `state.json` 的 `history` 承接）：

```
任務已建立！

📋 Notion 頁面：{URL}
📁 本地任務：.spec/{slug}/（plan.md + state.json）
🔀 Git branch：{branch}（若有）
📊 類型：{Feature / Bug}

退出驗證結果：
  {✅/⚠️} S1 Notion 頁面已建立
  {✅/⚠️} S2 專案資料庫：{專案名稱}
  {✅/⚠️} S3 修復分支：{branch}
  {✅/⚠️} S4 開發階段：{階段}
  {✅/⚠️} S5 負責人：{姓名 或 未設定}
  {✅/⚠️} S6 plan.md 骨架六節齊全
  {✅/⚠️} S7 state.json 驗證通過（phase=start）
  結論：{摘要}

後續可使用：
  • /plan                  — 完整規劃（spec → db → arch 三個 pass 寫進 plan.md）
  • /plan spec|db|arch     — 只跑其中一個 pass
  • /plan-build            — 多角色協作產生程式碼
  • /plan-next             — 不確定下一步時問它
  • /plan-status           — 查看所有任務狀態
  • /plan-close            — 結案並同步 Notion
```

---

## Gotchas

- **slug 翻譯品質影響全流程**：slug 會成為 `.spec/` 目錄名稱和 Git branch 名稱，一旦建立就很難改。中文翻譯成英文時，優先用專案中已有的術語（如範例專案中的「推播」→ `push` 而非 `broadcast`），保持與 codebase 一致。
- **骨架的錨點註解是後續所有寫入的插入點**：六行 `<!-- crew:xxx -->` 註解**不可改寫、不可對齊調整、不可翻譯**。改掉一個字，後續 pass 的 Edit 就找不到插入點，`crew-state.py rebuild` 也會誤判階段。
- **狀態不手寫**：分支、Notion 頁面 ID、階段一律經 `crew-state.py`。直接編輯 `state.json` 會繞過原子寫入與併發鎖；寫進 plan.md frontmatter 則會製造第二套狀態。
- **Bug 類型的 Notion 模板與 bug-start 不同步**：plan-start 建立 Bug 時用的模板要和 `bug-start` 的完全一致。如果 bug-start 更新了模板但 plan-start 沒跟上，會導致 `/bug-close` 找不到預期的區塊標題。
- **.gitignore 追加位置**：追加 `.spec/` 到 `.gitignore` 時，如果檔案末尾沒有換行，新增的行會和最後一行黏在一起。追加前確認末尾有換行。
- **Notion 層 relation 用 page ID 不是 URL**：`notion-update-page` 設定「相關任務」relation 時，`id` 欄位要填 page ID（UUID 格式），不是頁面 URL。`state.json` 的 `notion.page_id` 就是正確的值。
- **本地關聯和 Notion 關聯可能不一致**：本地「指路」節的來源 feature 與 Notion 的「相關任務」是兩個獨立的關聯。使用者在 Notion 手動刪除關聯不會更新本地，反之亦然。這是已知的 offline-first 限制。
- **Bug 的 Feature Branch 偵測依賴關聯結果**：Feature Branch 偵測是「Bug 自動關聯 Feature」一節的延伸邏輯，若關聯 Feature 失敗則整個分支偵測都跳過。不要獨立於關聯結果執行分支偵測。

---

## 何時不用

start 組 —— 本 skill 是完整入口（Notion + .spec/ + branch）；只要建 Notion bug 條目用 `/bug-start`。

- 只需 Notion bug 條目、不要 .spec/ 與 branch → 改用 `/bug-start`
- 任務已建、要規劃內容 → 改用 `/plan`
- 規劃前探索 → 改用 `/plan-explore`
- 註冊專案（非任務）→ 改用 `/project-add`

---

## 邊界情況

- **設定目錄不存在**：提示先執行 `/plan-setup` 或 `/bug-setup`
- **不在 Git repo 中**：跳過分支和專案自動偵測；`crew-state.py init` 的 `--commit` 省略
- **`.spec/` 目錄已存在同名 slug**：加數字後綴或詢問使用者（不要用 `init --force` 覆蓋別人的狀態檔）
- **Notion API 失敗（Step A）**：仍建立本地 `.spec/{slug}/`，Notion 頁面 ID 留空，提示使用者可稍後用 `/plan-sync` 補建
- **Notion API 失敗（Step B）**：頁面已建立但無 body 內容，提示使用者可用 `/plan-sync` 補寫 body
- **分支名稱衝突**：提示自訂名稱
