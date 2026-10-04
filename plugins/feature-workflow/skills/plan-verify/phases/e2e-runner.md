# plan-verify Phase: E2E Runner

本檔由 [`../SKILL.md`](../SKILL.md) 的 `--e2e` 模式引用。

## 目的

優先重用已存在、已維護的 Playwright E2E coverage；沒有 coverage 的 AC 回到 Verification Router，不強迫所有 AC 都走瀏覽器。

## 1. 解析 portable E2E contract

讀取 `projects/{repo-id}.md`：

```yaml
e2e_adapter: generic-playwright
e2e:
  workspace: ../e2e
  profile: uat
  command: npx playwright test
  results: test-results/crew-results.json
```

規則：
- `e2e.workspace` 必須是 repo/workspace-relative。
- 舊 `e2e_repo` / `e2e_profile` 只作 read compatibility。
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
1. E2E result / reporter metadata
2. test annotation / tag
3. `test.step("AC-n: ...")`
4. legacy `verify-map.json`

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

優先要求 runner 產出 `../../references/e2e-result-schema.md` 格式的 `crew-results.json`。

若 legacy runner 尚未支援：
- 可讀 Playwright JSON reporter 結果轉成 schema v1
- 但不得只 parse console 人話字串

最後再把 result 轉成 `.cache/verify.md` 與 `state.json.results.verify`。
