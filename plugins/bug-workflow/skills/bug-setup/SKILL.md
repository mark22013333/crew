---
name: bug-setup
description: Bug Workflow 首次設定引導。自動偵測 Notion 資料庫、建立設定檔、設定專案對應。當使用者提到「bug-setup」、「設定 bug workflow」、「初始化 bug」時觸發此 Skill。
---

# bug-setup — Bug Workflow 首次設定

互動式引導使用者完成 Bug Workflow Plugin 的初始設定，產出設定檔供其他 Skill 使用。

---

## 前置條件

- 已安裝 Notion MCP Server（Claude Code 可使用 `notion-search`、`notion-fetch` 等工具）
- 擁有 Notion Workspace 存取權限

---

## 流程

### 1. 決定設定檔位置並檢查是否已存在

**設定檔路徑規則**（依序檢查）：

1. 先檢查 `~/.claude-company/bug-workflow-config.md`（公司環境）
2. 再檢查 `~/.claude/bug-workflow-config.md`（個人環境）
3. 若都不存在 → 詢問使用者要儲存到哪裡：
   ```
   請選擇設定檔儲存位置：
   1. ~/.claude-company/bug-workflow-config.md（公司環境，推薦用於團隊共用 Notion Workspace）
   2. ~/.claude/bug-workflow-config.md（個人環境，推薦用於私人 Notion Workspace）
   ```
4. 若已存在 → 詢問使用者要「重新設定」還是「更新專案對應」

### 2. 偵測 Notion 資料庫

#### 2-1. 搜尋「任務追蹤工具」

使用 `notion-search` 搜尋 Workspace 中包含「任務追蹤」的資料庫。

**情境 A：找到現有資料庫**

用 `notion-fetch` 取得該資料庫的 data-source URL（`collection://...`），擷取 Data Source ID。

驗證欄位是否齊全（任務名稱、狀態、任務類型、優先順序、環境、根因分類、修復分支、專案資料庫）：
- 齊全 → 記錄 ID，繼續
- 缺少欄位 → 列出缺少的欄位，詢問使用者是否要自動新增（使用 `notion-update-data-source`）

**情境 B：找不到任務追蹤工具**

詢問使用者：
```
未找到「任務追蹤工具」資料庫，請選擇：
1. 建立新的「任務追蹤工具」（推薦，含標準欄位 + 4 個看板 View）
2. 指定一個現有資料庫
3. 跳過（無法使用 Bug Workflow）
```

若選擇建立：
1. 詢問要建立在哪個 Notion 頁面下（搜尋 Workspace 頁面供選擇）
2. 參照 `references/db-templates.md`「B. 任務追蹤工具」模版
3. 使用 `notion-create-database` 建立（**不含 Relation 欄位**，Relation 在步驟 2-4 統一補齊）
4. 使用 `notion-create-view` 依序建立 4 個 Views：所有任務（table）、依狀態（board）、我的任務（table）、核對清單（list）
5. 記錄 Data Source ID

#### 2-2. 搜尋「Bug 知識庫」

搜尋包含「bug」、「處理方式」的資料庫。

**情境 A：找到現有資料庫**

同樣擷取 Data Source ID 並驗證欄位。

**情境 B：找不到 Bug 知識庫**

詢問使用者：
```
未找到「Bug 知識庫」資料庫，請選擇：
1. 建立新的「Bug 知識庫」（推薦，含標準欄位）
2. 指定一個現有資料庫作為知識庫
3. 跳過知識庫（/bug-close 結案時不同步知識庫）
```

若選擇建立：
1. 詢問要建立在哪個 Notion 頁面下（預設與任務追蹤工具同頁面）
2. 參照 `references/db-templates.md`「C. Bug 知識庫」模版
3. 使用 `notion-create-database` 建立（**不含 Relation 欄位**）
4. 記錄 Data Source ID

#### 2-3. 偵測或建立「專案資料庫」

使用 `notion-search` 搜尋包含「專案」的資料庫。

**情境 A：找到現有資料庫**

用 `notion-fetch` 取得資料庫結構，驗證並補齊欄位：

| 欄位 | 類型 | 說明 | 必要性 |
|------|------|------|--------|
| 專案名稱 | Title | 顯示名稱 | 必要 |
| Git Repo | URL | Git 遠端倉庫 URL | 必要（缺少則新增） |
| 技術棧 | Select | scaffold 用 | 建議（缺少則詢問是否新增） |
| 狀態 | Status | 未開始 / 進行中 / 已結束 | 建議 |
| 程式版本 | Multi-Select | 碩網/偉康/極限/仁大/中華/客製版本 | 選用 |
| SIT 主機 | Text | SIT 部署主機資訊 | 選用 |
| UAT 主機 | Text | UAT 部署主機資訊 | 選用 |
| 正式環境主機 | Text | 正式環境部署主機資訊 | 選用 |
| 部署方式 | Text | 部署指令或流程簡述 | 選用 |
| 本機路徑 | Text | 本地開發路徑 | 選用 |
| JIRA | Text | JIRA 專案連結或代號 | 選用 |
| 地址 | Text | 客戶地址或辦公室位置 | 選用 |
| 說明 | Text | 專案簡要描述 | 選用 |
| Created | Created Time | 建立時間（自動） | 選用 |
| 上次編輯時間 | Last Edited Time | 最後編輯時間（自動） | 選用 |

