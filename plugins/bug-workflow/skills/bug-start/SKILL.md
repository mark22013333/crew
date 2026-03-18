---
name: bug-start
description: 在 Notion「任務追蹤工具」建立 Bug 條目並填入標準化模板。當使用者提到「建立 bug」、「記錄 bug」、「bug 通報」、「bug-start」、「開始修 bug」時觸發此 Skill。
---

# Bug Start — 建立 Bug 條目與標準化文件

在 Notion「任務追蹤工具」資料庫建立一筆 Bug 條目，自動填入標準化頁面模板，並關聯對應專案。

---

## 設定檔

執行前依序檢查以下路徑，讀取第一個找到的設定檔：
1. `~/.claude-company/bug-workflow-config.md`（公司環境）
2. `~/.claude/bug-workflow-config.md`（個人環境）

若都不存在，提示使用者先執行 `/bug-setup` 完成初始設定。

---

## 流程

> **前置檢查**：參照 `references/prerequisites.md` 執行完整前置檢查（CLAUDE.md + 設定檔 + 專案註冊）。

### 1. 解析使用者輸入

使用者會以以下格式觸發：

```
/bug-start <問題簡述>
```

從使用者輸入中擷取：
- **問題簡述**（必填）：作為「任務名稱」

### 2. 偵測環境資訊（自動專案對應）

取得 branch 名稱、當前工作目錄與 Git Repo 識別碼：

```bash
# 分支名稱
git branch --show-current 2>/dev/null || echo ""

# 當前工作目錄
pwd

# Git 遠端 URL（用於自動對應 Notion 專案）
git remote get-url origin 2>/dev/null || echo ""
```

**Git Repo 識別碼解析規則**：

從 `git remote get-url origin` 取得遠端 URL 後，解析為識別碼：
- Git host 含 `intumit`（公司 GitLab）→ 只取 `{group}/{repo}`，例如 `FUB03P2402/PushAPIService`
- 其他（GitHub 等）→ 加上 host：`{host}/{group}/{repo}`，例如 `github.com/mark22013333/crew`
- 解析時去掉 `.git` 後綴，支援 HTTPS / SSH 格式

**自動專案對應邏輯**：

1. 執行 `git remote get-url origin` 取得 Git 遠端 URL
2. 解析為 Git Repo 識別碼（host 含 `intumit` → `{group}/{repo}`，其他 → `{host}/{group}/{repo}`，去除 `.git` 後綴）
3. 讀取設定檔中「專案對應」表，精確匹配「Git Repo」欄位
4. 若匹配成功 → 自動選定該專案，不再詢問
5. 若不在 Git repo 或匹配失敗 → 進入互動式選擇

若設定檔中無對應，也可用 `notion-search` 搜尋 Notion「專案資料庫」（Data Source ID 見設定檔），找「Git Repo」欄位與識別碼匹配的專案。

### 3. 互動式補充資訊

若使用者未在初始輸入中提供以下資訊，依序詢問：

1. **所屬專案**（若自動偵測失敗）：搜尋 Notion「專案資料庫」，列出「進行中」的專案供選擇
2. **環境**（預設「正式」）：`測試` / `UAT` / `正式`
3. **優先順序**（預設「中」）：`高` / `中` / `低`

使用者可在初始輸入中直接指定，例如：
```
/bug-start SSO登入找不到使用者 正式 高
```

### 4. 建立 Notion 條目

使用 `notion-create-pages` 在「任務追蹤工具」資料庫建立新條目：

**Data Source ID**：從設定檔的「任務追蹤工具」取得

**Properties**：

| 欄位 | 值 |
|------|-----|
| 任務名稱 | 使用者提供的問題簡述 |
| 任務類型 | `["🐞 錯誤"]` |
| 狀態 | `進行中` |
| 優先順序 | 使用者選擇（預設「中」） |
| 環境 | 使用者選擇（預設「正式」） |
| 修復分支 | Git branch 名稱（若有） |
| 專案資料庫 | 關聯的專案頁面 URL |

### 5. 填入頁面模板

頁面的 content 使用以下標準模板：

```
## 🔴 問題描述
- **通報來源**：
- **發生時間**：{當前日期時間}
- **重現步驟**：
  1. ...
  2. ...
- **預期行為**：
- **實際行為**：
- **錯誤截圖**：

---

## 🔍 調查過程
### 關鍵 Log

### 相關 SQL 查詢

### 初步判斷

---

## 🧠 根因分析
- **問題根因**：
- **問題檔案**：
- **問題程式碼**：

---

## ✅ 修復方案
- **修改檔案清單**：
- **修改說明**：
- **修改後程式碼**：
- **修復 Commit**：
- **修復分支**：

---

## 🧪 驗證
- [ ] 本地測試通過
- [ ] UAT 驗證通過
- [ ] 正式環境確認
- [ ] 通報者確認問題已解決

---

## 📝 經驗教訓
- **學到什麼**：
- **如何預防**：
```

若使用者在初始輸入中已提供問題描述內容，將其預填入「問題描述」區塊的「實際行為」欄位。

### 6. 回傳結果

向使用者回傳：
- Notion 頁面連結
- 建立的條目摘要（任務名稱、專案、環境、優先順序）
- 提示後續可用指令：
  ```
  Bug 條目已建立！後續可使用：
  • /bug-update <內容>  — 補充調查資訊（Log、SQL、判斷等）
  • /bug-close          — 修復完成後結案
  • /bug-search <關鍵字> — 搜尋過往類似 Bug 的解法
  ```

---

## Gotchas

- **專案資料庫 Relation 值是頁面 URL，不是名稱**：`notion-create-pages` 的 Relation 欄位需要填入「被關聯頁面的 URL」（如 `https://www.notion.so/xxx`），不是填專案名稱字串。填錯格式會靜默失敗，條目建立成功但 Relation 為空。
- **任務類型是 Multi-select 不是 Select**：值必須用陣列格式 `["🐞 錯誤"]`，不是字串 `"🐞 錯誤"`。用字串格式不會報錯但會建立新的標籤。
- **emoji 是欄位值的一部分**：「🐞 錯誤」、「💬 功能要求」、「💅 細調」中的 emoji 是必要的，不能省略，否則會建立一個新的 Select 選項。
- **Git Repo 識別碼比對必須精確**：`FUB03P2402/LineBC` 和 `FUB03P2402/linebc` 是不同的識別碼。比對時使用原始大小寫，不做 case-insensitive matching。

---

## 邊界情況

- **設定檔不存在**：提示使用者先執行 `/bug-setup` 完成初始設定
- **不在 Git repo 中**：跳過分支與專案自動偵測，修復分支留空；進入互動式選擇專案
- **使用者未指定專案**：列出進行中的專案供選擇；若只有一個專案則自動選定
- **Notion API 失敗**：顯示錯誤訊息，建議使用者手動在 Notion 建立
