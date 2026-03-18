# Bug Workflow Plugin

整合 Notion 與 Claude Code，自動化 Bug 生命週期管理。

## 功能

| 指令 | 說明 |
|------|------|
| `/bug-setup` | 首次設定引導，自動偵測 Notion 資料庫並產出設定檔 |
| `/bug-start <問題簡述>` | 在 Notion 建立 Bug 條目，填入標準化模板 |
| `/bug-update <內容>` | 調查過程中更新 Bug 頁面（Log、SQL、判斷等） |
| `/bug-update reopen <Bug>` | 重新開啟已結案的 Bug（復發處理） |
| `/bug-close` | 從 Git diff 自動擷取修復細節，結案並同步知識庫 |
| `/project-add` | **偵測專案架構**（簡單型/產品型）→ Notion 註冊 → 可選安裝 DB MCP |

## 前置條件

1. **Notion Plugin** — 需先安裝 Notion MCP Server
   ```bash
   claude plugin install Notion
   ```

2. **Notion Workspace** — 需有以下資料庫（或由 `/bug-setup` 引導建立）：
   - **任務追蹤工具**：Bug 生命週期管理（主要資料庫）
   - **Bug 知識庫**（選用）：精簡索引，結案時自動同步
   - **專案資料庫**：管理專案對應

3. **Notion 權限** — Claude Code 需授權以下 Notion 工具：
   - `notion-search`、`notion-fetch`（搜尋與讀取）
   - `notion-create-pages`（建立 Bug 條目）
   - `notion-update-page`（更新頁面內容與屬性）
   - `notion-update-data-source`（新增欄位，僅 setup 時使用）

## 安裝

```bash
claude plugin marketplace add mark22013333/crew && \
claude plugin install bug-workflow
```

安裝後 Plugin 會自動啟用。若未自動啟用，手動執行：`claude plugin enable bug-workflow`

### 更新

```bash
claude plugin update bug-workflow@company-marketplace
```

更新完成後**重啟 Claude Code** 使新版生效。

> 若 `update` 顯示已是最新但功能未生效，可先移除再重裝：
> ```bash
> claude plugin uninstall bug-workflow@company-marketplace && \
> claude plugin install bug-workflow@company-marketplace
> ```

## 首次設定

安裝後執行 `/bug-setup`，自動完成：
1. 選擇設定檔儲存位置（公司環境或個人環境）
2. 偵測 Notion Workspace 中的資料庫
3. 驗證並補齊必要欄位（狀態、根因分類、修復分支等）
4. 設定當前專案目錄與 Notion 專案的對應
5. 產出設定檔

## 工作流程

```mermaid
flowchart TD
    discover["發現 Bug"]
    start["/bug-start<br/><i>建立 Notion 條目</i>"]
    update["/bug-update<br/><i>補充 Log、SQL、判斷</i>"]
    fix["修復並 commit"]
    close["/bug-close<br/><i>結案（diff → Notion → 知識庫）</i>"]
    reopen{上線後復發？}
    reopenCmd["/bug-update reopen<br/><i>重新開啟</i>"]

    discover --> start --> update --> fix --> close --> reopen
    reopen -- "是" --> reopenCmd --> update
    reopen -- "否" --> done(["完成"])

    style discover fill:#fee,stroke:#f66
    style done fill:#efe,stroke:#6c6
```

## 使用範例

### 建立 Bug

```bash
/bug-start 推播排程發送失敗，部分使用者未收到訊息
```

### 更新調查資訊

```bash
/bug-update 關鍵 log：NullPointerException at PushService.java:235
/bug-update 初步判斷：推播排程在取得 access token 時發生空指標，可能是 token 過期未更新
/bug-update log /opt/tomcat/logs/catalina.out    # 從檔案擷取 ERROR
```

### 結案

```bash
/bug-close    # 從 Git diff 自動擷取修復細節，更新 Notion 並同步知識庫
```

### 重新開啟已結案 Bug

```bash
/bug-update reopen                                   # 顯示該專案近期已結案 Bug 清單，互動式選擇
/bug-update reopen SSO登入找不到使用者                  # 用關鍵字搜尋已結案 Bug
/bug-update reopen https://www.notion.so/abe41af9...  # 直接貼 Notion 頁面連結
```

> 不帶參數時會列出該專案近期已結案的 Bug，可輸入編號、關鍵字、或 Notion 連結來選擇。

> 搜尋過往 Bug 解法可直接在 Notion 的 Bug 知識庫中搜尋，不需額外指令。

---

## 跨專案支援

Plugin 透過 `git remote get-url origin` 自動偵測 Git Repo，比對 Notion 專案資料庫中的「Git Repo」欄位，自動關聯到正確的專案。

在不同專案目錄下執行 `/bug-start`，會自動對應不同的 Notion 專案，無需手動切換。

### 新增專案（/project-add）

在新專案目錄下執行 `/project-add`，自動完成：

1. **偵測 Git Repo** 識別碼（支援公司 GitLab 與 GitHub）
2. **偵測技術棧**（掃描 pom.xml / build.gradle）
3. **判斷專案類型**：
   - **簡單型** — 單 WAR/JAR、Maven 單模組
   - **產品型** — Gradle 多模組、`kernel/` 外部資源、Solr/Hazelcast 中介軟體
4. **偵測 DB 類型**（MSSQL / MySQL / PostgreSQL / H2）
5. **同步 Notion** — 建立或更新專案條目，套用對應頁面模版
6. **可選安裝 DB MCP**（[DBHub](https://github.com/bytebase/dbhub)）：
   ```bash
   # 專案級安裝（推薦）
   claude mcp add dbhub --scope project -- \
     npx @bytebase/dbhub --transport stdio \
     --dsn "sqlserver://user:pwd@host:1433/database"
   ```
7. **檢查 CLAUDE.md** — 提醒 commit + push 讓團隊共用
8. **同步更新**所有 Workflow 設定檔（bug-workflow + feature-workflow）

已存在的專案也可用 `/project-add` 更新資訊（主機、部署方式等）。

## 設定檔

設定檔儲存位置由使用者在 `/bug-setup` 時選擇：

| 環境 | 路徑 | 適用場景 |
|------|------|---------|
| 公司 | `~/.claude-company/bug-workflow-config.md` | 團隊共用 Notion Workspace |
| 個人 | `~/.claude/bug-workflow-config.md` | 私人 Notion Workspace |

Skill 執行時會依序檢查公司 → 個人路徑，讀取第一個找到的設定檔。

設定檔包含：
- Notion 資料庫 Data Source ID
- 專案對應表
- 欄位對照表

可手動編輯此檔案，或透過 `/bug-setup` 重新設定。
