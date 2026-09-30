# 功能開發 Notion 頁面模板

此模板由 `/plan-start` 使用，建立新功能時自動填入頁面內容（共 **5 個區塊**）。

`/plan-sync`（中途同步）與 `/plan-close`（結案同步）都以這裡的**區塊標題**為契約，
把 `.spec/{slug}/plan.md` 與 `deploy.sql` 的內容寫進對應區塊 —— 改標題就要同步改那兩個 skill。對「📋 需求描述」而言，`### 原始需求` 與 `### 確認後任務描述` 是 intake-owned immutable prefix；sync/close 只能更新其後的 spec projection。

---

## 區塊 ↔ 來源對照（v2）

| 區塊 | 內容來源 | 寫入者 |
|------|---------|--------|
| 📋 需求描述 | 使用者的**原始需求原文**＋Human 確認後的 refined brief（建立時填，plan.md 不收原文）＋ plan.md「目標與範圍」「驗收條件」 | plan-start（intake）／plan-sync／plan-close |
| 📐 技術規格 | plan.md「決策紀錄」「已知取捨與風險」「指路」（錨點原樣，不展開內容） | plan-sync／plan-close |
| 🗄️ 資料庫設計 | `deploy.sql` 全文（唯一 SQL 事實來源）寫入「遷移 SQL」 | plan-sync／plan-close |
| 📁 程式碼清單 | `git diff --name-status` ＋ 分層變更摘要 | plan-close |
| 📝 開發日誌 | plan.md「檢查報告摘要」節（review／security／verify 各一行）＋ 結案紀錄（含 `verified_at_commit`） | plan-close |

**另有一個不在模板內的區塊**：「🚀 部署狀態」只由 `/plan-close` 在 `deploy.sql` 存在時建立
（每筆 Step 預設「待執行」），供 `/plan-deploy-confirm` 回報執行狀態時讀寫。`/plan-sync` 不建立它。

🔴 **已移除的區塊**（v2 已無來源，不要加回來）：

| 舊區塊 | 為什麼移除 |
|--------|-----------|
| 🏗️ 架構設計 | 分層圖／類別清單／介面定義 100% 是程式碼事實，改由「📐 技術規格」的決策條目＋錨點承接 |
| 🚀 上線前置作業 | `deploy-checklist.md` 已廢除（是 `deploy.sql` 的 derived view）；部署進度記在 `state.json` 的 `deploy` |
| 🧪 測試計畫 | 驗收條件在「📋 需求描述」的 `AC-n`，驗證結果在「📝 開發日誌」的摘要行，兩處已涵蓋 |

---

## 模板內容

```markdown
## 📋 需求描述
### 原始需求
（ORIGINAL_REQUEST 原封不動貼在此處）

### 確認後任務描述
（REFINED_REQUEST；已由 Human 明確確認）

### 目標與範圍
（plan.md「目標與範圍」projection；plan-sync / plan-close 只更新此段）

### 驗收條件
（plan.md「驗收條件」projection；AC-n 原樣；plan-sync / plan-close 只更新此段）

---
## 📐 技術規格
### 決策紀錄（為什麼這樣做、否決了什麼）
### 已知取捨與風險
### 指路（程式碼錨點）

---
## 🗄️ 資料庫設計
### 遷移 SQL
（deploy.sql 全文，由 plan-sync / plan-close 寫入）

---
## 📁 程式碼清單
### 變更檔案（git diff）
### 分層變更摘要

---
## 📝 開發日誌
### 檢查報告摘要
### [{日期}] 開始開發
```
