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

每個 step title 直接包含 `{slug}#AC-n`，避免後續工具需要 fuzzy mapping。

獨立 test 的 title 或 adapter-defined tag 也必須包含 `{slug}#AC-n`。

若 precondition 不成立，沿用 adapter 定義的 fixture/skip 慣例；不要把環境失敗改寫成產品 assertion。

## 3. Precondition 與 assertion

Candidate 必須把 precondition 與 product assertion 分開，例如 auth/session verify、fixture existence、dependency availability。

Precondition 與產品 assertion 必須分層，讓後續執行器可以區分環境失敗與產品失敗。

## 4. Safety invariant

若 Verification IR 有 `forbid_request` 等 safety invariant，candidate 必須轉成 hard assertion / listener；不可因 soft assertions 而放寬。

## 5. Locator

優先採 adapter 定義的 CI-safe locator。

若 runtime 只靠 `ci_eligible=false` fallback 成功：
- candidate 加 TODO / FIXME
- maturity 保持 draft
- candidate 必須維持 `draft`

## 6. Wait strategy

優先 web-first assertion、response / request、URL、DOM state。

固定 sleep 可暫留 draft 供診斷，但需要 TODO/理由；candidate 維持 `draft`。

## 7. 測試資料

Candidate 要標示：

```yaml
environment_bound_fixture: true|false
parallel_safe: true|false
cleanup: reliable|best-effort|none
```

hardcoded record ID 不必一律禁止，但必須能說明 fixture contract。

## 8. 產出後

1. test discovery
2. syntax/framework load
3. headed/headless 試跑（依 adapter）
4. 人工 review
5. 保存為 `draft` candidate；更高成熟度判定不屬本 phase

Candidate 不自動 commit 到外部 E2E repo；Git write 仍由使用者／Host 權限決定。
