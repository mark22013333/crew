---
name: bug-setup
description: Bug Workflow 首次設定引導。自動偵測 Notion 資料庫、建立設定檔、設定專案路徑對應。當使用者提到「bug-setup」、「設定 bug workflow」、「初始化 bug」時觸發此 Skill。
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

找到後用 `notion-fetch` 取得該資料庫的 data-source URL（`collection://...`），擷取 Data Source ID。

驗證欄位是否齊全（任務名稱、狀態、任務類型、優先順序、環境、根因分類、修復分支、專案資料庫）：
- 齊全 → 記錄 ID，繼續
- 缺少欄位 → 列出缺少的欄位，詢問使用者是否要自動新增（使用 `notion-update-data-source`）

#### 2-2. 搜尋「Bug 知識庫」

搜尋包含「bug」、「處理方式」的資料庫。

找到後同樣擷取 Data Source ID 並驗證欄位。

若找不到 → 詢問使用者：
- A) 指定一個現有資料庫作為知識庫
- B) 跳過知識庫（`/bug-close` 結案時不同步知識庫）

#### 2-3. 偵測或建立「專案資料庫」

使用 `notion-search` 搜尋包含「專案」的資料庫。

**情境 A：找到現有資料庫**

用 `notion-fetch` 取得資料庫結構，驗證並補齊欄位：

| 欄位 | 類型 | 說明 | 必要性 |
|------|------|------|--------|
| 專案名稱 | Title | 顯示名稱 | 必要 |
| 本機路徑 | Text | `pwd` 匹配用 | 必要（缺少則新增） |
| 技術棧 | Select | scaffold 用 | 建議（缺少則詢問是否新增） |
| Git Repo | URL | Git 遠端倉庫 | 建議 |
| SIT 主機 | Text | SIT 部署主機資訊 | 選用 |
| UAT 主機 | Text | UAT 部署主機資訊 | 選用 |
| 正式環境主機 | Text | 正式環境部署主機資訊 | 選用 |
| 部署方式 | Text | 部署指令或流程簡述 | 選用 |
| 狀態 | Status | `進行中` / `維護中` / `已結案` | 建議 |
| 說明 | Text | 專案簡要描述 | 選用 |

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
2. 使用 `notion-create-database` 建立資料庫，名稱為「專案資料庫」
3. 使用 `notion-update-data-source` 新增上表所有欄位
4. 記錄 Data Source ID

### 3. 設定專案資訊

取得當前工作目錄（`pwd`）和 Git 資訊：

```bash
# 當前工作目錄
pwd

# Git remote URL（自動偵測）
git remote get-url origin 2>/dev/null || echo ""

# 分支名稱
git branch --show-current 2>/dev/null || echo ""
```

搜尋專案資料庫中的所有專案，檢查是否已有對應的專案條目。

**情境 A：專案資料庫中已有匹配的專案**（本機路徑欄位匹配 `pwd`）

```
偵測到你目前在：/Users/cheng/IdeaProjects/Taipei/LineBC
已匹配到 Notion 專案：北市府-TPE01P2101

是否更新專案資訊？[Y/n]
```

若選擇更新 → 進入專案資訊填寫流程（僅更新空白欄位）。

**情境 B：專案資料庫中有專案但未匹配**

```
偵測到你目前在：/Users/cheng/IdeaProjects/Taipei/LineBC

請選擇要對應的 Notion 專案（或輸入 0 建立新專案）：
0. 建立新專案
1. 專案 A（本機路徑：未設定）
2. 專案 B（本機路徑：/Users/xxx/projects/B）
3. 專案 C（本機路徑：未設定）
```

選擇現有專案 → 將 `pwd` 寫入「本機路徑」欄位，並進入專案資訊填寫流程。
選擇建立新專案 → 進入情境 C。

**情境 C：建立新專案條目**

使用 `notion-create-pages` 在專案資料庫建立新條目，引導填寫：

```
建立新專案，請填寫以下資訊：

  專案名稱：（必填）
  本機路徑：/Users/cheng/IdeaProjects/Taipei/LineBC（已自動偵測）
  Git Repo：https://github.com/xxx/yyy.git（已自動偵測，Enter 確認或修改）
  狀態：進行中（預設）

以下欄位可現在填寫，或稍後在 Notion 頁面補充：
  SIT 主機：（如 10.0.1.100，多台用換行分隔）
  UAT 主機：（如 10.0.1.200）
  正式環境主機：（如 AP1: 10.0.1.10, AP2: 10.0.1.11, WEB: 10.0.1.20）
  部署方式：（如 WAR 部署到 Tomcat、Docker、K8s 等）
  說明：（專案簡要描述）
```

自動偵測的欄位：
- **本機路徑**：從 `pwd` 取得
- **Git Repo**：從 `git remote get-url origin` 取得
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
  • 北市府-TPE01P2101 → /Users/cheng/IdeaProjects/Taipei/LineBC

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
- **專案資料庫已有欄位但名稱不同**（如「路徑」vs「本機路徑」）：列出現有欄位讓使用者選擇對應
- **Git remote 不存在**：Git Repo 欄位留空，使用者可稍後補填
