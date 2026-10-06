# E2E Promotion Metadata Schema

> `crew-e2e-promote.py` 的 deterministic input。這份 metadata 同時描述 candidate 的 source/review/stability maturity 與 environment/shared-state safety contract，但不修改 runtime verify truth。

## 建議位置

放在 E2E repo，與 candidate 一起版控：

```text
.crew/e2e/{slug}.promotion.json
```

不要放 credential、cookie、token、真實個資或敏感 response。

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

當 `environment_gate="policy"` 時，還必須有：

```json
{
  "environment": {
    "shared_mutation": false,
    "environment_bound_fixture": false,
    "unique_test_data": false,
    "disposable_environment": false,
    "persistent_owned_fixture": false,
    "idempotent_seed": false,
    "exclusive_execution": false,
    "parallel_safe": false,
    "workers": 1,
    "cleanup": "none",
    "safety_invariants": []
  }
}
```

## environment_gate

允許三種：

- `not-required`：candidate 沒有需要額外 machine policy 的 environment/shared-state 依賴。
- `deferred`：尚未完成 environment review；**永遠維持 draft**。
- `policy`：由本 schema 的 `environment` object 做 deterministic machine gate。

Template 預設 `deferred`。

若 source linter 發現 `FIXED_RECORD_ID`，即使該 REVIEW issue 有 waiver，也不得用 `not-required` 繞過 environment policy；必須改成 `policy` 或維持 `deferred`。

## Environment policy

### shared_mutation

測試是否會修改共用／持久資料。

`true` 時：

- 至少一條非空 `safety_invariants`
- 必須有 `cleanup=reliable`
- 或 `disposable_environment=true`
- 或符合完整 persistent-owned fixture contract

`unique_test_data=true` 只避免 collision，不等於 cleanup。

### environment_bound_fixture

是否依賴特定環境既有資料／固定 record。

若為 `true`，必須：
- reliable cleanup/restoration，或
- disposable environment，或
- 合格 persistent-owned fixture

### unique_test_data

每次 run 是否建立唯一 key/name，避免平行執行互撞。

若 `parallel_safe=true` 且 `shared_mutation=true`，必須：
- `unique_test_data=true`，或
- `disposable_environment=true`

### disposable_environment

整個測試環境是否可在 run 後直接丟棄，例如 ephemeral DB、container 或 isolated namespace。

### persistent_owned_fixture

表示 record 是專門給 E2E 使用的持久 fixture，不是一般 UAT／使用者資料。

若 `persistent_owned_fixture=true`，必須同時：

- `idempotent_seed=true`
- `exclusive_execution=true`
- `workers=1`
- `parallel_safe=false`

Shared mutation 仍要有 safety invariants。

此模式允許 `cleanup=none`，因為 canonical fixture 本來就設計成長期存在；每次 run 必須先由 idempotent seed 重設成同一狀態。

### idempotent_seed

重跑 seed 一次或多次都得到相同 canonical fixture，不累積額外資料，也不改到未宣告 owned 的 record。

### exclusive_execution

跨 pipeline 的互斥，不只是 Playwright `workers=1`。

可由 GitLab `resource_group`、Jenkins lock、其他 CI concurrency/mutex 提供。Metadata 宣告為 true 前，專案 CI 必須真的有對應機制。

### cleanup

允許：

- `reliable`：deterministic 還原／刪除，cleanup 失敗會讓測試失敗
- `best-effort`：可能殘留，不足以單獨讓 shared mutation candidate ci-ready
- `none`：沒有 cleanup；只有 disposable environment 或合格 persistent-owned fixture 才可能安全

### parallel_safe / workers

- `workers > 1` → 必須 `parallel_safe=true`
- persistent-owned fixture → 必須 `workers=1` 且 `parallel_safe=false`

## Safety invariants

例：

```json
[
  "forbid_request POST /dangerous/update",
  "mutate only records tagged CREW_E2E"
]
```

Shared mutation 沒有 safety contract → promotion BLOCK。

## Review waiver

Source linter 的 REVIEW issue 必須修掉或明確 waiver：

```json
{
  "review_waivers": [
    {
      "code": "FIXED_SLEEP",
      "reason": "legacy component has no observable completion signal"
    }
  ]
}
```

- HARD issue 不可 waiver
- waiver 必須有非空 reason

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

Candidate bytes 改變後，舊 SHA-256 evidence 立即 stale，必須重新跑 stability。

## 與 runtime truth 的邊界

Promotion metadata 只回答「這支 E2E 資產是否適合長期 CI」。

產品 AC 是否通過仍由 `crew-results.json` → `/plan-verify --from-e2e` → `crew-state.py` 決定。
