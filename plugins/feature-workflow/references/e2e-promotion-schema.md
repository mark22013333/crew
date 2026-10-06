# E2E Promotion Metadata Schema

> `crew-e2e-promote.py` 的 deterministic input。這份 metadata 只回答 candidate 的 **source/review/stability maturity**，不修改 runtime verify truth。

## 建議位置

放在 E2E repo，與 candidate 一起版控：

```text
.crew/e2e/{slug}.promotion.json
```

不要放 credential、cookie、token 或測試帳號秘密。

## Schema v1

```json
{
  "schema_version": 1,
  "candidate": "tests/example/example.spec.js",
  "adapter": "generic-playwright",
  "maturity": "draft",
  "environment_gate": "deferred",
  "review_waivers": [],
  "stability": {
    "discovery": false,
    "framework_load": false,
    "headless_pass": false,
    "retries": 0,
    "repeat_each": 0,
    "passed": 0,
    "failed": 0,
    "candidate_sha256": "0000000000000000000000000000000000000000000000000000000000000000"
  }
}
```

## environment_gate

Batch C **不定義 environment/shared-state policy**。為避免在下一批 policy 尚未套用前把有環境風險的 candidate 誤標 `ci-ready`，promotion metadata 必須顯式宣告：

- `not-required`：此 candidate 不需要額外 environment machine gate，才能由本批 promotion evaluator 升級。
- `deferred`：需要後續 environment/fixture policy；本 evaluator 一律維持 `draft`。

Template 預設 `deferred`，採保守策略。

## Review waiver

Source linter 的 `REVIEW` issue 必須修掉或明確 waiver：

```json
{
  "review_waivers": [
    {
      "code": "FIXED_SLEEP",
      "reason": "legacy component currently exposes no observable completion signal"
    }
  ]
}
```

規則：

- `HARD` issue 不可 waiver。
- waiver 必須有非空 reason。
- 沒有 waiver 的 REVIEW issue → 維持 `draft`。

## Stability evidence

Promotion 至少要求：

```json
{
  "discovery": true,
  "framework_load": true,
  "headless_pass": true,
  "retries": 0,
  "repeat_each": 3,
  "passed": 3,
  "failed": 0,
  "candidate_sha256": "..."
}
```

### candidate_sha256

Stability evidence 必須綁定實際 candidate bytes。

取得：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-e2e-promote.py" fingerprint \
  --candidate tests/example/example.spec.js
```

若 candidate 修改後 SHA-256 不一致，promotion 必須拒絕舊 evidence。

## 操作

建立 template：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-e2e-promote.py" template \
  --candidate tests/example/example.spec.js \
  --adapter generic-playwright \
  > .crew/e2e/example-feature.promotion.json
```

完成 review 與 stability run 後：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-e2e-promote.py" check \
  --candidate tests/example/example.spec.js \
  --metadata .crew/e2e/example-feature.promotion.json
```

Exit code：

- `0`：本批 promotion gate 判定 `ci-ready`
- `1`：metadata 合法，但仍有 blocker，維持 `draft`
- `2`：metadata / input / schema 錯誤

## 與 runtime truth 的邊界

Promotion metadata 只回答：

> 這支 E2E candidate 的 source/review/stability 是否成熟？

它不回答：

> 目前產品 AC 是否通過？

Runtime AC truth 仍由 `crew-results.json` → `/plan-verify --from-e2e` → `crew-state.py` 處理。
