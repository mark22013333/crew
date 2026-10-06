# plan-verify Phase: E2E Promotion

本檔由 `/plan-verify --e2e-promote` 使用，依 `../../references/e2e-ci-policy.md` 判定 E2E candidate 能否由 `draft` 升為 `ci-ready`。

## 前提

- candidate 已存在
- framework adapter 已解析
- candidate 目前 maturity = `draft`
- promotion metadata 使用 `../../references/e2e-promotion-schema.md`

本 phase 不重新判斷產品 AC；runtime truth 仍由 plan-verify / `--from-e2e` 負責。

## 1. Static gate

執行：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/lint-playwright-e2e.py" {candidate}
```

- HARD issue → promotion BLOCK
- REVIEW issue → 修正，或在 metadata 寫 `review_waivers` + reason
- HARD 不可 waiver

## 2. Environment gate

讀 promotion metadata：

```json
{
  "environment_gate": "not-required"
}
```

- `not-required` → 可進下一步
- `deferred` → 維持 draft

本 phase **不定義** environment/shared-state 細節。需要這類判定時只能標 `deferred`，交給獨立 environment policy。

## 3. Stability gate

至少：

1. discovery 成功
2. framework/config load 成功
3. headless 單跑成功
4. `retries=0`
5. `repeat-each >= 3`
6. 全部 repeat 成功

Generic baseline：

```bash
npx playwright test {file} --repeat-each=3 --retries=0
```

完成後，把 `discovery / framework_load / headless_pass / retries / repeat_each / passed / failed` 寫回 promotion metadata。

## 4. Fingerprint

取得目前 candidate SHA-256：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-e2e-promote.py" fingerprint \
  --candidate {candidate}
```

寫入 `stability.candidate_sha256`。Candidate 內容之後若修改，必須重跑 stability。

## 5. Machine promotion gate

執行：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-e2e-promote.py" check \
  --candidate {candidate} \
  --metadata .crew/e2e/{slug}.promotion.json
```

- exit 0 → 可標 `maturity=ci-ready`
- exit 1 → 保持 `draft`，依 blockers 修正
- exit 2 → metadata / schema / input 錯誤

## 6. 結果

通過：

```yaml
maturity: ci-ready
adapter: {adapter}
```

未通過：

```yaml
maturity: draft
blockers:
  - {code}: {reason}
```

Promotion 不修改 runtime verify result，也不取代 Human UAT。
