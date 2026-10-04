# Verification IR Contract

> Verification IR 是 `/plan-verify` 在「執行驗證」與「產生 E2E 候選測試」之間的結構化中介格式。它是一次性 task cache，不是驗收 truth；真正結果仍是 `state.json.results.verify`。

## Canonical path

```text
.spec/{slug}/.cache/verification-ir.json
```

不得進版控；可隨 `.cache/` 清除。

## 為什麼需要 IR

禁止流程：

```text
瀏覽器結構化操作
→ verify.md 人話
→ 再猜回 selector/action/assertion
```

正確流程：

```text
runtime verification
→ Verification IR
├─ render verify.md
└─ E2E authoring
```

## Schema v1

```json
{
  "schema_version": 1,
  "slug": "example-feature",
  "scenario": "example-main-flow",
  "framework_adapter": "generic-playwright",
  "preconditions": [
    { "type": "authenticated", "role": "admin" }
  ],
  "safety": [
    {
      "type": "forbid_request",
      "method": "POST",
      "url_contains": "/dangerous/update"
    }
  ],
  "acs": {
    "AC-1": {
      "verification_type": "browser",
      "steps": [
        {
          "action": "goto",
          "path": "/example"
        },
        {
          "action": "click",
          "locator": {
            "strategy": "role",
            "role": "button",
            "name": "查詢"
          }
        }
      ],
      "assertions": [
        {
          "type": "visible",
          "locator": {
            "strategy": "role",
            "role": "table"
          }
        }
      ]
    }
  }
}
```

## v1 支援的 action

- `goto`
- `click`
- `fill`
- `select`
- `check`
- `upload`
- `press`
- `evaluate`
- `api_request`

不要把任意 JavaScript 當成第一選擇；`evaluate` 必須附上 recipe / reason。

## v1 支援的 assertion

- `visible`
- `hidden`
- `text`
- `value`
- `contains`
- `not_contains`
- `count`
- `url`
- `response_status`
- `response_body`

## Locator

優先保存語意，不要只保存最後成功的 CSS：

```json
{
  "strategy": "role",
  "role": "button",
  "name": "查詢",
  "fallback_selector": "#queryBtn"
}
```

可用 strategy：

- `role`
- `label`
- `testid`
- `id`
- `name`
- `css`
- `component`

`component` 交由 framework / product adapter 轉成實際操作。

## Safety invariant

`safety` 描述「驗證期間絕對不能發生」的副作用，例如：

- `forbid_request`
- `forbid_navigation`
- `forbid_delete`
- `allowed_mutation`

destructive / shared-environment scenario 若沒有 safety contract，不得升級成 CI-ready。

## AC identity

Join key 固定為：

```text
{slug}#AC-{n}
```

禁止再用 AC 文字 fuzzy matching 當唯一映射方式。
