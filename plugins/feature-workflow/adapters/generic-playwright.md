---
id: generic-playwright
framework: playwright
language: typescript
---

# Generic Playwright Adapter

> 公開 CREW 的預設 E2E framework adapter。專案若有自家 global hooks、auth helper、profile loader 或 component recipe，請在 repo 的 `.crew/adapters/{id}.md` 覆寫，不要修改本檔塞入私有細節。

## Runtime

```yaml
import_style: "@playwright/test"
profile_env: null
supports:
  test_step: true
  storage_state: true
  trace: true
```

## Authoring baseline

```ts
import { test, expect } from '@playwright/test';

test.describe('scenario', () => {
  test('feature-x#AC-1 coverage', async ({ page }) => {
    await test.step('feature-x#AC-1: example', async () => {
      await page.goto('/example');
      await expect(page.getByRole('main')).toBeVisible();
    });
  });
});
```

## Locator preference

CI candidate 優先：

1. `getByRole`
2. `getByLabel`
3. `getByTestId`
4. 穩定 ID / name
5. 簡單 CSS attribute

Runtime fallback 可更寬鬆，但 XPath、長 CSS chain、`nth-child` 等預設 `ci_eligible=false`。

## Waiting

優先等待可觀察條件：

- web-first assertion
- response
- URL
- element state

固定 `waitForTimeout` 只可作 draft diagnostics；E2E candidate review 應優先要求改成可觀察條件。

## Authentication

不得把帳密寫進測試。若需要 authenticated state：

- 由 CI secret / runtime profile 提供 credential
- 優先使用 setup project / storageState
- auth state 不進 Git


## CREW result reporter

Reference implementation：`references/playwright/crew-reporter.js`。

E2E repo 應自行 vendor/copy 或實作相同 `crew-results.json` schema，CI 不應依賴 CREW plugin 安裝路徑才能執行測試。

Convention：
- independent test：title / `crew-ac` annotation 包含 `{slug}#AC-n`
- stateful scenario：`test.step` title 直接包含 `{slug}#AC-n`
- whole-test precondition blocked：`crew-blocked` annotation
- selected AC outcome / partial coverage：`crew-ac-status` JSON annotation；舊 Playwright 可用同名 JSON attachment
