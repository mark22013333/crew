# CREW E2E Result Schema

> CI / E2E runner 與 `/plan-verify --from-e2e` 之間的機器可讀交換格式。CI 不直接寫 `state.json`。

## Default path

由 project `e2e_results` 決定；未設定時建議：

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
      "coverage": "full",
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
- 整支 scenario 的 precondition blocked：annotation `crew-blocked`，description = reason
- 只阻擋部分 AC：runtime annotation `crew-ac-status`，description 為 JSON，例如 `{"ac":"slug#AC-5","status":"blocked","reason":"fixture mismatch"}`
- 只有部分 evidence：`crew-ac-status` 可只填 `coverage:"partial"`
- retry 後才成功：reporter 輸出 `flaky`

Playwright 目前會把 runtime `testInfo.annotations` 暴露在 `TestResult.annotations`；CREW reporter 以 result annotations 為主，才能正確讀到執行中才發現的 BLOCKED。

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

## coverage

每筆 result 可選：

- `full`（預設）：這筆 evidence 足以代表該 AC 的完整 E2E coverage。
- `partial`：只證明 AC 的一部分，例如「前端篩選 UI 正常，但後端 count/query contract 由 JUnit 另外覆蓋」。

`status=passed + coverage=partial` 匯回 plan-verify 時是 **WARN**，不是 PASS。這能避免部分 evidence 被冒充成完整驗收。

## Import / aggregation

`--from-e2e` 先執行 plugin 內建：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-e2e-results.py" summarize \
  --file {result} --slug {slug} --expected-git-sha {sha}
```

同一個 AC 若被多個 test / scenario 覆蓋，採**最差狀態優先**：

```text
failed > blocked > flaky > manual > skipped > passed
```

這可避免一支 PASS 測試把另一支 FAIL coverage 蓋掉。

coverage 聚合：只要任一筆明確宣告 `full`，聚合 coverage 為 `full`；若所有 coverage 都是 `partial`，聚合結果維持 `partial`。

## Boundaries

- CI 只產 result artifact，不 commit / patch `.spec/{slug}/state.json`。
- `--from-e2e` 驗證 schema、join key 與 git/environment metadata 後，再透過 `crew-state.py result` 寫 state。
- 不在 result artifact 放 password、token、cookie 或完整敏感 response body。