- 必要欄位缺少 → 自動新增（使用 `notion-update-data-source`）
- 建議欄位缺少 → 詢問使用者是否新增
- 選用欄位缺少 → 列出可新增的欄位讓使用者勾選

**情境 B：找不到專案資料庫**

詢問使用者：
```
未找到專案資料庫，請選擇：
1. 建立新的「專案資料庫」（推薦，含標準欄位）
2. 指定一個現有資料庫
3. 跳過（無法自動關聯專案，需手動操作）
```

若選擇建立：
1. 詢問要建立在哪個 Notion 頁面下（搜尋 Workspace 頁面供選擇）
2. 參照 `references/db-templates.md`「A. 專案資料庫」模版
3. 使用 `notion-create-database` 建立資料庫，名稱為「專案資料庫」，包含上表所有欄位
4. 使用 `notion-create-view` 建立 2 個 Views：預設 Table View（Name 降序 + 狀態篩選）、List View
5. 記錄 Data Source ID

#### 2-4. 補齊 Relation 欄位

若本次有**新建**任何資料庫，需在所有資料庫建立完成後補上跨庫 Relation。

參照 `references/db-templates.md`「第二輪：補上 Relation 欄位」，使用 `notion-update-data-source` 執行：

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
   - host 含 `intumit`（公司 GitLab）→ `{group}/{repo}`（如 `FUB03P2402/PushAPIService`）
   - 其他（GitHub 等）→ `{host}/{group}/{repo}`（如 `github.com/org/repo`）
   - 自動去除 `.git` 後綴，支援 HTTPS / SSH 格式
3. 在設定檔「專案對應」表中精確匹配「Git Repo」欄位
4. 若不在 Git repo 或匹配失敗 → 進入互動式選擇

搜尋專案資料庫中的所有專案，檢查是否已有對應的專案條目。

**情境 A：專案資料庫中已有匹配的專案**（Git Repo 欄位精確匹配識別碼）

```
偵測到 Git Repo：TPE01P2101/LineBC
已匹配到 Notion 專案：北市府-TPE01P2101

是否更新專案資訊？[Y/n]
```

若選擇更新 → 進入專案資訊填寫流程（僅更新空白欄位）。

**情境 B：專案資料庫中有專案但未匹配**

```
偵測到 Git Repo：TPE01P2101/LineBC

請選擇要對應的 Notion 專案（或輸入 0 建立新專案）：
0. 建立新專案
1. 專案 A（Git Repo：未設定）
2. 專案 B（Git Repo：FUB03P2402/PushAPIService）
3. 專案 C（Git Repo：未設定）
```

選擇現有專案 → 將識別碼寫入「Git Repo」欄位，並進入專案資訊填寫流程。
選擇建立新專案 → 進入情境 C。

**情境 C：建立新專案條目**

使用 `notion-create-pages` 在專案資料庫建立新條目，引導填寫：

```
建立新專案，請填寫以下資訊：

  專案名稱：（必填）
  Git Repo：TPE01P2101/LineBC（已自動偵測，Enter 確認或修改）
  狀態：進行中（預設）

以下欄位可現在填寫，或稍後在 Notion 頁面補充：
  SIT 主機：（如 10.0.1.100，多台用換行分隔）
  UAT 主機：（如 10.0.1.200）
  正式環境主機：（如 AP1: 10.0.1.10, AP2: 10.0.1.11, WEB: 10.0.1.20）
  部署方式：（如 WAR 部署到 Tomcat、Docker、K8s 等）
  說明：（專案簡要描述）
```

自動偵測的欄位：
- **Git Repo**：從 `git remote get-url origin` 解析為識別碼
- 使用者可直接 Enter 確認或手動修改

選用欄位允許留空，使用者可稍後在 Notion 頁面直接編輯。

### 4. 產出設定檔

以 `references/config.template.md` 為模板，填入偵測到的 ID 與對應資訊，寫入使用者在步驟 1 選擇的路徑。

### 5. 回傳結果

向使用者顯示：

```
Bug Workflow 設定完成！

已偵測到的資料庫：
  ✅ 任務追蹤工具：1d8a401b-...
  ✅ Bug 知識庫：bd132aa4-...
  ✅ 專案資料庫：f67699b6-...

已設定的專案對應：
  • 北市府-TPE01P2101 → TPE01P2101/LineBC

設定檔位置：~/.claude-company/bug-workflow-config.md

現在可以使用：
  /bug-start <問題簡述>     — 建立 Bug 條目
  /bug-update <內容>        — 更新調查資訊
  /bug-close                — 結案並同步知識庫
  /bug-search <關鍵字>      — 搜尋過往 Bug 解法
  /bug-update reopen <Bug>  — 重新開啟已結案 Bug
```

---

## 邊界情況

- **Notion MCP 未安裝**：提示使用者先安裝 Notion Plugin（`claude plugin install Notion`）
- **Workspace 中有多個類似資料庫**：列出候選讓使用者選擇
- **使用者想新增更多專案對應**：可重複執行 `/bug-setup`，選擇「更新專案對應」
- **設定檔被意外刪除**：重新執行 `/bug-setup` 即可重建
- **專案資料庫已有欄位但名稱不同**（如「Repo」vs「Git Repo」）：列出現有欄位讓使用者選擇對應
- **不在 Git repo 中**：無法自動偵測識別碼，進入互動式選擇流程讓使用者手動指定專案
- **Git remote 不存在**：Git Repo 欄位留空，使用者可稍後補填
