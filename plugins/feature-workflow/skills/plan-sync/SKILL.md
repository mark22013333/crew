---
name: plan-sync
description: 手動中途同步 .spec/ 目錄的當前進度到 Notion。按需使用，不在常規流程中。當使用者提到「plan-sync」、「同步」、「sync」時觸發此 Skill。
---

# plan-sync — 手動中途同步

將 `.spec/{slug}/` 目錄的當前進度同步到 Notion。用於需要在結案前查看 Notion 頁面、或與團隊成員分享進度的場景。**不在常規流程中**，按需使用。

---

## 設定檔

執行前依序檢查以下路徑，讀取第一個找到的設定檔：
1. `~/.claude-company/feature-workflow-config.md`（公司環境）
2. `~/.claude/feature-workflow-config.md`（個人環境）

> **前置檢查**：參照 bug-workflow plugin 的 `references/prerequisites.md` 執行完整前置檢查（CLAUDE.md + 設定檔 + 專案註冊）。

---

## 使用方式

```
/plan-sync                 # 同步當前任務的所有文件
/plan-sync spec            # 只同步 spec.md
/plan-sync db              # 只同步 db.md + db.sql
/plan-sync arch            # 只同步 arch.md
```

---

## 流程

### 1. 定位活躍任務

與 `/plan` 相同邏輯。讀取 `.spec/{slug}/README.md` 取得 `type` 和 `notion_page_id`。

### 2. 檢查 Notion 頁面

若 `notion_page_id` 為空（例如 `/plan-start` 時 Notion 建立失敗）：
- 詢問使用者是否要補建 Notion 條目
- 若是，執行與 `/plan-start` 步驟 5 相同的建立邏輯
- 建立後更新 README.md 的 `notion_page_id` 和 `notion_url`

### 3. 確定同步範圍

掃描 `.spec/{slug}/` 目錄，列出可同步的檔案：

```
可同步的文件：
  ✅ spec.md → 📐 技術規格
  ✅ db.md   → 🗄️ 資料庫設計
  ❌ arch.md → 🏗️ 架構設計（不存在）
  ✅ review.md → 📋 程式碼審查

同步所有？[Y/n] 或輸入要同步的項目（如 spec db）
```

若使用者指定了子命令（如 `/plan-sync spec`），只同步指定項目。

### 4. 執行同步

**4-1. Fetch 現有頁面**（1 次 `notion-fetch`）

取得頁面現有內容，避免覆蓋其他區塊。

**4-2. 更新內容**（1 次 `notion-update-page` content）

將選定的本地文件內容寫入對應 Notion 區塊。

**Feature 類型的對應**：

| 本地檔案 | Notion 區塊 |
|---------|------------|
| spec.md | 📐 技術規格 |
| db.md | 🗄️ 資料庫設計 |
| arch.md | 🏗️ 架構設計 |
| files.md | 📁 程式碼清單 |
| review.md | 在「📝 開發日誌」前插入「📋 程式碼審查」 |
| log.md | 📝 開發日誌（附加） |

**Bug 類型的對應**：

| 本地檔案 | Notion 區塊 |
|---------|------------|
| investigation.md | 🔍 調查過程 |
| root-cause.md | 🧠 根因分析 |
| fix.md | ✅ 修復方案 |
| log.md | 📝 經驗教訓（附加） |

**4-3. 更新 Properties**（1 次 `notion-update-page` properties）

根據 README.md 的 `status` 更新：

| status | 開發階段 |
|--------|---------|
| 需求分析 | 需求分析 |
| 規格設計 | 規格設計 |
| DB 設計 | DB 設計 |
| 架構設計 | 架構設計 |
| 開發中 | 開發中 |
| 程式碼審查 | 程式碼審查 |

### 5. 回傳結果

```
同步完成！

📊 Notion 頁面：{URL}
📄 已同步：spec.md, db.md
📊 Notion API 呼叫：{N} 次

提示：此為中途同步，結案時請使用 /plan-close 做完整同步。
```

---

## 邊界情況

- **notion_page_id 為空**：引導補建 Notion 條目
- **無文件可同步**：提示先執行 `/plan` 產出文件
- **Notion 頁面內容與模板不符**：嘗試模糊匹配區塊標題，找不到則附加在頁面最後
- **Notion API 失敗**：顯示具體錯誤，建議檢查網路或稍後重試
