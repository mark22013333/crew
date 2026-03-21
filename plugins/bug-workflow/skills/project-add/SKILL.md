---
name: project-add
description: 將當前專案新增到 Notion 專案資料庫，或更新已存在的專案資訊。自動偵測 Git Repo、技術棧、專案類型（簡單型/產品型），產生 Notion 頁面內容，可選安裝 DB MCP。當使用者提到「新增專案」、「加專案」、「project-add」、「設定專案」、「註冊專案」時觸發此 Skill。
---

# project-add — 新增或更新 Notion 專案

快速將當前 Git 倉庫的專案新增到 Notion 專案資料庫，自動偵測專案架構並產生結構化頁面內容，可選安裝 DB MCP，同步更新所有 Workflow 設定檔。

---

## 前置條件

參照 `references/prerequisites.md` — 本 Skill 只檢查第 2 項（設定檔是否存在）。

- 已安裝 Notion MCP Server（`claude plugin install notion`）
- 已執行過 `/bug-setup` 或 `/plan-setup`（至少有一個設定檔存在）

---

## 設定檔

依序檢查以下路徑，讀取**所有找到的**設定（因為需要同步更新）：

**bug-workflow**（單一檔案格式）：
1. `~/.claude-company/bug-workflow-config.md`
2. `~/.claude/bug-workflow-config.md`

**feature-workflow**（階層式目錄格式）：
3. `~/.claude-company/feature-workflow/config.md`
4. `~/.claude/feature-workflow/config.md`
5. `~/.claude-company/feature-workflow-config.md`（舊格式，向下相容）
6. `~/.claude/feature-workflow-config.md`（舊格式，向下相容）

若都不存在，提示使用者先執行 `/bug-setup` 或 `/plan-setup` 完成初始設定。

從**第一個找到的設定**中取得「專案資料庫」Data Source ID（所有 workflow 共用同一個專案資料庫）。

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
- Git host 含 `intumit`（公司 GitLab）→ 只取 `{group}/{repo}`，例如 `FUB03P2402/PushAPIService`
- 其他（GitHub 等）→ 加上 host：`{host}/{group}/{repo}`，例如 `github.com/mark22013333/crew`
- 同時支援 HTTPS（`https://gitlab.intumit.com/FUB03P2402/PushAPIService.git`）和 SSH（`git@gitlab.intumit.com:FUB03P2402/PushAPIService.git`）格式

### 2. 檢查是否已存在

讀取設定檔中的「專案對應」表，檢查當前 Git Repo 識別碼是否已有對應的專案。

**已存在** → 顯示現有資訊，詢問：
```
此專案已在設定檔中：
  專案名稱：北市府-TPE01P2101
  Git Repo：FUB03P2402/LineBC

請選擇：
1. 更新專案資訊（Notion + 設定檔）
2. 取消
```

**不存在** → 繼續步驟 3。

### 3. 搜尋 Notion 專案資料庫

使用 `notion-search` 或直接用 Data Source ID 查詢「專案資料庫」中的所有專案。

**情境 A：Notion 中找到匹配的專案**（「Git Repo」欄位匹配識別碼）

```
偵測到 Notion 專案資料庫中已有匹配的專案：
  專案名稱：北市府-TPE01P2101
  Git Repo：FUB03P2402/LineBC

是否將此專案加入設定檔的專案對應？[Y/n]
```

若確認 → 跳到步驟 7（更新設定檔）。

**情境 B：Notion 中有專案但未匹配**

```
Notion 專案資料庫中有以下專案：

1. 北市府-TPE01P2101（Git Repo：FUB03P2402/LineBC）
2. FIA01P2403 WCS（Git Repo：FUB03P2402/WCS）
3. 專案 C（Git Repo：未設定）

0. 建立新專案

請選擇要對應的專案（輸入編號）：
```

選擇現有專案 → 將 Git Repo 識別碼寫入該專案的「Git Repo」欄位（`notion-update-page`），跳到步驟 7。
選擇建立新專案 → 繼續步驟 4。

**情境 C：Notion 專案資料庫為空或未找到匹配** → 繼續步驟 4。

