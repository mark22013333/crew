# plan-verify Phase: E2E Promotion

本檔依 `../../references/e2e-ci-policy.md` 判定 E2E candidate 能否由 `draft` 升為 `ci-ready`。

## 1. Static gate

檢查：
- 無 hardcoded secret
- 無 `test.only`
- 無未解 TODO / FIXME
- skip/fixme 有明確 contract
- 有 AC join key
- 有 assertion
- destructive flow 有 safety invariant
- shared mutation 有 cleanup / unique data / disposable env
- 沒有工程師家目錄絕對 path
- 不依賴 `ci_eligible=false` selector / recipe

命中 hard block → 保持 `draft`。

## 1.5 Static linter

先執行 plugin 內建 linter：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/lint-playwright-e2e.py" {candidate}
```

- HARD issue → promotion 直接 BLOCK
- REVIEW issue → 進入下一節人工／Agent 審查
- 需要把 REVIEW 也當 hard gate 時可加 `--strict-review`
- 此 linter 是 heuristic guard，不取代實際 Playwright 執行

## 2. Review gate

以下要求人工或 Agent 說明：
- `waitForTimeout`
- XPath / nth-child / 長 CSS chain
- fixed DB ID
- UAT 固定 fixture
- workers=1
- 短暫 notification / 第三方 dependency

輸出 metadata：

```yaml
environment_bound_fixture: true
parallel_safe: false
cleanup: best-effort
```

## 3. Stability gate

由 adapter 提供等價 command，語意必須包含：
1. discovery 成功
2. syntax / framework load 成功
3. headless 單跑成功
4. `retries=0`
5. 重複至少 3 次

Generic Playwright 範例：

```bash
npx playwright test {file} --list
npx playwright test {file}
npx playwright test {file} --repeat-each=3 --retries=0
```

任何一次失敗 → 不升級。

## 4. Flaky 判定

Promotion 期間 retry 禁止掩蓋 flaky。

如果正常 CI 設定 retries > 0，而某測試第一次失敗、retry 成功：

```text
FLAKY → verify WARN
```

不得視為乾淨 PASS。

## 5. Promotion result

通過後記錄：

```yaml
maturity: ci-ready
promoted_at: YYYY-MM-DD
adapter: {adapter}
parallel_safe: true|false
environment_bound_fixture: true|false
cleanup: reliable|best-effort|none
```

這是 E2E 資產 metadata，不是 UAT，也不是 `state.json.results.verify` 的 replacement。
