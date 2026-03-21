---
name: plan
description: 完整規劃串接器（自動依序執行 plan-spec → plan-db → plan-arch），所有產出寫入 .spec/ 目錄，不呼叫 Notion API。當使用者提到「plan」、「完整規劃」、「全部規劃」時觸發此 Skill。
---

# plan — 完整規劃串接器（零 Notion 呼叫）

自動依序執行 `/plan-spec` → `/plan-db` → `/plan-arch`，每個階段完成後向使用者展示摘要，確認後再執行下一個。

> **單獨執行某一階段**：請直接使用對應的獨立指令（如 `/plan-spec`、`/plan-db`、`/plan-arch`）。

---

## 使用方式

```
/plan                      # 自動判斷類型，依序執行完整規劃
```

---

## 流程

### 1. 定位活躍任務

參照 `references/plan-common.md`。

### 2. 依序執行

1. **`/plan-spec`**（技術規格）→ 展示摘要，確認後繼續
2. **`/plan-db`**（若 spec 判斷 DB_REQUIRED=true）→ 展示摘要，確認後繼續
3. **`/plan-arch`**（架構設計）

使用者可在任何階段中斷。

> Bug 類型的調查與修復由 bug-workflow 處理（`/bug-start` → `/bug-update` → `/bug-close`）。

### 3. 回傳結果

```
完整規劃完成！

📁 產出檔案：
  • .spec/{slug}/spec.md
  • .spec/{slug}/db.md + db.sql
  • .spec/{slug}/arch.md
📊 狀態：架構設計

後續可使用：
  • /plan-build  — Agent Teams 產生程式碼
  • /plan-review — Agent Teams 審查
  • /plan-status — 查看任務狀態
```

---

## 相關指令

| 指令 | 說明 | 產出檔案 |
|------|------|---------|
| `/plan-spec` | 技術規格書 | spec.md |
| `/plan-db` | 資料庫設計 | db.md + db.sql |
| `/plan-arch` | 架構設計 | arch.md |
