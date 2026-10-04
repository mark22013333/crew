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
  test('AC coverage', async ({ page }) => {
    await test.step('AC-1: example', async () => {
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

固定 `waitForTimeout` 只可作 draft diagnostics；promotion gate 會要求理由或替換。

## Authentication

不得把帳密寫進測試。若需要 authenticated state：

- 由 CI secret / runtime profile 提供 credential
- 優先使用 setup project / storageState
- auth state 不進 Git
