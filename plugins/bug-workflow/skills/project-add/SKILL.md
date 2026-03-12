---
name: project-add
description: 將當前專案新增到 Notion 專案資料庫，或更新已存在的專案資訊。自動偵測路徑、Git、技術棧，同步更新 bug-workflow 與 feature-workflow 設定檔。當使用者提到「新增專案」、「加專案」、「project-add」、「設定專案」、「註冊專案」時觸發此 Skill。
---

# project-add — 新增或更新 Notion 專案

快速將當前工作目錄的專案新增到 Notion 專案資料庫，並同步更新所有 Workflow 設定檔的專案路徑對應。

---

## 前置條件

- 已安裝 Notion MCP Server（`claude plugin install Notion`）
- 已執行過 `/bug-setup` 或 `/feature-setup`（至少有一個設定檔存在）

---

## 設定檔

依序檢查以下路徑，讀取**所有找到的**設定檔（因為需要同步更新）：

1. `~/.claude-company/bug-workflow-config.md`
2. `~/.claude/bug-workflow-config.md`
3. `~/.claude-company/feature-workflow-config.md`
4. `~/.claude/feature-workflow-config.md`

若都不存在，提示使用者先執行 `/bug-setup` 或 `/feature-setup` 完成初始設定。

從**第一個找到的設定檔**中取得「專案資料庫」Data Source ID（所有 workflow 共用同一個專案資料庫）。

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

### 2. 檢查是否已存在

讀取設定檔中的「專案路徑對應」表，檢查當前 `pwd` 是否已有對應的專案。

**已存在** → 顯示現有資訊，詢問：
```
此專案已在設定檔中：
  專案名稱：北市府-TPE01P2101
  本機路徑：/Users/cheng/IdeaProjects/Taipei/LineBC

請選擇：
1. 更新專案資訊（Notion + 設定檔）
2. 取消
```

**不存在** → 繼續步驟 3。

### 3. 搜尋 Notion 專案資料庫

使用 `notion-search` 或直接用 Data Source ID 查詢「專案資料庫」中的所有專案。

**情境 A：Notion 中找到匹配的專案**（「本機路徑」欄位匹配 `pwd`）

```
偵測到 Notion 專案資料庫中已有匹配的專案：
  專案名稱：北市府-TPE01P2101
  本機路徑：/Users/cheng/IdeaProjects/Taipei/LineBC

是否將此專案加入設定檔的路徑對應？[Y/n]
```

若確認 → 跳到步驟 5（更新設定檔）。

**情境 B：Notion 中有專案但未匹配**

```
Notion 專案資料庫中有以下專案：

1. 北市府-TPE01P2101（路徑：/Users/cheng/IdeaProjects/Taipei/LineBC）
2. FIA01P2403 WCS（路徑：/Users/cheng/IdeaProjects/cht）
3. 專案 C（路徑：未設定）

0. 建立新專案

請選擇要對應的專案（輸入編號）：
```

選擇現有專案 → 將 `pwd` 寫入該專案的「本機路徑」欄位（`notion-update-page`），跳到步驟 5。
選擇建立新專案 → 繼續步驟 4。

**情境 C：Notion 專案資料庫為空或未找到匹配** → 繼續步驟 4。

### 4. 建立新專案條目

#### 4-1. 技術棧自動偵測

掃描專案路徑下的 `pom.xml` 或 `build.gradle`：
- 含 `spring-webmvc` 且版本 < 5 + `tk.mybatis` → `spring-mvc-mybatis`
- 含 `spring-boot-starter` + `mybatis-spring-boot` → `spring-boot-mybatis`
- 含 `spring-boot-starter-data-jpa` → `spring-boot-jpa`
- 含 `mybatis-plus-boot-starter` → `spring-boot-mybatis-plus`
- 無法判斷 → 詢問使用者手動選擇或自訂

#### 4-2. 引導填寫專案資訊

