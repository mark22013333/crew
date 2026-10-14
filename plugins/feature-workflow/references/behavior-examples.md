# Behavior Examples Contract（BDD 漸進導入）

> 這是 CREW 既有 `/plan spec → /plan-build → /plan-verify` 的延伸，不是獨立的新 workflow。參考 Specification by Example / Discovery–Formulation–Automation 的精神；**Gherkin 為選用，不是所有 Host 或技術棧的依賴**。

## Discovery（找出可觀察的規則）

- 新需求仍先經 Intake Refiner + Human confirm；Intake **只確認意圖**，不提前產 AC 或架構。
- 由 `/plan spec` 針對每條 AC 思考正常、失敗／例外／權限、邊界與狀態轉換；僅保留能區分行為的最少案例。
- **附多少例由 Human 決定**：`/plan spec` 在派工前（1-0）以 `ask_user` 問 Sxx 深度——`none`（不附）／`risky`（只標高風險或有歧義的 AC，標「建議」但不是預設）／`all`（每條 AC 都附，之後可走 BDD Test-First）——或由 `--scenarios none|risky|all` 旗標指定；答案記在 `state.json.testing.scenario_depth`。AI 不代選，沉默、Enter 不算，headless 無旗標 BLOCK。
- 如果「包含起訖時間」或權限等行為尚未有業務決定，**標記為歧義交由 Human 決定**，不得由 AI 猜測後當成既定規格。
- 純重構、環境設定、無業務行為可觀察的任務沿用現行 AC，不強迫產案例。

## Formulation（不破壞 plan.md）

既有 `plan.md` 每條 AC **只佔一行**，有必要時同一行加精簡例子：

```markdown
- [ ] AC-1 同一會議室的預約時段不得重疊｜例：S01 正常：無衝突時成功；S02 衝突：重疊時拒絕；S03 邊界：首尾相接可預約（示意規則，正式使用前需 Human 確認）
```

- 寫入「可觀察的前置狀態／行為／結果」，不得寫 Controller 路徑、CSS selector、Step Definition 或測試框架細節。
- `S01`、`S02` 在同一 AC 內遞增且不重用；完整身分為 `{slug}#AC-n#S01`。**AC-n 仍是唯一驗收 join key**，Scenario 只做細分追溯。
- 此格式是精簡的行為範例而不是可直接執行的 `.feature`；需要可執行 BDD 時，使用者在應用專案的既有測試目錄維護 `.feature` / JUnit / Playwright，並保持 scenario_id 對應。
- `plan.md` 保持六個章節、`AC ≤15 行`、全檔 `≤100 行`；不要另建 `.spec/{slug}/scenarios.md`、不要為湊數強制每 AC 三例。
- 深度語意：`none` → AC 不附例；`risky` → 只對高風險／歧義 AC 附例；`all` → 每條 AC 至少 `S01 正常`＋`S02 例外`、最多 3 例（只有 `all` 能讓每條 AC 走 Test-First，代價是每個 Sxx 都要 GREEN 才能 `build=done`，UI 類情境容易 BLOCKED；`all` 時注意 AC 行長與全檔 100 行上限）。
- 規格與情境皆須 Human 明確核准；語意變更先將 requirement gate 設為 pending，再重新核准。Approval 不得由 Agent 代行。

## Automation（逐情境可追溯）

- `/plan-verify` 對已核准的 Sxx 逐一驗證，缺少、BLOCKED、MANUAL、SKIP、部分證據均不得讓所屬 AC 宣稱完整 PASS。
- 若透過 `--from-e2e`，結果項目的 `scenario_id` 為 `{slug}#AC-n#Sxx`；`crew-e2e-results.py summarize --plan .spec/{slug}/plan.md` 以規格宣告的案例清單核對，**只在全部已宣告案例均有 full + passed 證據時才允許 AC PASS**。
- 未附案例的舊 AC 與舊 CI JSON 不受新 ID 欄位影響；不可把沒有 scenario_id 的歷史結果拿來證明已宣告的 Sxx。
- `Verification IR` 可以選用每個 AC 的 `scenarios[]`，不得從人類摘要反推 selector/action；E2E candidate 保留 draft → promotion gate。
- `Machine Verify ≠ Code Review ≠ Human UAT`。不更改 `state.json` 的單一寫者、Host adapter 或結案權限。

## 選用 Test-First 實作

`/plan-build --bdd` 的完整順序與 runner/gate/checkpoint 規則見 `bdd-test-first.md`。原本 `/plan-build`、`--with-test`、`--no-test` 行為不變；`--bdd` 不可和 `--no-test` 併用，且不能以假的 RED 或環境錯誤代替產品 assertion 失敗。可用 JUnit、Playwright 或其他能提供 `crew-results.json` 結果的 adapter，不要求 Gherkin。

## 例子品質檢查

1. 能否用相同 Given、不同 When/Then 區分正常與拒絕行為？
2. 時間、數量、權限及重試等邊界是否可能改變產品行為？
3. 是否存在未經 Human 確認的假設？若存在先列為歧義。
4. 能否指出每個已宣告 Sxx 的可執行測試與 evidence？做不到只能回報待驗證，不能標 PASS。