### 4. 偵測專案類型與架構

#### 4-1. 技術棧自動偵測

掃描專案路徑下的 `pom.xml` 或 `build.gradle`：
- 含 `spring-webmvc` 且版本 < 5 + `tk.mybatis` → `spring-mvc-mybatis`
- 含 `spring-boot-starter` + `mybatis-spring-boot` → `spring-boot-mybatis`
- 含 `spring-boot-starter-data-jpa` → `spring-boot-jpa`
- 含 `mybatis-plus-boot-starter` → `spring-boot-mybatis-plus`
- 無法判斷 → 詢問使用者手動選擇或自訂

#### 4-2. 專案類型判斷

掃描專案結構，依據以下條件判定：

| 條件 | 判定 |
|------|------|
| 存在 `kernel/` 或類似外部資源目錄（含 `etc/`、`cores*/`、`db/`） | 產品型 |
| Gradle 多模組（根 `build.gradle` + 子目錄 `build.gradle`） | 產品型 |
| 偵測到中介軟體設定（Solr、Hazelcast、Elasticsearch 等） | 產品型 |
| VM Options 或 properties 中有 5+ 自訂 `-D` 參數 | 產品型 |
| 以上皆無 | 簡單型 |

```
偵測到專案類型：{簡單型 / 產品型}
確認？[Y/n]（輸入 n 可手動切換）
```

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

### 5. 建立新專案條目

#### 5-1. 引導填寫專案資訊

```
建立新專案，請填寫以下資訊：

  專案名稱：（必填）
  Git Repo：FUB03P2402/NewProject（已自動偵測）
  技術棧：spring-boot-mybatis（已自動偵測，Enter 確認或修改）
  狀態：進行中（預設）

以下欄位可現在填寫，或稍後在 Notion 頁面補充：
  SIT 主機：（如 10.0.1.100，多台用換行分隔）
  UAT 主機：（如 10.0.1.200）
  正式環境主機：（如 AP1: 10.0.1.10, AP2: 10.0.1.11, WEB: 10.0.1.20）
  部署方式：（如 WAR 部署到 Tomcat、Docker、K8s 等）
  說明：（專案簡要描述）
```

#### 5-2. 在 Notion 建立專案

使用 `notion-create-pages` 在「專案資料庫」（Data Source ID 從設定檔取得）建立新條目：

| 欄位 | 值 |
|------|-----|
| 專案名稱 | 使用者填入 |
| Git Repo | Git Repo 識別碼（從 `git remote get-url origin` 解析） |
| 技術棧 | 自動偵測或使用者指定 |
| 狀態 | `進行中`（預設） |
| 本機路徑 | `pwd` 的結果 |
| SIT 主機 | 使用者填入（可空） |
| UAT 主機 | 使用者填入（可空） |
| 正式環境主機 | 使用者填入（可空） |
| 部署方式 | 使用者填入（可空） |
| 說明 | 使用者填入（可空） |

#### 5-3. 產生頁面內容

參照 `references/project-page-templates.md`，根據步驟 4 偵測到的專案類型套用對應模版：

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

### 7. 同步更新所有設定

**重要**：必須同步更新所有存在的 Workflow 設定，確保 bug-workflow 和 feature-workflow 共用相同的專案對應。

#### bug-workflow（單一檔案格式）

依序檢查並更新：
1. `~/.claude-company/bug-workflow-config.md`
2. `~/.claude/bug-workflow-config.md`

在「專案對應」表中新增一列：
```markdown
| {專案名稱} | `{Git Repo 識別碼}` | {說明} |
```

#### feature-workflow（階層式目錄格式）

依序檢查並更新：
1. `~/.claude-company/feature-workflow/projects/`（新格式）
2. `~/.claude/feature-workflow/projects/`（新格式）
3. `~/.claude-company/feature-workflow-config.md`（舊格式，向下相容）
4. `~/.claude/feature-workflow-config.md`（舊格式，向下相容）

**新格式**：建立 `projects/{sanitized-repo-id}.md`（`/` → `--`）：
```markdown
---
notion_name: {專案名稱}
git_repo: {Git Repo 識別碼}
stack: {技術棧 ID}
---
{說明}
```

