---
name: plan-spec
description: 產出技術規格書，寫入 .spec/ 目錄，不呼叫 Notion API。當使用者提到「plan-spec」、「技術規格」、「規格書」、「spec」時觸發此 Skill。
---

# plan-spec — 技術規格書（零 Notion 呼叫）

讀取 `.spec/{slug}/` 目錄的需求描述，啟動 Agent 產出完整技術規格書。

---

## 前置條件

> **前置檢查**：參照 bug-workflow plugin 的 `references/prerequisites.md` 檢查 CLAUDE.md 是否存在。

- 適用類型：**Feature**
- 前置檔案：`README.md`（由 `/plan-start` 建立）

---

## 流程

### 1. 定位活躍任務 + 讀取專案上下文

參照 `references/plan-common.md`。

### 2. 產出技術規格

使用 **Agent tool** 啟動 subagent（model: opus），prompt 指示如下：

**輸入來源**：
- 需求描述從 `.spec/{slug}/README.md` 讀取（非 Notion）
- 若使用者在指令中補充需求，合併到輸入

**輸出目標**：
- 使用 Write tool 寫入 `.spec/{slug}/spec.md`（非 Notion）

**Agent 額外指示**：
```
產出完整技術規格，包含：
1. 功能範圍（In Scope / Out of Scope）
2. API 端點設計（表格格式）
3. 業務邏輯規則
4. 錯誤處理策略
5. 分層決策
6. 效能需求

在文件最後附加判斷區塊：
---
## 判斷
- FRONTEND_REQUIRED: true/false
- FRONTEND_TECH: JSP/Vue/React/無
- DB_REQUIRED: true/false
- DB_TABLES: 預估的表清單
```

完成後更新 README.md 的 `status: 規格設計`。

### 3. 一致性驗證 + 更新日誌

參照 `references/plan-common.md`。

### 4. 規格確認迴圈（必須執行）

> ⚠️ **硬性規則**：spec.md 產出後，**禁止自動呼叫 plan-build、plan-db、plan-arch 或直接開始寫程式碼**。必須進入以下確認迴圈，直到使用者明確表示規格書沒問題為止。

**首次呈現**：

向使用者摘要 spec.md 的關鍵內容（功能範圍、API 端點、業務規則、判斷區塊），然後詢問：

```
規格書初版已產出，請審閱：.spec/{slug}/spec.md

請確認是否需要調整？
  • 直接告訴我要修改的部分，我會更新 spec.md
  • 若確認規格書沒問題，我會列出後續可用的指令
```

**迭代修改**：

使用者提出修改要求時：
1. 根據使用者的回饋更新 `.spec/{slug}/spec.md`
2. 摘要本次修改內容
3. 再次詢問是否還需要調整

重複此迴圈，直到使用者明確表示「沒問題」、「OK」、「確認」、「可以了」等肯定回覆。

**使用者確認後**：

```
規格書已確認！

📁 產出檔案：.spec/{slug}/spec.md
📊 狀態：規格設計

後續可使用：
  • /plan-db    — DB 設計
  • /plan-arch  — 架構設計
  • /plan       — 完整規劃（自動串接 spec → db → arch）
  • /plan-build — Agent Teams 產生程式碼（需先完成架構設計）
```

---

## 範例

參考 `examples/good-spec-output.md` 了解理想的 spec.md 產出格式。
