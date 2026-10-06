---
name: project-add
description: 將當前專案新增或更新到 Notion 專案資料庫 —— 自動偵測 Git Repo、技術棧、專案類型，產生 Notion 頁面，可選裝 DB MCP。當使用者提到 /project-add、「新增專案到 Notion」、「註冊專案」時觸發此 Skill。
---

# project-add — 新增或更新 Notion 專案

快速將當前 Git 倉庫的專案新增到 Notion 專案資料庫，自動偵測專案架構並產生結構化頁面內容，可選安裝 DB MCP，並以 portable `feature/project` contract 維護專案對應。

---

## 前置條件

參照 plugin 根目錄 `references/prerequisites.md`（相對 SKILL.md 為 `../../references/`）— 本 Skill 只檢查 Notion 後端偵測（0.5）與設定檔（2）是否就緒。

- 依 §0.5 偵測結果取得可用的 Notion 後端（`NOTION_BACKEND = "plugin"` 或 `"local"`）；兩者皆不可用時依 §0.5 提示安裝，不限定單一後端
- 已執行過 `/bug-setup` 或 `/plan-setup`（至少有一個設定檔存在）

---

## 設定來源

不要自行列舉 Host-specific 實體路徑。Bug / Feature 主設定都透過 portable resolver 讀取：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"

BUG_CONFIG_JSON="$(python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key bug/config \
  --mode read \
  --format json)"

FEATURE_CONFIG_JSON="$(python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key feature/config \
  --mode read \
  --format json)"
```

- 解析兩份 JSON 的 `source / path / representation`；只讀取 `source != missing` 的設定。
- 兩者都是 `source=missing` → 提示先執行 `/bug-setup` 或 `/plan-setup`。
- 從第一份含有效「專案資料庫」Data Source ID 的設定取得該 ID；Bug / Feature workflow 共用同一個 Notion 專案資料庫。
- 主設定只用來取得 Workflow / Notion metadata；**專案對應的 canonical ownership 是 `feature/project`**，不再把 project mapping 回寫到 Bug config 或 legacy monolith。
- 實體 fallback 規則由 `../../references/config-contract.md` 與 `crew-config.py` 統一負責。

---

## 流程

### 1. 自動偵測環境資訊

```bash
# 當前工作目錄
pwd

# Git remote URL
git remote get-url origin 2>/dev/null || echo ""

# 當前分支
git branch --show-current 2>/dev/null || echo ""
```

**解析 Git Repo 識別碼**：從 `git remote get-url origin` 的結果解析，規則如下：

- 去掉 `.git` 後綴（若有）
- Git host 含 `intumit`（公司 GitLab）→ 只取 `{group}/{repo}`，例如 `ORG01P2401/PushAPIService`
- 其他（GitHub 等）→ 加上 host：`{host}/{group}/{repo}`，例如 `github.com/mark22013333/crew`
- 同時支援 HTTPS（`https://gitlab.intumit.com/ORG01P2401/PushAPIService.git`）和 SSH（`git@gitlab.intumit.com:ORG01P2401/PushAPIService.git`）格式

### 2. 檢查 portable 專案對應是否已存在

取得 Git Repo 識別碼後，以 `feature/project` logical key 讀取既有 mapping：

```bash
PROJECT_CONFIG_READ_JSON="$(python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key feature/project \
  --repo-id "{Git Repo 識別碼}" \
  --mode read \
  --format json)"
```

依 resolver 回傳選 parser：

- `source=missing` → 尚未註冊，繼續『搜尋 Notion 專案資料庫』。
- `representation=hierarchical` → 讀取回傳 `path` 的 project frontmatter。
- `representation=legacy_monolith` → 沿用舊「專案對應」表 parser，從回傳 `path` 擷取目前 Git Repo 的列；legacy monolith **只讀，不原地修改**。

**已存在** → 顯示現有資訊，詢問：
```
此專案已有對應：
  專案名稱：範例機關-ORG01P2401
  Git Repo：ORG01P2401/sample-app

請選擇：
1. 更新專案資訊（Notion + portable 專案對應）
2. 取消
```

**不存在** → 繼續『搜尋 Notion 專案資料庫』一節。

### 3. 搜尋 Notion 專案資料庫

