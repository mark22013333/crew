# Intake Refinement Contract

> `/plan-start` 在任何 Notion / `.spec` / Git side effect 之前使用本 contract。目的不是寫正式 spec，而是把 raw request 變成 Human 可確認的 task brief；正式 Goal / AC / Decision 仍由 `/plan spec` + `feature-spec-analyst` 負責。

## 責任分界

```text
raw user request
  → feature-intake-refiner
  → Human confirms intent
  → /plan-start side effects
  → /plan spec
  → feature-spec-analyst
```

Intake Refiner 回答：「使用者想做什麼？」

Spec Analyst 回答：「這個需求如何成為可驗收的工程 contract？」

兩者不得合併成同一階段。

## Input contract

Leader 保留：

- `ORIGINAL_REQUEST`：移除 CREW control flags 後的使用者自然語言原文，逐字保存
- explicit task type / `--related`
- project_instructions
- 使用者針對 blocking questions 的補充回答

Refiner 不得把自己的改寫回填成 `ORIGINAL_REQUEST`。

## Output contract

```text
refined_title: <= 80 chars
refined_request:
  1–8 lines; purpose + desired outcome + known constraints
known_constraints:
  - ...
ambiguities:
  - ...
blocking_questions:
  - ...   # 0–3 only
type_hint: feature|bug|unknown   # advisory only
```

禁止在 intake 階段產出：

- AC-n
- DB schema
- API endpoint table
- class/method design
- implementation plan
- code changes

這些都屬 `/plan spec|db|arch|build`。

## Refinement rules

1. **Preserve intent**：改善清楚度，不增加使用者沒說過的新 scope。
2. **Project terminology only**：可用 project_instructions 與少量已知術語修正命名；不要廣泛掃描 codebase。
3. **Separate fact / assumption**：無法從原文知道的內容放 `ambiguities`，不能偷偷補進 refined request。
4. **Ask only when blocking**：只有答案會改變任務方向、邊界或成功定義時才列 blocking question，最多 3 個。
5. **Concise**：refined request 是 task brief，不是 PRD。
6. **Read-only**：不得寫檔、Notion、state、Git branch。

## Human confirmation gate

任何 side effect 前必須展示 original + refined，讓 Human 選：

1. 確認 refined
2. 修改／補充後再 refine
3. 使用 original 作 confirmed brief
4. 取消

沉默、沒有再修改、Refiner 認為合理，都不等於確認。

## Persistence contract

### Notion（persistent raw source）

Feature 頁面的「📋 需求描述」固定順序：

```markdown
### 原始需求
{ORIGINAL_REQUEST}

### 確認後任務描述
{REFINED_REQUEST}

### 目標與範圍
{plan.md projection}

### 驗收條件
{plan.md AC projection}
```

`/plan-sync`、`/plan-close` 只更新後兩段，不得覆蓋前兩段。

### plan.md

只保存 Human 確認後的 brief：

```markdown
# {CONFIRMED_TITLE}

> {REFINED_REQUEST}
```

plan.md 不保存長篇原始 prompt，維持 ≤100 行與 spec ownership contract。

### Offline recovery

若 Notion page/body 建立失敗，在 task 建立後可暫存：

```text
.spec/{slug}/.cache/intake.md
```

它保存 original/refined/title，gitignored、不是 truth source。下一次 `/plan-sync` 或 `/plan-close` 成功把 intake 寫進 Notion 後刪除。

舊任務沒有 intake cache 且 Notion 也沒有 original request 時，**不得猜原文**；詢問 Human 是否補上，或明確標記原始需求不可恢復。

## Security / privacy

Refiner 不得把 secrets 從 project files 抄進 refined request。使用者 raw request 若本身含 secret，Notion persistence 前應警告 Human；不要未經確認擴散到更多 artifact。
