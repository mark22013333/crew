# E2E Framework Adapter Contract

> 定義 `/plan-verify` 如何把 Verification IR 轉成「符合目標 E2E repo 慣例」的候選測試。CREW 核心只定義 adapter contract，不硬編碼公司私有 framework 細節。

## Resolution precedence

若 `projects/{id}.md` 有 `e2e_adapter`：

1. 專案 repo `.crew/adapters/{e2e_adapter}.md`
2. plugin `adapters/{e2e_adapter}.md`
3. 找不到 → `generic-playwright`

產品知識亦採 project-local 優先：

1. 專案 repo `.crew/products/{product_id}.md`
2. plugin `products/{product_id}.md`
3. 找不到 → 通用模式

project-local knowledge 可包含公司內部 helper、路由、profile、元件 recipe；公開 plugin 不應要求把私有資訊複製進 bundle。

## projects/{id}.md

建議欄位：

```yaml
product_id: example-admin
e2e_adapter: company-admin-e2e
e2e_workspace: ../AdminE2ETest
e2e_profile: uat
e2e_command: npx playwright test
```

### Portable rule

- `e2e_workspace` 以**受測 application repo root** 為基準解析，必須是相對路徑；不得要求某位工程師的絕對家目錄。
- `e2e_command` 在解析後的 E2E workspace 內執行。
- credential / token / password 不得出現在 project config。
- `e2e_profile` 是邏輯識別，不是 secret container。
- CI 可以把 application repo 與 E2E repo checkout 到相同相對布局，讓同一份設定同時支援本機與 CI。
- 舊 `e2e_repo` 只作 read compatibility；新寫入不得再產生此欄位。

## Project-local adapter 起手式

需要公司／產品私有 framework 規則時，複製 [`e2e-adapter-template.md`](./e2e-adapter-template.md) 到：

```text
<application-repo>/.crew/adapters/{e2e_adapter}.md
```

再填入 import/global hooks、profile、auth、component recipe、fixture/cleanup 與 safety 規則。不要把 secret 或內部敏感資料搬進 public plugin。

## Adapter 最小欄位

Adapter 文件至少定義：

```yaml
id: generic-playwright
framework: playwright
language: typescript
import_style: "@playwright/test"
profile_env: null
supports:
  test_step: true
  storage_state: true
```

若 framework 使用自家 global hooks / config / auth helpers，應在 project-local adapter 說明。

## Authoring contract

E2E candidate 必須：

- 保留 `{slug}#AC-n` 穩定 join key
- 支援 stateful scenario 用 `test.step("AC-n: ...")`
- 不從 `verify.md` 重新猜操作；以 Verification IR 為主要輸入
- 不把 secret、一次性測試資料、session state 寫進測試
- framework adapter 可調整 import / auth / config / helper 寫法，但不得改寫 AC 語意

## 與 CI-ready 的邊界

產生出的測試預設 maturity：

```text
draft
```

`draft` 只代表「已形成可試跑的 E2E candidate」，不代表長期 CI 資產。後續若要升級成熟度，必須再經獨立 promotion policy；Runtime PASS 不等於 CI-ready。
