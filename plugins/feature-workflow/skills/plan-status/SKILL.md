---
name: plan-status
description: 列出 .spec/ 目錄中所有活躍和已完成的任務，純本地操作不呼叫 Notion。當使用者提到「plan-status」、「任務狀態」、「目前有哪些任務」、「任務列表」時觸發此 Skill。
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
/plan-status --park <slug>   # 暫停指定任務
/plan-status --unpark <slug> # 恢復指定任務
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

## 暫停中（{N} 個）

| # | 類型 | 名稱 | 暫停前狀態 | 分支 | 暫停日期 |
|---|------|------|-----------|------|---------|
| 1 | 🔧 feature | 資料匯出 | DB 設計 | feature/data-export | 2026-03-15 |

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
     ❌ root-cause.md
     ❌ fix.md
```

### 4. 暫停/恢復模式

#### --park `<slug>`

1. 讀取 `.spec/{slug}/README.md`，確認任務存在且非已完成/已暫停狀態
2. 在 README.md 的 frontmatter 新增 `parked_status` 欄位，記錄當前 `status` 值
3. 更新 `status` 為 `暫停`
4. 更新 `_index.md`：將該任務從「進行中」移至「暫停中」區段，記錄暫停日期
5. 在 `log.md` 追加暫停紀錄：
   ```markdown
   ### [{日期}] 任務暫停
   - 暫停前狀態：{原狀態}
   - 原因：{使用者可選填}
   ```
6. 輸出確認：
   ```
   ⏸️  已暫停：{name}（原狀態：{parked_status}）
   恢復請執行：/plan-status --unpark {slug}
   ```

#### --unpark `<slug>`

1. 讀取 `.spec/{slug}/README.md`，確認 `status` 為 `暫停` 且 `parked_status` 存在
2. 將 `status` 恢復為 `parked_status` 的值
3. 移除 `parked_status` 欄位
4. 更新 `_index.md`：將該任務從「暫停中」移回「進行中」區段
5. 在 `log.md` 追加恢復紀錄：
   ```markdown
   ### [{日期}] 任務恢復
   - 恢復狀態：{原 parked_status}
   ```
6. 輸出確認：
   ```
   ▶️  已恢復：{name}（狀態：{restored_status}）
   ```

### 5. 清理模式（--cleanup）

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

### 6. 索引修復

若掃描發現 `_index.md` 與實際目錄不一致（目錄存在但索引缺少、或索引有但目錄不存在），自動修復並提示：

```
⚠️  索引修復：
  + 新增 push-tag-query 到索引（目錄存在但索引缺少）
  - 移除 old-feature 從索引（索引有但目錄不存在）
```

---

## Gotchas

- **_index.md 與實際目錄常不同步**：`_index.md` 是快取性質，手動刪除目錄或中斷操作都可能造成不一致。掃描時應以「目錄存在 + README.md 可解析」為準，`_index.md` 僅作為輔助，發現不一致時自動修復（步驟 5）。
- **--cleanup 的天數計算基準**：應從移入「已完成」的日期算起，不是 `README.md` 中的 `created` 日期。完成日期從 `_index.md` 的「已完成」表的「完成日期」欄位讀取；若該欄位不存在，fallback 到 `log.md` 最後一筆紀錄的日期。
- **--park 不能暫停已完成的任務**：已完成的任務不應被暫停，因為暫停的語意是「稍後繼續」，已完成的任務沒有繼續的必要。
- **--unpark 要求 parked_status 存在**：若 README.md 的 `parked_status` 欄位不存在（手動修改造成），無法自動恢復。此時提示使用者手動指定要恢復到的狀態。

---

## 邊界情況

- **`.spec/` 不存在**：提示先執行 `/plan-start`
- **`_index.md` 損壞**：從各目錄的 `README.md` 重建
- **README.md frontmatter 解析失敗**：顯示警告，列出該目錄但標記為「格式異常」
- **Git branch 已刪除**：顯示分支但標記為「分支不存在」
- **--park 指定不存在的 slug**：提示任務不存在，列出可用的進行中任務
- **--unpark 指定非暫停狀態的任務**：提示該任務不在暫停狀態
- **`_index.md` 缺少「暫停中」區段**：索引修復時自動補充
