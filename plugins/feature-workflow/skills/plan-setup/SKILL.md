---
name: plan-setup
description: Workflow 首次設定引導。自動偵測 Notion 資料庫、匯入 bug-workflow 共用 ID、設定專案對應與技術棧、可選安裝獨立 Agent。當使用者提到「plan-setup」、「setup」、「設定 workflow」、「初始化」時觸發此 Skill。
---

# plan-setup — Workflow 首次設定

互動式引導使用者完成 Feature Workflow Plugin 的初始設定，產出設定檔供其他 Skill 使用。

---

## 前置條件

- 已安裝 Notion MCP Server（Claude Code 可使用 `notion-search`、`notion-fetch` 等工具）
- 擁有 Notion Workspace 存取權限

---

## 流程

### 1. 決定設定檔位置並檢查是否已存在

**設定檔路徑規則**（依序檢查）：

1. 先檢查 `~/.claude-company/feature-workflow-config.md`（公司環境）
2. 再檢查 `~/.claude/feature-workflow-config.md`（個人環境）
3. 若都不存在 → 詢問使用者要儲存到哪裡：
   ```
   請選擇設定檔儲存位置：
   1. ~/.claude-company/feature-workflow-config.md（公司環境，推薦用於團隊共用 Notion Workspace）
   2. ~/.claude/feature-workflow-config.md（個人環境，推薦用於私人 Notion Workspace）
   ```
4. 若已存在 → 詢問使用者要「重新設定」還是「更新專案對應」

### 2. 檢查並匯入 bug-workflow 共用 ID

檢查 bug-workflow 設定檔是否存在（依序：`~/.claude-company/bug-workflow-config.md`、`~/.claude/bug-workflow-config.md`）。

若找到 bug-workflow 設定檔：
1. 擷取「任務追蹤工具」Data Source ID → 直接匯入
2. 擷取「專案資料庫」Data Source ID → 直接匯入
3. 擷取「專案對應」表 → 作為基礎，後續補充技術棧欄位
4. 向使用者顯示匯入結果

若未找到 → 進入步驟 3 完整設定。

### 3. 偵測 Notion 資料庫

#### 3-1. 搜尋/驗證「任務追蹤工具」

若已從 bug-workflow 匯入，使用 `notion-fetch` 驗證並檢查「開發階段」欄位：
- 若「開發階段」欄位已存在 → 繼續
- 若不存在 → 使用 `notion-update-data-source` 新增「開發階段」Select 欄位，選項值：
  `需求分析` / `規格設計` / `DB 設計` / `架構設計` / `開發中` / `程式碼審查` / `測試中`

若未從 bug-workflow 匯入，使用 `notion-search` 搜尋包含「任務追蹤」的資料庫。

同時檢查「難度」欄位（bug-workflow 可能未建立）：
- 若不存在 → 新增「難度」Select 欄位，選項值：`小` / `中` / `大`

#### 3-2. 搜尋「功能設計庫」

搜尋包含「功能」、「設計」的資料庫。找不到 → 詢問建立/指定/跳過。

#### 3-3. 偵測或建立「專案資料庫」

若已從 bug-workflow 匯入 → 驗證並補齊欄位（特別確認「技術棧」欄位）。

**專案資料庫標準欄位**：

| 欄位 | 類型 | 必要性 |
|------|------|--------|
| 專案名稱 | Title | 必要 |
| Git Repo | Text | 必要 |
| 技術棧 | Select | 必要 |
| SIT/UAT/正式主機 | Text | 選用 |
| 部署方式 | Text | 選用 |
| 狀態 | Status | 建議 |

### 4. 設定專案對應

> **專案新增/偵測邏輯統一由 `/project-add` 處理**。

設定檔產出後，自動詢問是否執行 `/project-add` 新增當前專案。

### 5. Agent 安裝（選用）

詢問是否安裝 4 個獨立 Agent（spec-analyst / db-designer / backend-designer / code-generator）。

### 6. 產出設定檔

以 `references/config.template.md` 為模板填入偵測結果。

### 7. 回傳結果

```
Workflow 設定完成！

設定檔位置：~/.claude-company/feature-workflow-config.md

開始使用：
  /plan-start <功能簡述>   — 建立任務
  /plan                     — 規劃（spec/db/arch）
  /plan-build               — 產生程式碼
  /plan-verify              — 驗收驗證
  /plan-review              — 程式碼審查
  /plan-close               — 結案
```

---

## 邊界情況

- **Notion MCP 未安裝**：提示使用者先安裝 Notion Plugin
- **Workspace 中有多個類似資料庫**：列出候選讓使用者選擇
- **bug-workflow 設定檔部分資訊不全**：僅匯入有效的 ID
- **設定檔被意外刪除**：重新執行 `/plan-setup` 即可重建
- **Agent 目標目錄已有同名檔案**：詢問是否覆蓋
