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
| `/bug-search <關鍵字>` | 搜尋過往 Bug 解法與經驗 |

## 前置條件

1. **Notion Plugin** — 需先安裝 Notion MCP Server
   ```
   claude plugin install Notion
   ```

2. **Notion Workspace** — 需有以下資料庫（或由 `/bug-setup` 引導建立）：
   - **任務追蹤工具**：Bug 生命週期管理（主要資料庫）
   - **Bug 知識庫**（選用）：精簡索引，結案時自動同步
   - **專案資料庫**：管理專案與本機路徑對應

3. **Notion 權限** — Claude Code 需授權以下 Notion 工具：
   - `notion-search`、`notion-fetch`（搜尋與讀取）
   - `notion-create-pages`（建立 Bug 條目）
   - `notion-update-page`（更新頁面內容與屬性）
   - `notion-update-data-source`（新增欄位，僅 setup 時使用）

## 安裝

```bash
# 1. 加入 Marketplace（一次性）
claude marketplace add --github mark22013333/bug-workflow

# 2. 安裝
claude plugin install bug-workflow
```

## 首次設定

安裝後執行 `/bug-setup`，自動完成：
1. 選擇設定檔儲存位置（公司環境或個人環境）
2. 偵測 Notion Workspace 中的資料庫
3. 驗證並補齊必要欄位（狀態、根因分類、修復分支等）
4. 設定當前專案目錄與 Notion 專案的對應
5. 產出設定檔

## 工作流程

```
發現 Bug → /bug-start 建立條目
    │
    ├── /bug-update 補充 Log、SQL、判斷
    │
    ├── 修復並 commit
    │
    ├── /bug-close 結案（自動擷取 diff → 更新 Notion → 同步知識庫）
    │
    └── 上線後復發？ → /bug-update reopen → 繼續調查 → /bug-close 二次結案
```

## 跨專案支援

Plugin 透過 `pwd` 自動偵測當前工作目錄，比對 Notion 專案資料庫中的「本機路徑」欄位，自動關聯到正確的專案。

在不同專案目錄下執行 `/bug-start`，會自動對應不同的 Notion 專案，無需手動切換。

新增專案對應：重新執行 `/bug-setup` 選擇「更新專案對應」即可。

## 設定檔

設定檔儲存位置由使用者在 `/bug-setup` 時選擇：

| 環境 | 路徑 | 適用場景 |
|------|------|---------|
| 公司 | `~/.claude-company/bug-workflow-config.md` | 團隊共用 Notion Workspace |
| 個人 | `~/.claude/bug-workflow-config.md` | 私人 Notion Workspace |

Skill 執行時會依序檢查公司 → 個人路徑，讀取第一個找到的設定檔。

設定檔包含：
- Notion 資料庫 Data Source ID
- 專案路徑對應表
- 欄位對照表

可手動編輯此檔案，或透過 `/bug-setup` 重新設定。
