---
name: plan-close
description: 一次性批次同步 .spec/ 設計文件到 Notion，更新狀態、同步知識庫、提交設計文件到 Git。當使用者提到「plan-close」、「結案」、「完成」時觸發此 Skill。
---

# plan-close — 統一結案（批次 Notion 同步）

將 `.spec/{slug}/` 中的所有設計文件一次性批次同步到 Notion，更新狀態，同步到知識庫，並提交設計文件到 Git。**整個流程僅 3-5 次 Notion API 呼叫**。

---

## 設定檔

執行前依序檢查以下路徑，讀取第一個找到的設定檔：
1. `~/.claude-company/feature-workflow-config.md`（公司環境）
2. `~/.claude/feature-workflow-config.md`（個人環境）

Bug 類型還需：
1. `~/.claude-company/bug-workflow-config.md`
2. `~/.claude/bug-workflow-config.md`

---

## 前置條件

- 已使用 `/plan-start` 建立任務
- 已完成規劃和開發（`.spec/{slug}/` 下有設計文件）
- 程式碼已 commit

---

## 流程

### 1. 定位活躍任務

與 `/plan` 相同邏輯。讀取 `.spec/{slug}/README.md` 取得 `type`、`notion_page_id`、`notion_url`。

### 2. 收集所有本地設計文件

掃描 `.spec/{slug}/` 目錄，列出所有可用文件：

**Feature 類型**：

| 檔案 | Notion 區塊 | 存在？ |
|------|------------|--------|
| spec.md | 📐 技術規格 | ✅/❌ |
| db.md | 🗄️ 資料庫設計 | ✅/❌ |
| arch.md | 🏗️ 架構設計 | ✅/❌ |
| files.md | 📁 程式碼清單 | ✅/❌ |
| review.md | 📋 程式碼審查（新增區塊） | ✅/❌ |
| verify.md | 🧪 驗證報告（新增區塊） | ✅/❌ |
| log.md | 📝 開發日誌 | ✅/❌ |

**Bug 類型**：

| 檔案 | Notion 區塊 | 存在？ |
|------|------------|--------|
| investigation.md | 🔍 調查過程 | ✅/❌ |
| root-cause.md | 🧠 根因分析 | ✅/❌ |
| fix.md | ✅ 修復方案 | ✅/❌ |
| log.md | 📝 經驗教訓 | ✅/❌ |

### 3. 從 Git 擷取變更摘要

從 Git diff 擷取變更摘要：

```bash
git branch --show-current
git log --oneline $(git merge-base HEAD production)..HEAD
git diff $(git merge-base HEAD production)..HEAD --stat
git diff $(git merge-base HEAD production)..HEAD
```

根據 CLAUDE.md 的架構描述，產出分層變更摘要。

### 4. 智慧判斷目標狀態

狀態推斷邏輯：
- 使用者輸入含「完成」、「done」、「上線」、「結案」→ `已完成`
- 含「測試」、「QA」→ `測試中`
- 無法判斷 → 詢問，預設 `測試中`

### 5. 一次性 Notion 批次更新

**5-1. Fetch 現有頁面**（1 次 `notion-fetch`）

使用 `notion_page_id`（從 README.md 取得）fetch 頁面。

**5-2. 更新頁面內容**（1 次 `notion-update-page` content）

將所有設計文件內容組合成一次 `update_content` 操作：

**Feature 類型**：

```
📐 技術規格 區塊 ← spec.md 內容
🗄️ 資料庫設計 區塊 ← db.md 內容
🏗️ 架構設計 區塊 ← arch.md 內容
📁 程式碼清單 區塊 ← files.md 內容 + Git diff 產出的分層變更摘要
📝 開發日誌 區塊 ← 附加結案紀錄：
  ### [{日期}] 開發完成
  - **分支**：{branch}
  - **Commit 數**：{N}
  - **變更摘要**：{分層變更摘要}

若 review.md 存在，在「📝 開發日誌」前插入：
📋 程式碼審查 區塊 ← review.md 內容

若 verify.md 存在，在「📋 程式碼審查」後（或「📝 開發日誌」前）插入：
🧪 驗證報告 區塊 ← verify.md 內容
```

**Bug 類型**：

