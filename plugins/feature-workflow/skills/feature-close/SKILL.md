---
name: feature-close
description: 功能開發結案，從 Git diff 擷取完整變更摘要、更新 Notion 頁面、同步功能設計庫。當使用者提到「feature-close」、「功能完成」、「結案」、「開發完成」時觸發此 Skill。
---

# feature-close — 功能結案

功能開發完成後，從 Git 擷取完整變更資訊，更新 Notion 功能頁面，並在「功能設計庫」同步建立設計文件索引。

---

## 設定檔

執行前依序檢查以下路徑，讀取第一個找到的設定檔：
1. `~/.claude-company/feature-workflow-config.md`（公司環境）
2. `~/.claude/feature-workflow-config.md`（個人環境）

若都不存在，提示使用者先執行 `/feature-setup`。

---

## 前置條件

- 已使用 `/feature-start` 建立功能條目
- 功能程式碼已 commit

---

## 流程

### 1. 從 Git 擷取完整變更

```bash
# 當前分支
git branch --show-current

# 功能分支所有 commit（相對於基礎分支）
git log --oneline $(git merge-base HEAD production)..HEAD

# 變更統計
git diff $(git merge-base HEAD production)..HEAD --stat

# 完整 diff（用於摘要化）
git diff $(git merge-base HEAD production)..HEAD
```

若使用者指定 commit 範圍，使用指定的範圍。

### 2. 定位目標功能 Notion 頁面

使用與 feature-update 相同的定位邏輯：
- 搜尋狀態為「進行中」、任務類型為「💬 功能要求」
- 優先以 Git branch 匹配「修復分支」欄位

選定後，使用 `notion-fetch` 取得頁面完整內容。

### 3. 互動式補充資訊

詢問使用者（若未在初始輸入中提供）：

1. **目標狀態**：`測試中`（預設）或 `已完成`

### 4. 產出分層變更摘要

根據 git diff 和專案 CLAUDE.md 中的架構描述，自動以分層方式摘要變更：

**自動分層邏輯**：
- 讀取 CLAUDE.md 中的 package 結構描述
- 將變更檔案按 package 歸類到各層
- 若 CLAUDE.md 無描述，從檔案路徑推斷（controller/ → Controller 層、service/ → Service 層 等）

產出格式：

```
### 變更摘要

**分支**：feature/xxx
**Commit 數**：N
**變更檔案數**：M（+A 行 / -B 行）

#### Controller 層
- `XxxController.java` — 新增 API 端點 GET /api/xxx、POST /api/xxx

#### Service 層
- `XxxService.java` — 新增業務邏輯介面
- `XxxServiceImpl.java` — 實作查詢、新增、更新邏輯

#### DAO 層
- `XxxMapper.java` — 新增 Mapper 介面
- `CustomXxxMapper.xml` — 複雜查詢 SQL

#### Model 層
- `Xxx.java` — 新增 POJO

#### 其他
- `xxx.sql` — 資料庫遷移 SQL
```

### 5. 更新 Notion 功能頁面

使用 `notion-update-page` 更新條目：

**Properties 更新**：

| 欄位 | 值 |
|------|-----|
| 狀態 | 使用者選擇（預設「測試中」） |
| 開發階段 | `測試中` |
| 修復分支 | 當前 Git branch（若原本為空） |

**Content 更新**：

1. 「📁 程式碼清單」區塊：
   - 新增檔案 = 從 diff 擷取新增的檔案
   - 修改檔案 = 從 diff 擷取修改的檔案

2. 「📝 開發日誌」區塊附加結案紀錄：
   ```
   ### [{日期}] 開發完成
   - **分支**：{branch}
   - **Commit 數**：{N}
   - **變更摘要**：
     {分層變更摘要}
   ```

### 6. 同步到功能設計庫

在「功能設計庫」資料庫建立一筆設計文件索引（Data Source ID 見設定檔）：

| 欄位 | 值 |
|------|-----|
| Name | 功能標題 |
| Tags | 從設定檔中的預設選項自動推測標籤（`API` / `報表` / `標籤` / `推播` / `排程` / `綁定` / `權限` / `Rich Menu` / `匯出匯入` / `Flex Message`），可多選 |
| 設計類型 | 根據頁面內容判斷：規格+DB+架構齊全→`完整設計`、僅規格→`規格書`、僅DB→`DB 設計`、僅架構→`架構設計` |
| 技術棧 | 設定檔中的技術棧 ID |
| 參考連結 | 任務追蹤工具的頁面 URL |
| 專案資料庫 | 同一專案 |

頁面內容為精簡版摘要：
```
**功能概述**：{需求描述摘要}

**技術規格**：{API 數量} 個 API

**DB 設計**：{表數量} 個表

**架構設計**：{類別數量} 個類別

**變更統計**：{N} 個 commit、{M} 個檔案（+A/-B 行）

**參考**：[完整設計文件]({Notion 連結})
```

若設定檔中「功能設計庫」ID 為空，則跳過此步驟。

### 7. 回傳結果

向使用者顯示：
- 更新後的 Notion 頁面連結
- 分層變更摘要
- 功能設計庫條目連結（若有同步）
- 提示後續操作（依專案 Git Flow 動態提示）：

讀取 CLAUDE.md 中的 Git Flow 描述，產出對應提示：

```
功能開發已結案！後續事項：

📋 測試驗證：
  • 在 Notion 頁面勾選測試計畫中的驗證項目

🔀 Git 合併（依專案 Git Flow）：
  • {根據 CLAUDE.md 中的 Git Flow 描述產生合併提示}
  • 例如：將 feature/xxx 合併至 LineBC-UAT 進行測試
  • 測試通過後從 production 建立 release/Prod_yyyyMMdd

💡 其他：
  • 若需補充文件，可使用 /feature-update
  • 若上線後發現問題，可建立 hotfix 分支
```

---

## 邊界情況

- **設定檔不存在**：提示使用者先執行 `/feature-setup` 完成初始設定
- **無 commit 可擷取**：提示使用者先 commit 程式碼
- **Notion 頁面內容與模板不符**：嘗試模糊匹配區塊標題，找不到則附加在頁面最後
- **diff 過大（> 500 行）**：僅摘要檔案清單和分層變更，不貼完整 diff
- **功能設計庫不存在或 ID 為空**：跳過同步，提示使用者可後續設定
- **CLAUDE.md 無 Git Flow 描述**：使用通用提示（合併到主分支進行測試）
