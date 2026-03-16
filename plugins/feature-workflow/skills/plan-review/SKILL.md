---
name: plan-review
description: 以 Agent Teams 3 人並行審查程式碼（邏輯/品質/安全），完成後互相分享發現並交叉審查，產出審查報告寫入 .spec/ 目錄。當使用者提到「plan-review」、「審查」、「review」時觸發此 Skill。
---

# plan-review — Agent Teams 程式碼審查

以 **Agent Teams** leader-delegate 模式，3 位 Reviewer 並行審查程式碼，完成後**互相分享發現並交叉審查**，Leader 彙整報告寫入 `.spec/{slug}/review.md`。

---

## 前置條件

### 環境變數

必須啟用 Agent Teams 實驗功能（同 plan-build）。

### 程式碼

建議已執行 `/plan-build` 產生程式碼，或已有開發中的程式碼。

---

## 使用方式

```
/plan-review               # 完整 3 人審查
/plan-review --quick       # 快速審查（僅 logic-reviewer，用 Subagent）
```

---

## 流程

### 1. 定位活躍任務

與 `/plan` 相同邏輯：從 Git branch 或 `_index.md` 匹配活躍任務。

### 2. 收集審查範圍

確定要審查的程式碼範圍：

1. 若 `.spec/{slug}/files.md` 存在 → 從中取得檔案清單
2. 否則，從 Git diff 取得：
   ```bash
   git diff $(git merge-base HEAD production)..HEAD --name-only
   ```
3. 若都沒有 → 提示使用者指定檔案

### 3. 讀取設計文件

讀取 `.spec/{slug}/` 下的可用文件作為審查基準：
- `spec.md`（技術規格 — 驗證功能正確性）
- `db.md`（DB 設計 — 驗證 SQL 正確性）
- `arch.md`（架構設計 — 驗證分層一致性）
- `verify.md`（運行時驗證結果 — 供 Reviewers 參考）— 選讀

### 4. 確認執行計畫

```
即將啟動 Agent Teams 程式碼審查：

📁 審查範圍：N 個檔案
📊 Reviewer 配置：
  • Reviewer 1 — 邏輯正確性（Opus）
  • Reviewer 2 — 程式碼品質（Sonnet）
  • Reviewer 3 — 安全性與效能（Opus）

確認開始？[Y/n]
```

### 5. 啟動 Agent Teams

#### 完整審查（Agent Teams）

使用自然語言要求 Claude 建立 Agent Team：

```
建立一個 Agent Team 來做 Code Review，生成 3 個 Reviewer：

【Reviewer 1：邏輯正確性】Logic Reviewer
- 讀取專案 CLAUDE.md 了解架構慣例
- 讀取設計文件：
  * .spec/{slug}/spec.md（技術規格）
  * .spec/{slug}/arch.md（架構設計）
- 若 .spec/{slug}/verify.md 存在：
  * 讀取驗證結果，關注 ❌ FAIL 項目
  * 檢查失敗原因是否對應到程式碼問題
  * 審查報告中引用驗證結果作為佐證
- 讀取本次新增/修改的所有程式碼檔案：
  {檔案清單}
- 檢查：
  * API 參數驗證是否完整
  * 業務邏輯是否符合規格
  * 查詢條件是否正確
  * 例外處理是否恰當
  * 邊界條件是否考慮
  * 回傳格式是否一致
- 標記嚴重程度：🔴 嚴重 / 🟡 建議 / 🟢 良好
- 使用 Opus 模型
- 使用繁體中文

【Reviewer 2：程式碼品質】Quality Reviewer
- 掃描專案中 2-3 個同類型的現有檔案作為風格基準
- 讀取本次新增/修改的所有程式碼檔案：
  {檔案清單}
- 檢查：
  * 程式碼風格、命名規範是否與專案一致
  * package 結構和 import 順序
  * Lombok 使用方式
  * 註解風格和位置
  * Error handling 是否完善
  * 有沒有 edge case 沒處理（空數據、數據不足等）
- 標記：🟡 不一致 / 🟢 一致
- 可使用 Sonnet 模型
- 使用繁體中文

【Reviewer 3：安全性與效能】Security Reviewer
- 讀取專案 CLAUDE.md 了解安全框架（ESAPI? AntiSamy?）
- 讀取 .spec/{slug}/db.md 了解 DB 設計
- 讀取本次新增/修改的所有程式碼檔案：
  {檔案清單}
- 安全性檢查：
  * SQL Injection（MyBatis ${} vs #{}）
  * XSS（輸入未轉義、前端的 XSS 防護）
  * API 的 input validation
  * 權限控制遺漏
  * 敏感資料外洩
  * CSRF 防護
- 效能檢查：
  * N+1 查詢
  * 缺少分頁
  * 缺少索引
  * 迴圈內 DB 呼叫
  * 大量資料未串流
  * 潛在的效能問題（大數據量回測）
- 標記：🔴 安全漏洞 / 🟡 效能風險 / 🟢 良好
- 使用 Opus 模型
- 使用繁體中文

三位 Reviewer 完成後請互相分享各自的發現，
看看有沒有交叉觀點或遺漏（如邏輯問題可能導致安全風險），
最後由 Lead 彙整產出完整的 Review Report。

請使用 delegate mode，Lead 只負責協調，不要自己寫 code。
所有輸出使用繁體中文。
```

