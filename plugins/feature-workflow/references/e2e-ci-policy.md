# E2E CI Promotion Policy

> `/plan-verify` 產生的 E2E 預設是 `draft`。Runtime PASS 只證明「這次環境能驗」，不代表腳本適合長期 CI。

## Maturity

```text
draft
  ↓ promotion gate
ci-ready
```

## Hard block

以下任一成立，不得標示 `ci-ready`：

- hardcoded password / token / cookie / API key
- `test.only`
- 沒有理由的 `test.skip` / `test.fixme`
- TODO / FIXME 尚未處理
- AC 沒有穩定 `{slug}#AC-n` join key
- 沒有 assertion，只做操作／截圖
- destructive/shared-environment flow 沒有 safety invariant
- 會建立／修改共享資料但沒有可靠 cleanup、unique data 或 disposable environment
- 依賴某位工程師家目錄的絕對路徑
- 必須使用 `ci_eligible=false` 的 selector / recipe 才能成功

## Static lint

Promotion 前先執行：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/lint-playwright-e2e.py" {candidate}
```

HARD issue 不得 promotion；REVIEW issue 必須有明確理由或修正。

## Review required

以下不是一律禁止，但必須明確說明：

- `waitForTimeout`
- XPath / `nth-child` / 長 CSS chain
- hardcoded DB record ID
- 固定 UAT fixture
- worker 必須為 1
- 依賴第三方或短暫 UI notification

Promotion metadata 至少要明確記錄：

- `shared_mutation=true|false`
- `environment_bound_fixture=true|false`
- `unique_test_data=true|false`
- `disposable_environment=true|false`
- `parallel_safe=true|false`
- `workers=N`
- `cleanup=reliable|best-effort|none`

## Promotion metadata machine gate

Fixture / safety / review waiver / stability evidence 使用 `e2e-promotion-schema.md`，最後由：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-e2e-promote.py" check \
  --candidate {candidate} \
  --metadata .crew/e2e/{slug}.promotion.json
```

決定是否可標 `ci-ready`。

Machine gate 額外保證：

- shared mutation 沒有 safety invariant → BLOCK
- shared mutation 沒有 reliable cleanup 且不是 disposable environment → BLOCK
- environment-bound fixture 無法可靠還原 → BLOCK
- workers > 1 但 parallel_safe=false → BLOCK
- REVIEW issue 沒有具體 waiver reason → BLOCK
- stability evidence 的 candidate SHA-256 與目前測試內容不同 → BLOCK

## Stability gate

CI-ready 前至少：

1. test discovery 成功
2. syntax / type / framework load 成功
3. headless 單跑成功
4. promotion 階段用 `retries=0` 重複執行至少 3 次
5. 3 次都成功才視為穩定；任何 retry 才成功都標 flaky，不得靜默當 PASS

Framework adapter 可定義等價 command，但不得跳過上述語意。

## Stateful scenario

若多個 AC 共用昂貴 login / fixture / state，可使用一個 scenario + 多個：

```ts
test.step('AC-1: ...')
test.step('AC-2: ...')
```

不要求為了「一 AC 一 test」重複破壞性 setup。

## CI execution baseline

- PR：smoke + 本次 feature coverage
- main/nightly：regression
- 預設 shared state 不足以安全平行時 workers=1
- 只有 fixture 隔離成熟後才提高 parallelism
- failure 保存 trace / screenshot；video 依 adapter / storage policy 決定

## Promotion output

Promotion 不修改 `state.json` 的 verify truth。它只產生 E2E 資產成熟度：

```yaml
maturity: ci-ready
parallel_safe: false
environment_bound_fixture: true
cleanup: reliable
```

真正 AC runtime 結果仍由 `plan-verify` / `--from-e2e` 寫入 `state.json.results.verify`。
