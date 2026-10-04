# plan-verify Phase: From E2E

本檔定義 `/plan-verify --from-e2e <crew-results.json>`。

目的：消費已在 CI / E2E runner 執行完成的結果，**不重新開瀏覽器**。

## 1. 驗證輸入

依 `../../references/e2e-result-schema.md` 驗：
- schema_version
- runner
- environment
- git_sha（若可得）
- results[]
- 每個 result 的 `{slug}#AC-n` join key

格式錯誤 → 停止，不寫 state。

## 1.5 Deterministic summarize

不要由 LLM 自己掃 JSON 算統計。先執行：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-e2e-results.py" summarize \
  --file {crew-results.json} \
  --slug {slug} \
  --expected-git-sha {目前受測 commit}
```

此腳本負責：
- schema / status / AC join key 驗證
- blocked 必須有 reason
- 只保留目前 slug，其他結果計入 ignored
- 同一 AC 多筆 coverage 採最差狀態聚合
- git SHA freshness
- deterministic counts / overall PASS|WARN|FAIL

Health Score 不在此腳本發明新公式，仍由 plan-verify 既有評分邏輯處理。

## 2. Scope

只消費目前 active slug 的 AC。

其他 slug 的 result：
- 忽略
- 在摘要顯示 ignored count
- 不得寫進目前 task state

## 3. Status mapping

| E2E | Verify |
|---|---|
| passed | PASS |
| flaky | WARN |
| failed | FAIL |
| blocked | BLOCKED |
| skipped | SKIP |
| manual | MANUAL |

若 result 缺 reason：
- failed 仍可 FAIL，但保留 runner error
- blocked 必須降為 schema error，因為無法判斷 blocking precondition

## 4. Evidence

保留 artifact pointer：trace、screenshot、video、reporter attachment。

不要把大型 binary 搬進 `plan.md` 或 `state.json`。

## 5. 寫回 Crew

重建本次 `.cache/verify.md`，然後只透過：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" result ...
```

寫入 status / health_score / passed / failed / blocked / skipped / manual / mode=e2e。

CI 本身不得 commit / patch `state.json`。

## 6. Freshness

若 result 的 git_sha 與目前受測 commit 明顯不一致：
- 標 WARN
- 不得把 stale CI result 宣稱為目前程式碼的最新驗收證據