#### 快速審查（--quick，Subagent）

使用 Agent tool 啟動單一 subagent（model: opus），只做邏輯正確性審查：

```
你是資深程式碼審查員。

## 設計文件
{spec.md + arch.md 內容}

## 審查檔案
{檔案清單及內容}

## 專案上下文
{CLAUDE.md 內容}

## 任務
對以上程式碼進行快速審查，聚焦於：
1. 邏輯正確性
2. 明顯的安全問題
3. 風格一致性（與專案現有程式碼比對）

標記嚴重程度：🔴 嚴重 / 🟡 建議 / 🟢 良好
輸出使用繁體中文。
```

### 6. 彙整審查報告

Leader 收集所有 Reviewer 的發現（含交叉分享結果），彙整寫入 `.spec/{slug}/review.md`：

```markdown
# 程式碼審查報告

## 審查日期
{日期}

## 審查範圍
{N} 個檔案

## 統計
| 類別 | 🔴 嚴重 | 🟡 建議 | 🟢 良好 |
|------|---------|---------|---------|
| 邏輯正確性 | {N} | {N} | {N} |
| 程式碼品質 | — | {N} | {N} |
| 安全與效能 | {N} | {N} | {N} |
| **合計** | **{N}** | **{N}** | **{N}** |

## 🔴 嚴重問題

### [{序號}] {問題標題}
- **檔案**：{路徑}:{行號}
- **Reviewer**：{logic/quality/security}
- **問題**：{描述}
- **建議**：{修復建議}

## 🟡 改善建議

### [{序號}] {建議標題}
- **檔案**：{路徑}:{行號}
- **Reviewer**：{reviewer}
- **建議**：{描述}

## 🟢 良好實踐

{正面反饋清單}

## 交叉審查發現

{Reviewers 之間互相分享後發現的額外觀點}
```

### 7. 更新 .spec/

1. 更新 `README.md` 的 `status: 程式碼審查`
2. 在 `log.md` 追加紀錄

### 8. 回傳結果

```
程式碼審查完成！

📋 報告：.spec/{slug}/review.md
📊 統計：🔴 {N} 嚴重 / 🟡 {N} 建議 / 🟢 {N} 良好

{若有嚴重問題}
⚠️  發現 {N} 個嚴重問題，建議修復後再結案。

後續可使用：
  • 修正問題後再次 /plan-review
  • /plan-close   — 結案並同步 Notion
```

---

## 邊界情況

- **無程式碼可審查**：提示先執行 `/plan-build` 或 commit 程式碼
- **Agent Teams 未啟用**：顯示設定指引，或建議用 `--quick` 模式
- **交叉審查發現嚴重問題**：提供選項：修正後重新審查 / 忽略繼續 / 終止
- **Reviewer 失敗**：提供選項：重試 / 跳過該 Reviewer / 終止
- **--quick 模式**：不建立 Agent Teams，只用 Subagent
