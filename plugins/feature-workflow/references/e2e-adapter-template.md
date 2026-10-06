# Project-local E2E Adapter Template

> 複製本檔到受測 application repo 的 `.crew/adapters/{adapter-id}.md`，填入該公司／產品實際 E2E framework 規則。不要把私有 route、帳密、內部 repo URL 回寫 public CREW plugin。

```markdown
---
id: {adapter-id}
framework: playwright
language: javascript
---

# {Product} E2E Adapter

## Import contract

- test / expect 來源：{例如 custom global-hooks 或 @playwright/test}
- config loader：{helper / module；沒有則填 none}
- 共用 commands：{helper modules；沒有則填 none}

## Runtime profile

- profile env：{例如 PROFILE；沒有則填 none}
- base URL 來源：{config / env / Playwright baseURL}
- profile 檔是否含 secret：{yes/no}
- secret storage：{CI secret / gitignored local profile}

## Authentication

- login helper：{名稱或 none}
- 登入成功的**可靠證據**：{受保護 endpoint / DOM / cookie contract}
- helper 自己的 log 是否可信：{yes/no + 注意事項}
- auth state 是否可重用：{storageState / session / none}

## AC mapping

- canonical join key：`{slug}#AC-n`
- independent test：{annotation/tag 寫法}
- stateful scenario：`test.step('{slug}#AC-n: ...')`
- whole-scenario blocked：{framework 如何讓 reporter 輸出 blocked + reason}
- targeted AC blocked：`crew-ac-status` JSON，至少含 `ac/status=blocked/reason`
- partial coverage：`crew-ac-status` JSON，含 `ac/coverage=partial/reason`
- runtime metadata compatibility：新 Playwright 可用 `testInfo.annotations`；要支援舊版時，同步 `testInfo.attach('crew-ac-status', { body: JSON... })`

## Component recipes

### {component-name}

- detect：{selector / JS condition}
- action：{操作步驟}
- assertion：{可觀察完成條件}
- CI-safe：{yes/no}
- fallback：{若有}
- 禁止：{已知會造成 flaky / side effect 的做法}

## Wait strategy

優先順序：
1. {web-first assertion}
2. {response / URL / model state}
3. {component-specific condition}

固定 sleep 只有在無事件／狀態可觀察時使用，並記理由。

## Fixture contract

- seed：{API / DB / existing record / none}
- unique test data：{規則}
- environment-bound fixture：{true/false}
- parallel safe：{true/false}
- cleanup：{reliable/best-effort/none}
- workers 限制：{例如 1 / unrestricted}

## Safety invariants

- forbidden requests：{method + path pattern}
- forbidden actions：{delete/create/update 等}
- allowed mutations：{白名單}
- hard assertion：{如何在 teardown/finally 驗}

## Reporter

- CREW reporter：{vendor path / custom reporter}
- output：`crew-results.json`
- trace/screenshot/video：{artifact policy}

## Known environment differences

| 差異 | 哪些環境 | 驗證處理 |
|---|---|---|
| {field/feature} | {uat/local/...} | {count check / BLOCKED / skip contract} |

## Known pitfalls

- {helper 成功訊息不代表 session 成功}
- {某元件直接 fill 不會同步}
- {某資料無法 cleanup}
```

## 寫入原則

Adapter 可以保存：
- framework 慣例
- helper 名稱
- component recipe
- environment behavior
- fixture / cleanup policy

Adapter 不得保存：
- password / token / cookie
- 個資
- production secret
- 一次性 session 資料
- 客戶資料內容本身

若資訊只是單一任務的 workaround，先留在 task-level verification memory，不要直接升級 adapter。
