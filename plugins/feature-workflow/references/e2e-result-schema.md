# CREW E2E Result Schema

> CI / E2E runner 與 `/plan-verify --from-e2e` 之間的機器可讀交換格式。CI 不直接寫 `state.json`。

## Default path

由 project `e2e.results` 決定；未設定時建議：

```text
test-results/crew-results.json
```

## Schema v1

```json
{
  "schema_version": 1,
  "runner": "playwright",
  "environment": "uat",
  "git_sha": "abc123",
  "run_id": "ci-456",
  "results": [
    {
      "ac": "example-feature#AC-1",
      "scenario": "example-main-flow",
      "status": "passed",
      "attempts": 1,
      "duration_ms": 1832,
      "evidence": {
        "trace": null,
        "screenshot": "test-results/ac-1.png"
      }
    }
  ]
}
```

## Playwright reporter convention

CREW 提供 reference implementation：

```text
references/playwright/crew-reporter.js
```

E2E repo 應 vendor/copy 或自行實作相同 schema，不要讓 CI 依賴某台機器的 CREW plugin 路徑。

Mapping：
- test annotation `crew-ac`：description = `{slug}#AC-n`
- stateful `test.step`：title 直接包含 `{slug}#AC-n`
- precondition blocked：annotation `crew-blocked`，description = reason
- retry 後才成功：reporter 輸出 `flaky`

## status

允許：

- `passed`
- `failed`
- `flaky`
- `blocked`
- `skipped`
- `manual`

轉換為 plan-verify：

| E2E | Verify |
|---|---|
| passed | PASS |
| flaky | WARN |
| failed | FAIL |
| blocked | BLOCKED |
| skipped | SKIP |
| manual | MANUAL |

`blocked` 必須有 `reason`，代表 environment / auth / fixture / dependency precondition 失敗，不是產品 assertion failure。

## Boundaries

- CI 只產 result artifact，不 commit / patch `.spec/{slug}/state.json`。
- `--from-e2e` 驗證 schema、join key 與 git/environment metadata 後，再透過 `crew-state.py result` 寫 state。
- 不在 result artifact 放 password、token、cookie 或完整敏感 response body。
