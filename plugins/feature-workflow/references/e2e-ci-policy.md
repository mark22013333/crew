# E2E CI Promotion Policy

> Draft Playwright candidate 必須通過 source / review / stability / fingerprint / environment policy，才可標示 `ci-ready`。

## 流程

```text
draft
  ↓
static source gate
  ↓
review waiver gate
  ↓
stability gate
  ↓
candidate SHA-256 freshness
  ↓
environment gate
  ├ not-required
  ├ deferred → draft
  └ policy → environment machine gate
  ↓
ci-ready
```

## Source / review hard blockers

- source linter 有 HARD issue
- REVIEW issue 沒有具體 waiver reason
- `FIXED_RECORD_ID` 卻宣告 `environment_gate=not-required`

## Stability hard blockers

- discovery 未成功
- framework/config load 未成功
- headless 單跑未成功
- `retries != 0`
- `repeat_each < 3`
- stability run 有 failure
- passed 次數少於 repeat count
- candidate SHA-256 與 stability evidence 不一致

## Environment gate

### not-required

只適合沒有 environment/shared-state machine policy 需求的 candidate。

若 static source 已顯示固定 record ID，不得使用此值。

### deferred

代表 environment review 尚未完成，promotion 一律維持 `draft`。

### policy

依 `e2e-promotion-schema.md` 的 `environment` object 判定。

Machine gate 至少保證：

- shared mutation 沒有 safety invariant → BLOCK
- shared mutation 沒有 reliable cleanup、不是 disposable environment、也不是合格 persistent-owned fixture → BLOCK
- environment-bound fixture 不可可靠還原，且沒有 disposable / persistent-owned 路徑 → BLOCK
- persistent-owned fixture 沒有 idempotent seed / exclusive execution / workers=1 → BLOCK
- workers > 1 但 parallel_safe=false → BLOCK
- parallel shared mutation 沒有 unique data / disposable isolation → BLOCK
- persistent-owned flags 沒有 ownership 宣告 → BLOCK

## Static source gate

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/lint-playwright-e2e.py" {candidate}
```

HARD 不可 waiver；REVIEW 必須修正或寫入 promotion metadata 的 `review_waivers`，且每筆都要有具體 reason。

## Stability baseline

至少：

1. test discovery 成功
2. framework/config load 成功
3. headless 單跑成功
4. `retries=0`
5. `repeat-each >= 3`
6. 全部 repeat 成功

Generic baseline：

```bash
npx playwright test {file} --repeat-each=3 --retries=0
```

實際 command 由 framework adapter / project config 決定。

## Machine gate

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-e2e-promote.py" check \
  --candidate {candidate} \
  --metadata .crew/e2e/{slug}.promotion.json
```

不得由 Agent 以「看起來穩」取代 machine gate。

## CI execution baseline

- PR：smoke + 本次 feature coverage
- main/nightly：regression
- shared state 不足以平行時 workers=1
- persistent-owned fixture 必須有跨 pipeline concurrency/resource lock
- failure 保存 trace / screenshot；video 依 adapter/storage policy

## Promotion output

Promotion 只改 E2E 資產 maturity，不改 `state.json.results.verify`。

Runtime PASS != E2E ci-ready != Human UAT。