**舊格式**（向下相容）：在「專案對應」表中新增一列：
```markdown
| {專案名稱} | `{Git Repo 識別碼}` | {技術棧} | {說明} |
```

**更新已存在的專案**（步驟 2 選擇「更新」時）：
- 使用 `notion-update-page` 更新 Notion 中的專案欄位
- 新格式：更新 `projects/{sanitized-repo-id}.md` 的 frontmatter
- 舊格式：更新設定檔中該專案的對應列

### 8. 檢查 CLAUDE.md 是否已推送

```bash
git ls-files --error-unmatch CLAUDE.md 2>/dev/null
```

- **CLAUDE.md 未被 Git 追蹤** → 提示：
  ```
  建議將 CLAUDE.md commit 並 push，讓團隊成員進入專案時不需重新執行 /init：
    git add CLAUDE.md && git commit -m "docs: 新增 CLAUDE.md 專案說明" && git push

  是否現在執行？[Y/n]
  ```
  若使用者確認 → 執行 commit + push。

- **已追蹤但有未提交的變更** → 提示：
  ```
  CLAUDE.md 有未提交的變更，建議 commit 並 push 讓團隊同步。
  ```

- **已追蹤且無變更** → 跳過。

### 9. 回傳結果

```
專案已新增到 Notion 專案資料庫！

  專案名稱：XXX
  Git Repo：FUB03P2402/NewProject
  專案類型：{簡單型 / 產品型}
  技術棧：spring-boot-mybatis
  DB：MSSQL {+ H2（Quartz）}
  DB MCP：{✅ 已安裝 DBHub / ⏭️ 已跳過}

已同步更新設定檔：
  ✅ ~/.claude-company/bug-workflow-config.md
  ✅ ~/.claude-company/feature-workflow-config.md

CLAUDE.md：{✅ 已推送 / ⚠️ 建議推送}

現在可以在此目錄使用：
  /bug-start <問題簡述>     — 建立 Bug 條目（自動關聯此專案）
  /plan-start <功能簡述>    — 建立功能需求（自動關聯此專案）
```

---

## Gotchas

- **設定同步必須更新「所有存在的」**：bug-workflow（單一檔案）+ feature-workflow（階層式目錄或舊檔案），遺漏任一個會導致另一個 workflow 找不到專案對應。步驟 7 的所有路徑每個存在的都要更新。若同時存在新舊格式的 feature-workflow 設定，**只更新新格式**，忽略舊格式。
- **intumit 判斷是硬編碼規則**：Git host 含 `intumit`（公司 GitLab）→ 只取 `{group}/{repo}`。未來若遷移到其他 GitLab 實例，需修改步驟 1 的解析邏輯。
- **Relation 值是頁面 URL 不是名稱**：`notion-create-pages` 的 Relation 欄位需要填入「被關聯頁面的 URL」（如 `https://www.notion.so/xxx`），不是填專案名稱字串。填錯格式會靜默成功但 Relation 為空。

---

## 邊界情況

- **設定檔不存在**：提示使用者先執行 `/bug-setup` 或 `/plan-setup`
- **專案資料庫 Data Source ID 不存在**：提示使用者重新執行 setup
- **已在設定檔中但 Notion 中找不到**：提示可能是 Notion 頁面被刪除，詢問是否重新建立
- **不在 Git repo 中**：提示使用者需在 Git 倉庫目錄下執行，或手動輸入 Git Repo 識別碼
- **Notion API 失敗**：顯示錯誤訊息，已填入的設定檔變更仍保留
- **只裝了其中一個 workflow**：僅更新該 workflow 的設定檔，不報錯
- **技術棧無法自動偵測**（非 Java 專案等）：技術棧欄位留空或使用者自訂
- **DB MCP 安裝失敗**：顯示錯誤訊息，不影響其他步驟（Notion 頁面已建立）
- **DBHub npx 不可用**：提示使用者先安裝 Node.js，或手動安裝 `npm install -g @bytebase/dbhub`
- **CLAUDE.md 不存在**：提示使用者先執行 `/init`（但不中止流程，專案註冊仍可完成）
