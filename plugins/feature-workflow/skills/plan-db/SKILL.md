---
name: plan-db
description: 產出資料庫設計，寫入 .spec/ 目錄，不呼叫 Notion API。當使用者提到「plan-db」、「DB 設計」、「資料庫設計」、「設計資料表」時觸發此 Skill。
---

# plan-db — 資料庫設計（零 Notion 呼叫）

讀取技術規格，啟動 Agent 產出資料庫表結構設計與 SQL 檔案。

---

## 前置條件

> **前置檢查**：參照 bug-workflow plugin 的 `references/prerequisites.md` 檢查 CLAUDE.md 是否存在。

- 適用類型：**Feature**
- 前置檔案：`spec.md`（建議但非必要，若不存在則從 README.md 需求描述直接設計）

---

## 流程

### 1. 定位活躍任務 + 讀取專案上下文

參照 `references/plan-common.md`。

### 2. 產出 DB 設計

使用 **Agent tool** 啟動 subagent（model: opus），prompt 指示如下：

**輸入來源**：
- 技術規格從 `.spec/{slug}/spec.md` 讀取
- 若 spec.md 不存在，提示建議先執行 `/plan-spec`，但允許從 README.md 需求描述直接設計

**輸出目標**：
- 設計文件 → `.spec/{slug}/db.md`
- SQL 檔案 → `.spec/{slug}/db.sql`（含 CREATE TABLE / INDEX / 範例資料 / Rollback SQL）

完成後更新 README.md 的 `status: DB 設計`。

### 3. 一致性驗證 + 更新日誌

參照 `references/plan-common.md`。

### 4. 回傳結果

```
DB 設計完成！

📁 產出檔案：.spec/{slug}/db.md, .spec/{slug}/db.sql
📊 狀態：DB 設計

後續可使用：
  • /plan-arch  — 架構設計
  • /plan-build — Agent Teams 產生程式碼
```
