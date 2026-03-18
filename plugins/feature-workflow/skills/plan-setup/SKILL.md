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

搜尋包含「功能」、「設計」的資料庫。

**情境 A：找到現有資料庫**

用 `notion-fetch` 取得資料庫結構，驗證並補齊欄位（Name, Tags, 設計類型, 技術棧, 參考連結, 日期）。不移動既有資料庫。

**情境 B：找不到功能設計庫**

詢問使用者：
```
未找到「功能設計庫」資料庫，請選擇：
1. 建立新的「功能設計庫」（推薦，含標準欄位）
2. 指定一個現有資料庫
3. 跳過（/plan-close 結案時不同步設計庫）
```

若選擇建立，先決定 parent 位置：

1. **嘗試取得工作區頁面**：
   - 從 bug-workflow 設定檔讀取「CREW 工作區 → 工作區頁面 ID」
   - 若設定檔無此欄位 → 使用 `notion-search` 搜尋「CREW 工作區」頁面
   - 若找到工作區頁面 → **parent 設為工作區頁面**（不再詢問位置），記錄 `workspace_page_id`
   - 若找不到工作區頁面 → **退回原流程**（詢問要建立在哪個 Notion 頁面下）

2. 參照 bug-workflow plugin 的共用模版：
   `~/.claude-company/company-marketplace/plugins/bug-workflow/references/db-templates.md`「D. 功能設計庫」
3. 使用 `notion-create-database` 建立（**不含 Relation 欄位**）
4. 使用 `notion-update-data-source` 補上「專案資料庫」Relation：
   ```
   ADD COLUMN "專案資料庫" RELATION({專案DS_ID})
   ```
5. 使用 `notion-create-view` 建立 2 個 Views：
   - 預設 Table View（日期降序，顯示 Name, Tags, 設計類型, 技術棧, 日期）
   - 按專案看板（board，Group by 專案資料庫）
6. 記錄 Data Source ID

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

#### 3-4. 更新工作區頁面（追加功能設計庫）

若步驟 3-2 有建立或偵測到功能設計庫，且工作區頁面存在（`workspace_page_id` 有值）：

使用 `notion-update-page` 的 `update_content`，在工作區頁面中 Bug 知識庫（`🐛`）的 linked view **前面**插入功能設計庫的 linked view：

```markdown
<database data-source-url="collection://{功能設計庫DS_ID}" inline="true" icon="📐">功能設計庫</database>
```

最終頁面排版順序：
1. ✅ 任務追蹤工具
2. 📐 功能設計庫
3. 🐛 Bug 知識庫
4. 📂 專案資料庫

> **注意**：若工作區頁面中已有功能設計庫的 linked view（重複執行 setup），則跳過此步驟。
> 若工作區頁面不存在（`workspace_page_id` 為空），跳過此步驟。

### 4. 設定專案對應

> **專案新增/偵測邏輯統一由 `/project-add` 處理**。

設定檔產出後，自動詢問是否執行 `/project-add` 新增當前專案。

### 5. Agent 安裝（選用）

詢問是否安裝 4 個獨立 Agent（spec-analyst / db-designer / backend-designer / code-generator）。

### 6. Chrome DevTools MCP 安裝（選用）

若使用者計畫使用 `/plan-verify` 驗收驗證，詢問是否安裝：

```
是否安裝 Chrome DevTools MCP？（Google 官方維護，推薦）
1. 安裝（推薦，29 種工具，持續維護）
2. 跳過（使用內建 cdp.mjs，需 Node.js 22+）
```

若選擇安裝：
```bash
claude mcp add chrome-devtools --scope user -- \
  npx chrome-devtools-mcp@latest --autoConnect
```

提示安裝後**重啟 Claude Code**。

### 7. 產出設定檔

以 `references/config.template.md` 為模板填入偵測結果。

**新增欄位**：若有取得工作區頁面 ID，在設定檔中填入「CREW 工作區」區段：

```markdown
## CREW 工作區

| 項目 | 值 |
|------|-----|
| 工作區頁面 ID | `{workspace_page_id}` |
| 工作區頁面 URL | `https://www.notion.so/{workspace_page_id}` |
```

### 8. 回傳結果

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

## Gotchas

- **匯入 bug-workflow ID 時不要盲目信任**：bug-workflow 設定檔中的 Data Source ID 可能過期（資料庫被刪除或 Workspace 變更）。匯入後務必用 `notion-fetch` 驗證每個 ID 仍然有效，無效的 ID 要重新搜尋。
- **「開發階段」欄位的 Select 選項建立順序**：`notion-update-data-source` 新增 Select 欄位時，選項的顯示順序等於建立順序。所以 `需求分析` 要第一個加，`測試中` 最後加，確保在 Notion UI 中按流程階段排列。
- **功能設計庫搜尋關鍵字衝突**：搜尋「功能」「設計」可能命中使用者的其他資料庫（如「功能需求清單」）。額外比對是否有「設計類型」或「技術棧」欄位來確認是目標資料庫。
- **Chrome DevTools MCP 安裝後需重啟**：使用者容易忘記重啟 Claude Code，導致後續 `/plan-verify` 找不到 MCP 工具而失敗。安裝後要明確提醒「必須重啟 Claude Code」。

---

## 邊界情況

- **Notion MCP 未安裝**：提示使用者先安裝 Notion Plugin
- **Workspace 中有多個類似資料庫**：列出候選讓使用者選擇
- **bug-workflow 設定檔部分資訊不全**：僅匯入有效的 ID
- **設定檔被意外刪除**：重新執行 `/plan-setup` 即可重建
- **Agent 目標目錄已有同名檔案**：詢問是否覆蓋
