# plan-verify Phase: E2E Runner

本檔由 [`../SKILL.md`](../SKILL.md) 的 `--e2e` 模式引用。

## 目的

優先重用已存在、已維護的 Playwright E2E coverage；沒有 coverage 的 AC 回到 Verification Router，不強迫所有 AC 都走瀏覽器。

## 1. 解析 portable E2E contract

讀取 `projects/{repo-id}.md`：

```yaml
e2e_adapter: generic-playwright
e2e_workspace: ../e2e
e2e_profile: uat
e2e_command: npx playwright test
```

規則：
- `e2e_workspace` 以受測 application repo root 為基準，必須是相對路徑。
- `e2e_command` 在 E2E workspace 內執行。
- 舊 `e2e_repo` 只作 read compatibility；`e2e_profile` 保留為 canonical 邏輯 profile 欄位。
- Adapter resolution 見 `../../references/e2e-contract.md`。

若 workspace 不存在：
- 本機模式 → `BLOCKED`，說明 E2E repo 未提供。
- 不得猜工程師家目錄或自動 clone 未授權私有 repo。

## 2. 建立 AC coverage map

新 mapping 使用穩定 join key：

```text
{slug}#AC-n
```

允許來源：
1. test title / tag 內的 `{slug}#AC-n`
2. `test.step("{slug}#AC-n: ...")`
3. legacy `verify-map.json`

Legacy condition text fuzzy matching 只能 fallback，不得當新資產的 canonical mapping。

## 3. 執行

依 adapter 組合 command。Generic baseline：

```bash
npx playwright test {matched files}
```

若 project 有 profile env，由 adapter 提供，例如：

```bash
PROFILE={profile} npx playwright test {matched files}
```

不可由 CREW generic core 假設 `PROFILE` 一定存在。

## 4. 分類失敗

- framework 載入失敗 / profile 缺失 / auth 失敗 / fixture 失敗 → `BLOCKED`
- test assertion 確實失敗 → `FAIL`
- retry 後才成功 → `WARN / FLAKY`
- skip → `SKIP`，不得當 PASS

## 5. 輸出

收集 framework-native 執行結果與可用 evidence（例如 trace / screenshot / Playwright test status），再依穩定 AC mapping 寫入本次 verify 明細。

- 只有能明確映射到單一 `{slug}#AC-n` 的結果才可更新該 AC。
- suite-level failure 不得反推所有 AC 都是產品 FAIL。
- 沒有可靠 per-AC mapping 時，回到 Verification Router 驗證該 AC。
- state 寫入仍遵守 plan-verify 既有 `crew-state.py` 單一寫者規則。