使用 `notion-search` 或直接用 Data Source ID 查詢「專案資料庫」中的所有專案。

**情境 A：Notion 中找到匹配的專案**（「Git Repo」欄位匹配識別碼）

```
偵測到 Notion 專案資料庫中已有匹配的專案：
  專案名稱：範例機關-ORG01P2401
  Git Repo：ORG01P2401/sample-app

是否將此專案加入 portable 專案對應？[Y/n]
```

若確認 → 跳到『寫入 portable 專案對應』一節。

> **缺值處理**：portable `feature/project` frontmatter 必填 `stack`（技術棧）、`prod_branch`（PROD 分支）；`uat_branch` 可空。情境 A 跳過了『偵測專案類型與架構』（4）與『Git Flow 分支偵測』（4-5），若 Notion 既有專案頁面缺少對應欄位值，寫入設定檔前需補齊：
> 1. 優先從 Notion 既有頁面欄位讀取技術棧／PROD 分支／UAT 分支
> 2. 仍缺值 → 針對缺的項目才執行對應偵測（技術棧跑 4-1、分支跑 4-5），不需重跑整個『偵測專案類型與架構』流程
> 3. 偵測不出 → 詢問使用者手動輸入 `stack` 與 `prod_branch`（必填不可留空；`uat_branch` 可留空）

**情境 B：Notion 中有專案但未匹配**

```
Notion 專案資料庫中有以下專案：

1. 範例機關-ORG01P2401（Git Repo：ORG01P2401/sample-app）
2. FIA01P2403 WCS（Git Repo：ORG01P2401/WCS）
3. 專案 C（Git Repo：未設定）

0. 建立新專案

請選擇要對應的專案（輸入編號）：
```

選擇現有專案 → 將 Git Repo 識別碼寫入該專案的「Git Repo」欄位（`notion-update-page`），跳到『寫入 portable 專案對應』一節。
選擇建立新專案 → 繼續『偵測專案類型與架構』一節。

**情境 C：Notion 專案資料庫為空或未找到匹配** → 繼續『偵測專案類型與架構』一節。

### 4. 偵測專案類型與架構

#### 4-1. 技術棧自動偵測

掃描專案路徑下的 `pom.xml` 或 `build.gradle`：
- 含 `spring-webmvc` 且版本 < 5 + `tk.mybatis` → `spring-mvc-mybatis`
- 含 `spring-boot-starter` + `mybatis-spring-boot` → `spring-boot-mybatis`
- 含 `spring-boot-starter-data-jpa` → `spring-boot-jpa`
- 含 `mybatis-plus-boot-starter` → `spring-boot-mybatis-plus`
- 無法判斷 → 詢問使用者手動選擇或自訂

#### 4-2. 專案類型判斷

掃描專案結構，依判定表分為「產品型 / 簡單型」，偵測後詢問使用者確認。判定條件表與確認框範本，參照 plugin 根目錄 `references/project-page-templates.md`（相對 SKILL.md 為 `../../references/`）「專案類型判斷」一節。

#### 4-3. DB 類型偵測

掃描以下來源偵測 DB 類型：

- `jdbc-*.properties` / `application.yml` / `application.properties` 中的 JDBC URL
- `pom.xml` / `build.gradle` 中的 JDBC driver 依賴
- `.run/*.xml`（IntelliJ Run Configuration）中的 `-Dsql=` 參數
- `kernel/db/` 目錄下的 `.mv.db` 或 `.h2.db` 檔案（H2）

| 偵測結果 | DB 類型 |
|---------|---------|
| `mssql-jdbc` / `sqlserver` / `-Dsql=MSSQL` | MSSQL |
| `mysql-connector` / `mysql://` | MySQL |
| `postgresql` / `postgres://` | PostgreSQL |
| `*.mv.db` / `*.h2.db` / `h2database` | H2（本機檔案） |

> 產品型專案通常同時有 MSSQL（業務資料）+ H2（Quartz 排程），兩者都要記錄。

#### 4-4. 產品型額外偵測

若判定為產品型，額外掃描：

