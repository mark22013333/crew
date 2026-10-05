# plan-verify Phase: E2E Authoring

本檔由 [`../SKILL.md`](../SKILL.md) 的 E2E candidate 流程引用。

## 前提

只有在：
- runtime verify 沒有 FAIL / BLOCKED
- `.spec/{slug}/.cache/verification-ir.json` 可用
- E2E adapter 已解析

時才產生 candidate。

輸出預設：

```text
maturity = draft
```

不要宣稱 CI-ready。

## 1. 輸入

主要輸入：
1. Verification IR
2. framework adapter
3. project-local product knowledge / verify memory
4. 實際 E2E repo 現有測試風格

`verify.md` 只用來補人類描述，不可拿來重新猜 selector/action。

## 2. Scenario 組織

### 獨立 AC
若 AC 無共享昂貴 state，優先一 AC 一 test。

### Stateful product flow
若 login / fixture / shared state 很昂貴或 AC 天然連續，允許：

```ts
test('scenario', async ({ page }) => {
  await test.step('{slug}#AC-1: ...', async () => {});
  await test.step('{slug}#AC-2: ...', async () => {});
});
```

每個 step title 直接包含 `{slug}#AC-n`，避免 reporter 需要 fuzzy mapping。

獨立 test 可使用：

```js
annotation: { type: 'crew-ac', description: '{slug}#AC-1' }
```

若 precondition 不成立，使用 adapter 支援的 blocked contract。Stateful scenario 優先用 `crew-ac-status` 指定受影響的 `{slug}#AC-n`；若整支 scenario 都被阻擋，再對所有預計覆蓋 AC 寫 targeted BLOCKED 後 skip。舊版 Playwright 可用 `crew-ac-status` JSON attachment fallback。

## 3. Precondition 與 assertion

Candidate 必須把 precondition 與 product assertion 分開，例如 auth/session verify、fixture existence、dependency availability。

Precondition 失敗應能被 reporter 辨識為 blocked，而不是讓後面每條 AC 一起 fail。

## 4. Safety invariant

若 Verification IR 有 `forbid_request` 等 safety invariant，candidate 必須轉成 hard assertion / listener；不可因 soft assertions 而放寬。

## 5. Locator

優先採 adapter 定義的 CI-safe locator。

若 runtime 只靠 `ci_eligible=false` fallback 成功：
- candidate 加 TODO / FIXME
- maturity 保持 draft
- promotion gate 必須 BLOCK

## 6. Wait strategy

優先 web-first assertion、response / request、URL、DOM state。

固定 sleep 可暫留 draft 供診斷，但需要 TODO/理由；不可自動升 CI-ready。

## 7. 測試資料

Candidate 產出時同步建立 E2E repo 的 `.crew/e2e/{slug}.promotion.json` 初稿，schema 見 `../../references/e2e-promotion-schema.md`。

至少要標示：

- shared_mutation
- environment_bound_fixture
- unique_test_data
- disposable_environment
- parallel_safe / workers
- cleanup
- safety_invariants

hardcoded record ID 不必一律禁止，但必須反映為 environment-bound fixture；若會修改共享資料又只有 best-effort cleanup，maturity 必須維持 draft。

## 8. 產出後

1. test discovery
2. syntax/framework load
3. headed/headless 試跑（依 adapter）
4. 人工 review
5. 進入 `e2e-promotion.md`

Candidate 不自動 commit 到外部 E2E repo；Git write 仍由使用者／Host 權限決定。
