# BDD Test-First（`/plan-build --bdd`）

> 本契約只在使用者明確指定 `--bdd` 時啟用。不改動 `/plan-build` 原本測試預設、Human approval、`state.json` 單一寫者或 Feature lifecycle。

## 前置條件

- 需求規格與架構已經分別由 Human approve；如果任何新增／修訂 Sxx 影響語意，回 `/plan spec` 重新 approve 後才能開始。
- `plan.md` 的 `crew:ac` 需至少有一個 Sxx，完整 key `{slug}#AC-n#S01`。未宣告 Sxx 的 AC 仍由後續一般 `/plan-verify` 驗收。
- 在專案現有測試目錄建立測試，不在 `.spec/` 新增永久文件或源碼。Gherkin 是選用，JUnit／pytest／Playwright 皆可由 adapter 輸出既有 `crew-results.json` schema v1。
- Java 可用內建 `crew-bdd-junit.py` 轉換 Surefire／Gradle JUnit XML；`@DisplayName` 或方法名稱需包含 `{slug}#AC-n#Sxx`。`<failure>` 是斷言失敗，`<error>` 映射 BLOCKED，`<skipped>` 映射 SKIP。
- `--bdd --no-test` 拒絕、`--dry-run` 僅呈現計畫，不呼叫寫入與測試，不得標示 RED/GREEN。
- 測試命令與結果由實際專案環境決定；若無可執行 runner/adapter，明確 BLOCK，不能假裝有 BDD。

## 可稽核的執行順序

```text
Human requirement + architecture approval
      ↓
Read approved AC/Sxx + discover real runner
      ↓
test-engineer: tests/fixtures/runner only (no production code)
      ↓
Run tests → .spec/{slug}/.cache/bdd-red.json
      ↓
crew-bdd-gate.py --phase red          [BLOCK if no behavioral failure]
      ↓
crew-state.py unit: RED evidence pointer
      ↓
backend / api / frontend / DB: allowed scopes
      ↓
Rerun same suite → .spec/{slug}/.cache/bdd-green.json
      ↓
crew-bdd-gate.py --phase green --red-results ... [BLOCK if any incomplete]
      ↓
crew-state.py unit --clear; set --step build --status done
```

### JUnit XML 轉換範例

JUnit 5 可在 `@DisplayName` 放入 `reservation#AC-1#S02`；RED 與 GREEN 必須各自重新執行測試，勿沿用舊 XML。

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-bdd-junit.py" \
  --junit-xml target/surefire-reports/TEST-BookingTest.xml \
  --output .spec/{slug}/.cache/bdd-red.json \
  --environment local --run-id red-{run-id}

# 實作產品碼之後重新執行相同 JUnit 測試，再轉換新 XML
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-bdd-junit.py" \
  --junit-xml target/surefire-reports/TEST-BookingTest.xml \
  --output .spec/{slug}/.cache/bdd-green.json \
  --environment local --run-id green-{run-id}
```

可多次提供 `--junit-xml`，但至少要有一筆有效 `{slug}#AC-n#Sxx` 測試結果。
`crew-bdd-gate.py` 的使用：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-bdd-gate.py" \
  --plan .spec/{slug}/plan.md --slug {slug} \
  --phase red --results .spec/{slug}/.cache/bdd-red.json

python3 "${CREW_PLUGIN_ROOT}/scripts/crew-bdd-gate.py" \
  --plan .spec/{slug}/plan.md --slug {slug} \
  --phase green --results .spec/{slug}/.cache/bdd-green.json \
  --red-results .spec/{slug}/.cache/bdd-red.json
```

- RED：每個宣告 Sxx 都要有 `scenario_id` 與 `coverage=full`，只有 `passed`／`failed` 可接受，至少一筆 `failed` 必須附失敗原因。**Leader 還必須人工檢視實際失敗訊息屬於產品 assertion**，不是 missing fixture/權限/載入失敗。
- GREEN：RED 證據仍有效，所有 Sxx 都 `passed + full`，runner 必須重新執行；同一檔、相同非空 `run_id`、相同 payload 都拒絕。
- Runner 提供的 JSON 為證據而非安全邊界；此 script **不能保證實際執行順序、測試來源可信或未竄改測試**。流程必須依 Git diff、unit checkpoint、命令輸出與 Human review 交叉核對。
- RED/GREEN 證據暫存在 gitignored `.cache/`；`state.json` 的進度與指標仍只能由 `crew-state.py` 寫入。不可把整份 test log 放到 `plan.md`。
- `--bdd --resume` 必須重新驗證之前的 RED 和核准情境，若 RED 遺失、規格變更或不能證明是在改產品碼之前產生，立即 BLOCK；若使用者選擇改回一般 `--with-test`，須明確回報不再滿足 Test-First。
- `build=done` 需要通過 GREEN。Machine Verify 與 Human UAT 仍分離；此 gate 不替代後續 `/plan-verify`、`/plan-review` 或 `/plan-close`。