- **產品名稱**：從 `-Dwise.version=` 或 build 設定推斷（如 `SRBT` → SmartRobot）
- **外部資源目錄**：`kernel/` 的相對路徑與子目錄結構
- **中介軟體**：
  - `solr.solr.home` → Solr
  - `hazelcast.config` → Hazelcast
  - 其他（Elasticsearch、Redis、RabbitMQ 等）
- **VM Options 範本**：從 `.run/*.xml`、`setenv.sh`、或使用者提供的 VM Options 擷取

```
偵測結果：
  專案類型：產品型
  產品名稱：SmartRobot
  DB：MSSQL + H2（Quartz）
  中介軟體：Solr, Hazelcast
  外部資源：kernel/（etc/, cores.v9/, db/）

是否正確？[Y/n]
```

#### 4-5. Git Flow 分支偵測

自動推測正式環境（PROD）和測試環境（UAT）分支。以 **commit 活動模式**為主要依據，分支名稱為輔助信號。完整的資料收集指令、PROD/UAT 推測邏輯信號表、展示範例與邊界情況，參照 plugin 根目錄 `references/git-flow-detection.md`（相對 SKILL.md 為 `../../references/`）。

> 此資訊會影響 `/plan-start`（從 PROD 分支建立 feature branch）、`/plan-close` 和 `/plan-review`（用 PROD 分支做 merge-base 計算 diff）。

### 5. 建立新專案條目

#### 5-1. 引導填寫專案資訊

```
建立新專案，請填寫以下資訊：

  專案名稱：（必填）
  Git Repo：ORG01P2401/NewProject（已自動偵測）
  技術棧：spring-boot-mybatis（已自動偵測，Enter 確認或修改）
  PROD 分支：production（已自動偵測，Enter 確認或修改）
  UAT 分支：uat（已自動偵測，Enter 確認或修改）
  狀態：進行中（預設）
```

其餘欄位（SIT 主機／UAT 主機／正式環境主機／部署方式／說明）為通用欄位引導，參照 plugin 根目錄 `references/project-page-templates.md`（相對 SKILL.md 為 `../../references/`）「建立新專案條目－通用欄位引導」一節。

#### 5-2. 在 Notion 建立專案

使用 `notion-create-pages` 在「專案資料庫」（Data Source ID 從設定檔取得）建立新條目：

| 欄位 | 值 |
|------|-----|
| 專案名稱 | 使用者填入 |
| Git Repo | Git Repo 識別碼（從 `git remote get-url origin` 解析） |
| 技術棧 | 自動偵測或使用者指定 |
| PROD 分支 | 自動偵測或使用者指定 |
| UAT 分支 | 自動偵測或使用者指定（可空） |
| 狀態 | `進行中`（預設） |
| 本機路徑 | `pwd` 的結果 |

其餘欄位（SIT 主機／UAT 主機／正式環境主機／部署方式／說明）值同通用欄位引導（見上方 5-1 的參照）。

#### 5-3. 產生頁面內容

參照 plugin 根目錄 `references/project-page-templates.md`（相對 SKILL.md 為 `../../references/`），根據『偵測專案類型與架構』一節偵測到的專案類型套用對應模版：

- **簡單型** → 模版 A
- **產品型** → 模版 B（含中介軟體、H2、VM Options 範本）

用偵測結果填充模版中的 `{佔位符}`，無法偵測的欄位保留 `{待填}`。

使用 `notion-update-page` 將模版內容寫入頁面 body。

> **更新已存在的專案**時，不覆蓋現有頁面內容，僅在頁面頂部追加缺少的區段。

### 6. DB MCP 安裝（可選）

偵測到 DB 類型後，詢問使用者是否安裝 DB MCP：

```
偵測到 DB 類型：MSSQL

是否安裝 DB MCP（讓 Claude Code 可直接查詢資料庫）？
1. 安裝 DBHub（推薦，支援 MSSQL/MySQL/PostgreSQL/SQLite/Oracle）
2. 跳過
```

#### 若選擇安裝

**Step 1 — 收集連線資訊**

```
請提供 DB 連線資訊：

  Host：（如 localhost 或 10.0.1.100）
  Port：（MSSQL 預設 1433，MySQL 預設 3306）
  Database：（資料庫名稱）
  Username：
  Password：
```

**Step 2 — 選擇 scope**