```
建立新專案，請填寫以下資訊：

  專案名稱：（必填）
  本機路徑：/Users/cheng/IdeaProjects/NewProject（已自動偵測）
  技術棧：spring-boot-mybatis（已自動偵測，Enter 確認或修改）
  Git Repo：https://github.com/xxx/yyy.git（已自動偵測，Enter 確認或修改）
  狀態：進行中（預設）

以下欄位可現在填寫，或稍後在 Notion 頁面補充：
  SIT 主機：（如 10.0.1.100，多台用換行分隔）
  UAT 主機：（如 10.0.1.200）
  正式環境主機：（如 AP1: 10.0.1.10, AP2: 10.0.1.11, WEB: 10.0.1.20）
  部署方式：（如 WAR 部署到 Tomcat、Docker、K8s 等）
  說明：（專案簡要描述）
```

#### 4-3. 在 Notion 建立專案

使用 `notion-create-pages` 在「專案資料庫」（Data Source ID 從設定檔取得）建立新條目：

| 欄位 | 值 |
|------|-----|
| 專案名稱 | 使用者填入 |
| 本機路徑 | `pwd` |
| 技術棧 | 自動偵測或使用者指定 |
| Git Repo | `git remote get-url origin` |
| 狀態 | `進行中`（預設） |
| SIT 主機 | 使用者填入（可空） |
| UAT 主機 | 使用者填入（可空） |
| 正式環境主機 | 使用者填入（可空） |
| 部署方式 | 使用者填入（可空） |
| 說明 | 使用者填入（可空） |

### 5. 同步更新所有設定檔

**重要**：必須同步更新所有存在的 Workflow 設定檔，確保 bug-workflow 和 feature-workflow 共用相同的專案路徑對應。

依序檢查並更新以下設定檔（所有存在的都要更新）：

1. `~/.claude-company/bug-workflow-config.md`
2. `~/.claude/bug-workflow-config.md`
3. `~/.claude-company/feature-workflow-config.md`
4. `~/.claude/feature-workflow-config.md`

在每個設定檔的「專案路徑對應」表中新增一列：

```markdown
| {專案名稱} | `{本機路徑}` | {說明} |
```

若是 feature-workflow 設定檔，還需包含技術棧欄位：

```markdown
| {專案名稱} | `{本機路徑}` | {技術棧} | {說明} |
```

**更新已存在的專案**（步驟 2 選擇「更新」時）：
- 使用 `notion-update-page` 更新 Notion 中的專案欄位
- 更新設定檔中該專案的對應列

### 6. 回傳結果

```
專案已新增到 Notion 專案資料庫！

  專案名稱：XXX
  本機路徑：/Users/cheng/IdeaProjects/NewProject
  技術棧：spring-boot-mybatis
  Git Repo：https://github.com/xxx/yyy.git

已同步更新設定檔：
  ✅ ~/.claude-company/bug-workflow-config.md
  ✅ ~/.claude-company/feature-workflow-config.md

現在可以在此目錄使用：
  /bug-start <問題簡述>       — 建立 Bug 條目（自動關聯此專案）
  /feature-start <功能簡述>   — 建立功能需求（自動關聯此專案）
```

---

## 邊界情況

- **設定檔不存在**：提示使用者先執行 `/bug-setup` 或 `/feature-setup`
- **專案資料庫 Data Source ID 不存在**：提示使用者重新執行 setup
- **已在設定檔中但 Notion 中找不到**：提示可能是 Notion 頁面被刪除，詢問是否重新建立
- **不在 Git repo 中**：Git Repo 欄位留空，其餘正常執行
- **`pwd` 匹配到多個專案**（子目錄關係）：列出候選讓使用者選擇
- **Notion API 失敗**：顯示錯誤訊息，已填入的設定檔變更仍保留
- **只裝了其中一個 workflow**：僅更新該 workflow 的設定檔，不報錯
- **技術棧無法自動偵測**（非 Java 專案等）：技術棧欄位留空或使用者自訂
