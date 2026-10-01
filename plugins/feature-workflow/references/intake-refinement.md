# CREW Intake Refinement Contract

> 所有新的 raw user request / raw issue 在建立 CREW task 之前，都先經過唯讀 intake refinement 與 Human confirmation。Feature/Plan 與 Bug 使用相同語意 contract，但各 plugin 帶自己的 named Agent 定義，維持可獨立安裝。

## 入口

```text
Feature / Plan:
raw request
  → feature-intake-refiner
  → Human confirms intent
  → /plan-start side effects
  → /plan spec
  → feature-spec-analyst

Bug:
raw issue
  → bug-intake-refiner
  → Human confirms intent
  → /bug-start side effects
  → /bug-investigate
```

已存在的 task、`--resume`、reopen、後續 investigate/build/fix 不重新跑 intake；intake 只處理「新任務的第一次 raw request」。

## Host capability

優先使用 `delegate_readonly`：

- Feature role=`feature-intake-refiner`
- Bug role=`bug-intake-refiner`
- task=`requirement_analysis`
- profile=`STANDARD`
- risk=`low`
- complexity=`low`

Host 沒有 named sub-agent / delegation 時，主 Agent inline 執行**同一份唯讀 contract**。Named Agent 是執行元件，不是 Slash Skill；使用者不需要手動呼叫它。

## Input contract

Leader 必須分離：

- `ORIGINAL_REQUEST`：移除 CREW control metadata 後的使用者自然語言原文，逐字保存
- explicit task type / environment / priority / related feature 等 control metadata
- project_instructions
- 使用者針對 blocking questions 的補充回答

Refiner 不得把自己的改寫回填成 `ORIGINAL_REQUEST`。

## Output contract

```text
refined_title: <= 80 chars
refined_request:
  1–8 lines; purpose/symptom + desired outcome + known constraints
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
- bug 根因結論

這些留給後續 `/plan spec|db|arch|build` 或 `/bug-investigate|bug-fix`。

## Refinement rules

1. **Preserve intent**：改善清楚度，不增加使用者沒說過的新 scope。
2. **Project terminology only**：可用 project_instructions 與少量已知術語修正命名；不要廣泛掃描 codebase。
3. **Separate fact / assumption**：無法從原文知道的內容放 `ambiguities`，不能偷偷補進 refined request。
4. **Ask only when blocking**：只有答案會改變任務方向、邊界或成功定義時才列 blocking question，最多 3 個。
5. **Concise**：refined request 是 task brief / issue brief，不是 PRD 或 RCA。
6. **Read-only**：不得寫檔、Notion、state、Git branch 或產品碼。

## Human confirmation gate

任何 task-creation side effect 前必須展示 original + refined，讓 Human 選：

1. 確認 refined
2. 修改／補充後再 refine
3. 使用 original 作 confirmed brief
4. 取消

沉默、沒有再修改、Refiner 認為合理，都不等於確認。

確認前禁止：

- Notion create/update
- 建立 `.spec`
- `crew-state.py init`
- 建立/切換 Git branch

取消必須是 **zero side effect**。

## Persistence contract

### Feature / Plan

Notion「📋 需求描述」固定保留：

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

`plan.md` 只保存 confirmed refined brief；raw prompt 留在 Notion。

Notion 暫時失敗時，可用 `.spec/{slug}/.cache/intake.md` 暫存；`/plan-sync` 或 `/plan-close` 成功持久化後刪除。

### Bug

Bug Notion「🔴 問題描述」固定保留：

```markdown
### 原始通報
{ORIGINAL_REQUEST}

### 確認後問題描述
{REFINED_REQUEST}
```

Bug state 的 `name` 使用 `CONFIRMED_TITLE`，不把 raw prompt 塞進 state schema。

#### Recovery cache：第一個 post-confirmation side effect

Human confirmation + slug 決定後，**在 Notion create / state init 之前**先建立：

```text
.spec/{slug}/.cache/intake.md
```

固定保存 `original_request`、`refined_request`、`refined_title`。這個 directory 可以先於 `state.json` 存在；`crew-state.py init` 只把既有 `state.json` 視為 collision。

因此任何後續失敗都至少保留 confirmed intake：

- Notion create 失敗
- state init 失敗
- Notion body/template 寫入失敗

只有 Notion 頁面已重新 fetch 並確認 `### 原始通報` + `### 確認後問題描述` 存在後，才能刪除 cache。

#### Pending task reuse

重跑 `/bug-start` 遇到同 slug 時：

1. 若沒有 `state.json`、但有 matching intake cache → 詢問 Human 是否沿用這個 pre-init pending task。
2. 若已有 `type=bug, phase=start` state 且 intake cache 相符 → 詢問是否沿用，不論 `notion.page_id` 是否已存在。
3. 沿用時：
   - state 已存在 → 不重新 `init`
   - page ID 已存在 → 不建立第二個 Notion page
   - page ID 為空 → 建立 page 後用 `crew-state.py set --notion-page-id` 綁回既有 state
4. cache 不相符或 Human 不沿用 → 才產生數字後綴的新 slug。

#### Bug intake recovery preflight

任何正常 lifecycle command 在定位既有 Bug 後，若能綁到唯一 `{slug}`，都先做：

1. `.spec/{slug}/.cache/intake.md` 不存在 → 直接繼續。
2. cache 存在 → `notion-fetch` 目前 page。
3. 若 intake headings 已完整存在 → 刪 cache，繼續。
4. 若缺 intake prefix 或標準 Bug template section：
   - 以 cache 的 original/refined 為來源。
   - 保留既有頁面內容。
   - 補回 `### 原始通報`、`### 確認後問題描述`。
   - 缺少 `🔍 調查過程`、`🧠 根因分析`、`✅ 修復方案`、`🧪 驗證`、`📝 經驗教訓` 時，只補缺少的 section，不覆蓋既有內容。
5. 再次 `notion-fetch`；確認兩個 intake headings 都存在後才刪 cache。
6. recovery 失敗 → 保留 cache，停止會覆寫/結案的後續動作並回報；不得假裝已持久化。

`/bug-investigate`、`/bug-update`、`/bug-close` 都套用此 preflight。Legacy task 若無可綁定 state/cache，可維持原流程；不得猜不存在的 original request。

若 original request 無法恢復，**不得猜原文**；詢問 Human 或標記 unavailable。

## Existing-task rule

以下情況**不重新 refine**：

- `/bug-investigate --resume`
- 已定位到既有 Bug 的 `/bug-investigate`
- `/bug-update`
- `/bug-fix`
- `/bug-close`
- 已建立 task 後的 `/plan spec|db|arch|build|...`

只有「使用者帶著新的 raw request 要建立新 task」才跑 intake。

## Security / privacy

Refiner 不得把 secrets 從 project files 抄進 refined request。使用者 raw request 若本身含 secret，持久化到 Notion 前應警告 Human；不要未經確認擴散到更多 artifact。