```
MCP 安裝範圍：
1. project — 僅此專案可用（推薦，密碼不跨專案）
2. user — 所有專案共用
```

**Step 3 — 執行安裝**

根據 DB 類型組裝 DSN 並執行：

```bash
# MSSQL
claude mcp add dbhub --scope project -- npx @bytebase/dbhub --transport stdio --dsn "sqlserver://user:password@host:port/database"

# MySQL
claude mcp add dbhub --scope project -- npx @bytebase/dbhub --transport stdio --dsn "mysql://user:password@host:port/database"

# PostgreSQL
claude mcp add dbhub --scope project -- npx @bytebase/dbhub --transport stdio --dsn "postgresql://user:password@host:port/database"
```

**Step 4 — 記錄與提示**

- 在 Notion 頁面的 🗄️ 資料庫區段填入連線資訊（**不含密碼**，僅記錄 host:port/database）
- 提示使用者：
  ```
  DB MCP 已安裝！請重啟 Claude Code 使其生效。
  重啟後可直接在對話中查詢資料庫（如「查看 users 表的結構」）。
  ```

> **注意**：H2 為本機檔案型 DB，DBHub 不直接支援。H2 資訊僅記錄在 Notion 頁面，不安裝 MCP。

### 7. 寫入 portable 專案對應

專案 mapping 的唯一新寫入目的地是 `feature/project --mode write`。不要修改 Bug config、Feature 主設定或 resolver read fallback 指向的 legacy monolith。

```bash
PROJECT_CONFIG_WRITE_PATH="$(python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key feature/project \
  --repo-id "{Git Repo 識別碼}" \
  --mode write \
  --format path)"

mkdir -p "$(dirname "$PROJECT_CONFIG_WRITE_PATH")"
```

將以下內容建立或完整更新到 `PROJECT_CONFIG_WRITE_PATH`。

**驗證／E2E 選填 metadata（不可在更新時誤刪）**：

- 若既有 hierarchical project frontmatter 已有 `product_id`、`e2e_adapter`、`e2e_workspace`、`e2e_profile`、`e2e_command`，更新專案時預設原值保留。
- 新專案不主動追問整套 E2E 設定；只有使用者明確提供、或目前 repo 已有 `.crew/products/` / `.crew/adapters/` 且需要關聯時才寫。
- `e2e_workspace` 必須是相對於**受測 application repo root** 的相對路徑；不得寫 `/Users/.../`、`/home/.../` 或 Windows 使用者家目錄絕對路徑。
- `e2e_profile` 只能放邏輯 profile ID；帳密、token、cookie 不得寫入 project frontmatter。
- 舊 `e2e_repo` 可讀取協助遷移，但新寫入一律改成 `e2e_workspace`。
- 若沒有這些選填值，frontmatter 直接省略欄位，不寫空 placeholder。

```markdown
---
notion_name: {專案名稱}
git_repo: {Git Repo 識別碼}
stack: {技術棧 ID}
prod_branch: {PROD 分支名稱}
uat_branch: {UAT 分支名稱，可空}
{若有 product_id：product_id: {產品 ID}}
{若有 E2E adapter：e2e_adapter: {adapter ID}}
{若有 E2E workspace：e2e_workspace: {相對於 application repo root 的路徑}}
{若有 E2E profile：e2e_profile: {邏輯 Profile ID}}
{若有 E2E command：e2e_command: {runner command}}
---
{說明}
```

**新增專案**：
- 使用上面的 canonical write path 建立 project file。
- 若 Step 2 從 `legacy_monolith` 找到舊 mapping，但使用者要更新，仍寫新的 canonical project file；portable canonical path 之後會優先於 legacy fallback。

**更新已存在的專案**：
- 使用 `notion-update-page` 更新 Notion 中的專案欄位。
- 更新 `PROJECT_CONFIG_WRITE_PATH` 的 frontmatter/body。
- 若 read source 是 legacy monolith，**不得**修改舊表格；它只作相容讀取來源。

Bug / Feature 主設定仍各自由 `bug/config`、`feature/config` 管理；本步驟不把專案 mapping 複製回主設定。

### 8. 檢查專案指令是否已納入 Git

