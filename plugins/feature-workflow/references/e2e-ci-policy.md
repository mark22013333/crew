# E2E CI Promotion Policy

> 定義 draft Playwright candidate 如何經過 deterministic source/review/stability gate，才可標示 `ci-ready`。

## 流程

```text
draft
  ↓
static source gate
  ↓
review gate
  ↓
stability gate
  ↓
candidate SHA-256 freshness
  ↓
environment gate
  ↓
ci-ready
```

## Hard blockers

以下任一成立，本批不得標示 `ci-ready`：

- Playwright source linter 有 `HARD` issue
- source linter 的 `REVIEW` issue 沒有具體 waiver reason
- test discovery 未成功
- framework/config load 未成功
- headless 單跑未成功
- promotion stability 使用 `retries != 0`
- `repeat_each < 3`
- stability run 有任何 failure
- passed 次數不足以覆蓋 repeat count
- stability evidence 的 `candidate_sha256` 與目前 candidate 不一致
- `environment_gate=deferred`

最後一項是刻意的保守邊界：Batch C 不自行發明 environment/shared-state policy。需要 environment/shared-state gate 的 candidate 先維持 draft，等獨立 policy 判定。

## Static source gate

先執行：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/lint-playwright-e2e.py" {candidate}
```

- `HARD`：不可 waiver。
- `REVIEW`：修正或寫入 promotion metadata 的 `review_waivers`。
- waiver 是 explicit exception，不是把 issue 當不存在。

## Stability gate

至少完成：

1. Playwright 能 discovery candidate。
2. framework/config 可載入。
3. headless 單跑成功。
4. 使用 `retries=0`。
5. 同一 candidate 重複至少 3 次且全部成功。

Generic baseline：

```bash
npx playwright test {file} --repeat-each=3 --retries=0
```

實際 command 仍由 framework adapter / project config 決定。

## Fingerprint freshness

Stability evidence 必須記錄 candidate SHA-256。只要 candidate bytes 改變，舊 evidence 即 stale，必須重新驗證。

## Machine gate

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-e2e-promote.py" check \
  --candidate {candidate} \
  --metadata .crew/e2e/{slug}.promotion.json
```

不得由 Agent 以「看起來穩」取代 machine gate。

## Promotion output

Promotion 只改 E2E 資產 maturity，不改 `state.json.results.verify`：

```yaml
maturity: ci-ready
adapter: {adapter}
```

Runtime PASS != E2E ci-ready != Human UAT。
