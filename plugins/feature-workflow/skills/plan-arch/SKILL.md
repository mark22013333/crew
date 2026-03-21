---
name: plan-arch
description: 產出架構設計，寫入 .spec/ 目錄，不呼叫 Notion API。當使用者提到「plan-arch」、「架構設計」、「架構」、「arch」時觸發此 Skill。
---

# plan-arch — 架構設計（零 Notion 呼叫）

讀取技術規格和 DB 設計，啟動 Agent 產出架構設計（Mermaid 架構圖、類別清單、介面定義、設計模式）。

---

## 前置條件

> **前置檢查**：參照 bug-workflow plugin 的 `references/prerequisites.md` 檢查 CLAUDE.md 是否存在。

- 適用類型：**Feature**
- 前置檔案：`spec.md` + `db.md`（建議但非必要，若不存在則從 README.md 需求描述設計）

---

## 流程

### 1. 定位活躍任務 + 讀取專案上下文

參照 `references/plan-common.md`。

### 2. 產出架構設計

使用 **Agent tool** 啟動 subagent（model: opus），prompt 指示如下：

**輸入來源**：
- 技術規格從 `.spec/{slug}/spec.md` 讀取
- DB 設計從 `.spec/{slug}/db.md` 讀取
- 若檔案不存在，允許從 README.md 需求描述設計

**輸出目標**：
- 架構設計 → `.spec/{slug}/arch.md`（含 Mermaid 架構圖、類別清單、介面定義、設計模式）

完成後更新 README.md 的 `status: 架構設計`。

### 3. 一致性驗證 + 更新日誌

參照 `references/plan-common.md`。

### 4. 回傳結果

```
架構設計完成！

📁 產出檔案：.spec/{slug}/arch.md
📊 狀態：架構設計

後續可使用：
  • /plan-build  — Agent Teams 產生程式碼
  • /plan-review — Agent Teams 審查
```