```bash
for f in AGENTS.md CLAUDE.md; do
  [ -f "$f" ] && git ls-files --error-unmatch "$f" >/dev/null 2>&1 && echo "$f"
done
```

- **兩份都不存在** → 提示建立專案指令（Codex 建議 `AGENTS.md`；Claude Code 可用 `/init` 建立 `CLAUDE.md`），但不阻擋專案註冊。
- **存在但未被 Git 追蹤** → 建議把實際存在的指令檔 commit 並 push，讓團隊共用。
- **已追蹤但有未提交變更** → 提示同步變更。
- **至少一份已追蹤且乾淨** → ✅。

### 9. 回傳結果

```
專案已新增到 Notion 專案資料庫！

  專案名稱：XXX
  Git Repo：ORG01P2401/NewProject
  專案類型：{簡單型 / 產品型}
  技術棧：spring-boot-mybatis
  PROD 分支：production
  UAT 分支：uat
  DB：MSSQL {+ H2（Quartz）}
  DB MCP：{✅ 已安裝 DBHub / ⏭️ 已跳過}

Portable 專案對應：
  ✅ {PROJECT_CONFIG_WRITE_PATH}

專案指令：{✅ 已推送 / ⚠️ 建議推送 / ⚠️ 尚未建立}

現在可以在此目錄使用：
  /bug-start <問題簡述>     — 建立 Bug 條目（自動關聯此專案）
  /plan-start <功能簡述>    — 建立功能需求（自動關聯此專案）
```

---

## 何時不用

- 首次整體設定（尚未執行過 `/bug-setup` 或 `/plan-setup`）→ `/crew-init`（或分別執行 `/bug-setup` + `/plan-setup`）
- 要建立任務條目（非專案）→ `/plan-start` 或 `/bug-start`
- 要把含多個 sub-repo 的目錄轉成 virtual monorepo / 跨 repo workspace → `repo-atlas:atlas`
- 只是要初始化專案指令 → Codex 建立 `AGENTS.md`；Claude Code 可用 `/init`

---

## Gotchas

- **專案對應只有一個 canonical writer**：新的 project mapping 只寫 `feature/project --mode write`。`bug/config` / `feature/config` 是主設定 metadata，legacy monolith 只提供 read compatibility；不要為了「同步」再複製 project row 到多個 Host-specific 檔案。
- **intumit 判斷是硬編碼規則**：Git host 含 `intumit`（公司 GitLab）→ 只取 `{group}/{repo}`。未來若遷移到其他 GitLab 實例，需修改『自動偵測環境資訊』一節的解析邏輯。
- **Relation 值是頁面 URL 不是名稱**：`notion-create-pages` 的 Relation 欄位需要填入「被關聯頁面的 URL」（如 `https://www.notion.so/xxx`），不是填專案名稱字串。填錯格式會靜默成功但 Relation 為空。

---

## 邊界情況

- **設定檔不存在**：提示使用者先執行 `/bug-setup` 或 `/plan-setup`
- **專案資料庫 Data Source ID 不存在**：提示使用者重新執行 setup
- **已在設定檔中但 Notion 中找不到**：提示可能是 Notion 頁面被刪除，詢問是否重新建立
- **不在 Git repo 中**：提示使用者需在 Git 倉庫目錄下執行，或手動輸入 Git Repo 識別碼
- **Notion API 失敗**：顯示錯誤訊息；若 portable project file 已寫入則保留，後續重跑時依 `feature/project --mode read` 辨識既有 mapping
- **只完成其中一個 workflow 的 setup**：只要 `bug/config` 或 `feature/config` 其中一份可提供專案資料庫 Data Source ID 就可繼續；project mapping 仍統一寫 `feature/project`
- **技術棧無法自動偵測**（非 Java 專案等）：技術棧欄位留空或使用者自訂
- **DB MCP 安裝失敗**：顯示錯誤訊息，不影響其他步驟（Notion 頁面已建立）
- **DBHub npx 不可用**：提示使用者先安裝 Node.js，或手動安裝 `npm install -g @bytebase/dbhub`
- **`AGENTS.md` / `CLAUDE.md` 都不存在**：提示建立至少一份專案指令（但不中止流程，專案註冊仍可完成）
