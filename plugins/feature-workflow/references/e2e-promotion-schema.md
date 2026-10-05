# E2E Promotion Metadata Schema

> `crew-e2e-promote.py` 的 deterministic input。此 metadata 描述「這支 E2E candidate 是否具備長期 CI 條件」，不是 AC runtime truth，也不寫 `state.json`。

## 建議位置

放在 **E2E repo**，隨測試一起版控：

```text
.crew/e2e/{slug}.promotion.json
```

例如：

```text
.crew/e2e/push-schedule-category-filter.promotion.json
```

不要放 credential、cookie、token、真實個資或敏感 response。

## Schema v1

```json
{
  "schema_version": 1,
  "candidate": "tests/example/example.spec.js",
  "adapter": "generic-playwright",
  "maturity": "draft",

  "shared_mutation": false,
  "environment_bound_fixture": false,
  "unique_test_data": false,
  "disposable_environment": false,
  "parallel_safe": false,
  "workers": 1,
  "cleanup": "none",

  "safety_invariants": [],
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

## Fixture 欄位

### shared_mutation

測試是否會修改共用／持久資料。

`true` 時：

- 必須有 `safety_invariants`
- 必須 `cleanup=reliable`，**或**在 `disposable_environment=true` 的環境執行
- 只有 `unique_test_data=true` 不代表可以不 cleanup；它只解決 collision，不解決資料污染

### environment_bound_fixture

測試是否依賴特定環境既有資料／固定 record。

例如固定 template ID、schedule ID、特定 UAT 帳號資料。

此值可以是 `true` 且仍 ci-ready，但前提是 fixture 有可靠 restoration 或 environment disposable。

### unique_test_data

每個 run 是否使用唯一資料命名／key，避免兩次執行互撞。

若 `parallel_safe=true` 且 `shared_mutation=true`：

- 要有 `unique_test_data=true`
- 或 `disposable_environment=true`

### disposable_environment

整個測試環境是否可在 run 後直接丟棄，例如 ephemeral DB / container / isolated namespace。

### cleanup

允許：

- `reliable`：可以 deterministic 還原／刪除測試資料，且失敗會讓測試 fail
- `best-effort`：嘗試 cleanup，但可能殘留；不能讓 shared mutation candidate 升 ci-ready
- `none`：沒有 cleanup

### parallel_safe / workers

`workers > 1` 時必須 `parallel_safe=true`。

`parallel_safe=false` 不會單獨阻擋 ci-ready；可在 CI 固定 workers=1。

## Safety invariants

範例：

```json
[
  "forbid_request POST /push/schedule/update",
  "forbid_delete production-like fixture"
]
```

Shared mutation 沒有 safety contract → promotion BLOCK。

## Review waiver

Static linter 的 REVIEW issue 必須修掉或明確 waiver：

```json
{
  "review_waivers": [
    {
      "code": "FIXED_SLEEP",
      "reason": "legacy component currently exposes no observable completion signal; tracked for replacement"
    }
  ]
}
```

- HARD issue 不可 waiver
- waiver 必須有 reason
- 一個 code waiver 套用該 candidate 內同 code 的 REVIEW issue

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

Stability evidence 必須綁定實際測試檔 bytes。

取得：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-e2e-promote.py" fingerprint \
  --candidate tests/example/example.spec.js
```

若測試檔改過，SHA-256 不一致：

```text
STALE_STABILITY_EVIDENCE
```

必須重新跑 promotion stability；不能沿用舊的 3/3 成績。

## 操作流程

先建立 template：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-e2e-promote.py" template \
  --candidate tests/example/example.spec.js \
  --adapter generic-playwright \
  > .crew/e2e/example-feature.promotion.json
```

完成 fixture review、stability run 並更新 metadata 後：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-e2e-promote.py" check \
  --candidate tests/example/example.spec.js \
  --metadata .crew/e2e/example-feature.promotion.json
```

Exit code：

- `0`：ci-ready
- `1`：合法 metadata，但仍有 promotion blocker
- `2`：輸入／schema／檔案錯誤

## Promotion 與 runtime truth 的邊界

Promotion metadata 只回答：

> 這支測試資產是否適合長期 CI？

它不回答：

> 目前產品 AC 是否通過？

Runtime AC 結果仍由 `crew-results.json` → `/plan-verify --from-e2e` → `crew-state.py` 處理。