```
🔍 調查過程 區塊 ← investigation.md 內容
🧠 根因分析 區塊 ← root-cause.md 內容
✅ 修復方案 區塊 ← fix.md 內容 + Git diff 分層摘要
📝 經驗教訓 區塊 ← log.md 或自動產生的經驗教訓
```

**5-3. 更新 Properties**（1 次 `notion-update-page` properties）

**Feature**：

| 欄位 | 值 |
|------|-----|
| 狀態 | 步驟 4 判斷結果 |
| 開發階段 | `測試中` |
| 修復分支 | 當前 Git branch |

**Bug**：

| 欄位 | 值 |
|------|-----|
| 狀態 | 步驟 4 判斷結果 |
| 根因分類 | 從 root-cause.md 推斷（邏輯錯誤/資料異常/設定問題/第三方API/效能/權限/前端UI） |
| 修復分支 | 當前 Git branch |

### 6. 同步到知識庫

**Feature → 功能設計庫**（1 次 `notion-create-pages`）

同步邏輯：

| 欄位 | 值 |
|------|-----|
| Name | 功能標題 |
| Tags | 自動推測（API/報表/標籤/推播/排程 等） |
| 設計類型 | 依文件齊全度判斷 |
| 技術棧 | 設定檔中的技術棧 ID |
| 參考連結 | Notion 頁面 URL |
| 專案資料庫 | 同一專案 |

**Bug → Bug 知識庫**（1 次 `notion-create-pages`）

複用 `bug-close` 的同步邏輯：

| 欄位 | 值 |
|------|-----|
| Name | Bug 標題 |
| Tags | 自動推測 |
| 難易度 | 依修改檔案數和行數判斷 |
| 專案資料庫 | 同一專案 |
| 參考連結 | Notion 頁面 URL |

### 7. Feature-Bug 關聯（僅 Bug 且有 related_feature）

若 README.md 中 `related_feature` 不為空：

1. 從 `.spec/{related_feature}/README.md` 取得 `notion_page_id`
2. `notion-fetch` 取得關聯 Feature 的 Notion 頁面（1 次）
3. 在「📝 開發日誌」區塊追加：

```
### [{日期}] 🔴 相關 Bug
- Bug: {Bug 名稱}（{Bug Notion URL}）
- 根因: {root-cause.md 摘要}
- 修復: {fix.md 摘要}
```

4. `notion-update-page` 更新 Feature 頁面（1 次）

### 8. 提交 .spec/ 設計文件到 Git

將最終版本的設計文件提交：

1. 在 `.gitignore` 中排除此 slug 的目錄：
   - 追加 `!.spec/{slug}/` 到 `.gitignore`

2. Git 操作：
   ```bash
   git add .spec/{slug}/
   git commit -m "docs: 新增 {slug} 設計文件"
   ```

### 9. 更新 _index.md

將任務從「進行中」移至「已完成」區段：

```markdown
## 已完成

| slug | 類型 | 名稱 | 完成日期 | Notion |
|------|------|------|---------|--------|
| {slug} | {type} | {name} | {日期} | [連結]({url}) |
```

**不刪除 `.spec/{slug}/` 目錄**，保留供未來 Bug 關聯匹配。

### 10. 回傳結果

```
結案完成！

📊 Notion 頁面：{URL}（已更新）
📚 知識庫：{知識庫條目 URL}（已同步）
{📎 Feature 關聯：已更新 {related_feature} 的開發日誌}
📁 設計文件：已提交到 Git

Notion API 呼叫統計：{N} 次（fetch: 1, update: 2, create: 1{, 關聯更新: 2}）

後續事項：
  📋 測試驗證：在 Notion 頁面勾選驗證項目
  🔀 Git 合併：{根據 CLAUDE.md Git Flow 產出合併建議}
```

---

## 邊界情況

- **notion_page_id 為空**：建議先用 `/plan-sync` 建立 Notion 條目
- **無設計文件**：僅更新 Properties 和開發日誌
- **diff 過大（> 500 行）**：僅摘要檔案清單和分層變更
- **知識庫 ID 為空**：跳過知識庫同步
- **related_feature 的 Notion 頁面不存在**：跳過關聯更新，提示使用者
- **Notion API 失敗**：顯示已完成和失敗的步驟，建議用 `/plan-sync` 重試
- **CLAUDE.md 無 Git Flow 描述**：使用通用提示
