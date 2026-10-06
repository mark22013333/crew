# plan-verify Phase: E2E Promotion

本檔由 `/plan-verify --e2e-promote` 使用，依 `../../references/e2e-ci-policy.md` 判定 E2E candidate 能否由 `draft` 升為 `ci-ready`。

## 前提

- candidate 已存在
- framework adapter 已解析
- candidate 目前 maturity = `draft`
- promotion metadata 使用 `../../references/e2e-promotion-schema.md`

本 phase 不重新判斷產品 AC；runtime truth 仍由 plan-verify / `--from-e2e` 負責。

## 1. Static / review gate

執行：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/lint-playwright-e2e.py" {candidate}
```

- HARD → promotion BLOCK
- REVIEW → 修正或在 `review_waivers` 寫具體 reason
- `FIXED_RECORD_ID` → environment gate 不得宣告 `not-required`

## 2. Environment gate

Promotion metadata 可選：

### 不需要額外 policy

```json
{ "environment_gate": "not-required" }
```

### 尚未完成 review

```json
{ "environment_gate": "deferred" }
```

→ 保持 draft。

### 使用 machine policy

```json
{
  "environment_gate": "policy",
  "environment": {
    "shared_mutation": true,
    "environment_bound_fixture": true,
    "unique_test_data": false,
    "disposable_environment": false,
    "persistent_owned_fixture": true,
    "idempotent_seed": true,
    "exclusive_execution": true,
    "parallel_safe": false,
    "workers": 1,
    "cleanup": "none",
    "safety_invariants": ["mutate only CREW_E2E-owned records"]
  }
}
```

完整規則見 `../../references/e2e-promotion-schema.md`。

## 3. Stability gate

至少：

1. discovery 成功
2. framework/config load 成功
3. headless 單跑成功
4. `retries=0`
5. `repeat-each >= 3`
6. 全部 repeat 成功

Generic baseline：

```bash
npx playwright test {file} --repeat-each=3 --retries=0
```

## 4. Fingerprint

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-e2e-promote.py" fingerprint \
  --candidate {candidate}
```

把輸出寫入 `stability.candidate_sha256`。Candidate 修改後必須重跑 stability。

## 5. Machine promotion gate

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-e2e-promote.py" check \
  --candidate {candidate} \
  --metadata .crew/e2e/{slug}.promotion.json
```

- exit 0 → 可標 `maturity=ci-ready`
- exit 1 → 保持 `draft`，依 blockers 修正
- exit 2 → metadata / schema / input 錯誤

## 6. 結果

Promotion 不修改 runtime verify result，也不取代 Human UAT。
