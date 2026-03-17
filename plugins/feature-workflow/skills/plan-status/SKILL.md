---
name: plan-status
description: 列出 .spec/ 目錄中所有活躍和已完成的任務，純本地操作不呼叫 Notion。當使用者提到「plan-status」、「狀態」、「任務列表」時觸發此 Skill。
---

# plan-status — 查看任務狀態

純本地操作，讀取 `.spec/_index.md` 和各任務的 `README.md`，格式化顯示所有任務狀態。**不呼叫任何 Notion API**。

> **前置檢查**：參照 bug-workflow plugin 的 `references/prerequisites.md` 檢查 CLAUDE.md 是否存在。

---

## 使用方式

```
/plan-status               # 列出所有任務
/plan-status --active      # 只列出進行中的任務
/plan-status --detail      # 詳細模式，顯示每個任務的設計文件完成度
/plan-status --cleanup     # 清除超過 N 天的已完成任務
```

---

## 流程

### 1. 檢查 .spec/ 目錄

若 `.spec/` 目錄不存在或為空 → 提示使用者先執行 `/plan-start`。

### 2. 掃描任務

讀取 `.spec/_index.md`。若 `_index.md` 不存在或不完整，從各子目錄的 `README.md` 重建：

```bash
# 掃描所有 slug 目錄
ls -d .spec/*/
```

對每個目錄，讀取 `README.md` 的 YAML frontmatter 取得：
- type、name、slug、status、branch、notion_url、created

### 3. 格式化輸出

#### 基本模式

```
📋 任務狀態

## 進行中（{N} 個）

| # | 類型 | 名稱 | 狀態 | 分支 | 建立日期 |
|---|------|------|------|------|---------|
| 1 | 🔧 feature | 推播標籤查詢 | 架構設計 | feature/push-tag-query | 2026-03-16 |
| 2 | 🐞 bug | SSO 登入錯誤 | 調查中 | hotfix/sso-login-fix | 2026-03-17 |

## 已完成（{N} 個）

| # | 類型 | 名稱 | 完成日期 |
|---|------|------|---------|
| 1 | 🔧 feature | 訂閱推播統計 | 2026-03-10 |
```

#### 詳細模式（--detail）

```
📋 任務詳細狀態

### 1. 🔧 推播標籤查詢（feature/push-tag-query）
   狀態：架構設計
   Notion：https://www.notion.so/xxx
   設計文件：
     ✅ README.md（需求描述）
     ✅ spec.md（技術規格 — 3 個 API、5 項業務規則）
     ✅ db.md + db.sql（2 個表、3 個索引）
     ✅ arch.md（8 個類別、2 個設計模式）
     ❌ files.md（待 /plan-build）
     ❌ review.md（待 /plan-review）
     📝 log.md（3 筆紀錄）

### 2. 🐞 SSO 登入錯誤（hotfix/sso-login-fix）
   狀態：調查中
   Notion：https://www.notion.so/yyy
   關聯 Feature：推播標籤查詢
   設計文件：
     ✅ README.md（問題描述）
     ✅ investigation.md（含 Log 和 SQL）
     ❌ root-cause.md（待 /plan root-cause）
     ❌ fix.md（待 /plan fix）
```

### 4. 清理模式（--cleanup）

```
以下已完成任務超過 30 天：

| # | 名稱 | 完成日期 | 天數 |
|---|------|---------|------|
| 1 | 訂閱推播統計 | 2026-02-10 | 34 天 |

是否清除？（會刪除 .spec/ 目錄，Notion 資料不受影響）[y/N]
```

確認後：
1. 刪除 `.spec/{slug}/` 目錄
2. 從 `_index.md` 的「已完成」表移除對應列
3. 還原 `.gitignore` 中的 `!.spec/{slug}/` 排除規則

### 5. 索引修復

若掃描發現 `_index.md` 與實際目錄不一致（目錄存在但索引缺少、或索引有但目錄不存在），自動修復並提示：

```
⚠️  索引修復：
  + 新增 push-tag-query 到索引（目錄存在但索引缺少）
  - 移除 old-feature 從索引（索引有但目錄不存在）
```

---

## 邊界情況

- **`.spec/` 不存在**：提示先執行 `/plan-start`
- **`_index.md` 損壞**：從各目錄的 `README.md` 重建
- **README.md frontmatter 解析失敗**：顯示警告，列出該目錄但標記為「格式異常」
- **Git branch 已刪除**：顯示分支但標記為「分支不存在」
