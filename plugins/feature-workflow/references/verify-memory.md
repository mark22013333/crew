# Verify Memory Contract

> 定義 `/plan-verify` 的三層驗證記憶、portable storage、precedence 與 legacy migration。記憶是操作加速資訊，不是驗收結果；驗收 truth 仍是 `state.json.results.verify`。

## 三層 storage

| Layer | Canonical storage | 共享 | 生命週期 |
|---|---|---|---|
| Layer 3 產品級 | project-local `.crew/products/{product_id}-memory.md` → plugin `products/{product_id}-memory.md` | 專案／plugin | 長期 |
| Layer 2 專案級 | repo `.crew/verify-memory.md` | Git commit / push | 中期 |
| Layer 1 任務級 | `.spec/{slug}/.cache/verify-memory.md` | 不共享 | 暫存 |

載入順序：Layer 3 → Layer 2 → Layer 1；越具體的後層可覆蓋前層。

## Layer 2 legacy compatibility

舊專案可能已有：

```text
.claude/verify-memory.md
```

Read contract：

1. `.crew/verify-memory.md` 存在 → 只讀 canonical。
2. canonical 不存在、legacy 存在 → 可讀 legacy。
3. 都不存在 → Layer 2 為空。

Write / promotion contract：

- 新寫入永遠寫 `.crew/verify-memory.md`。
- 若 promotion 時只有 legacy，可把 legacy 內容當 merge baseline，再建立 canonical。
- 不刪、不搬、不覆寫 legacy；遷移完成與否由 canonical 是否存在判斷。

## 記憶內容

可記錄：

- 有效/無效 selector
- 頁面操作 recipe
- wait strategy
- 穩定的環境差異
- 踩坑紀錄
- 專案統一 API 格式

不得記錄：

- Cookie / Token / 密碼 / API key
- 個資或 production secret
- 一次性測試資料
- 驗收 PASS/FAIL 作為權威結果

每個可失效條目應有 `last_verified: YYYY-MM-DD`。

### CI eligibility metadata

Runtime verification 能成功，不代表該知識適合產生長期 CI 測試。可重用 selector / recipe 建議額外記錄：

```yaml
selector:
  value: "#queryBtn"
  strategy: id
  stability: stable
  ci_eligible: true
  last_verified: 2026-10-04
```

`ci_eligible=false` 的典型案例：

- `nth-child` / 長 CSS chain / XPath 等脆弱 selector
- 依賴某次 session / popup / 暫時 DOM 結構
- hardcoded 一次性測試資料
- 只能靠固定 sleep 才成功的 recipe
- cleanup 不可靠的共享資料操作

`plan-verify` runtime 可使用 `ci_eligible=false` 的 fallback 來完成驗證，但 E2E authoring / promotion 不得把它當成 CI-ready 資產。

## Freshness

| 距今 | 語意 |
|---|---|
| ≤ 30 天 | fresh，可直接使用 |
| 31–90 天 | stale，需要確認；確認有效後刷新日期 |
| > 90 天 | expired，不使用舊值；重新探索 |
| 無日期 | 視為 stale |

踩坑紀錄屬 advisory，可永久保留。

## Promotion

Layer 1 有新資訊時，由 Human 決定是否升級到 Layer 2。

升級：

- 通用 selector
- 可重用 recipe
- 穩定 wait strategy
- 專案統一 API 行為

不升級：

- 一次性 workaround
- 測試資料
- session-specific state
- secret

Layer 2 → Layer 3 屬人工 curate，不由 `/plan-verify` 自動寫 plugin bundle。

若產品知識包含公司／客戶私有資訊，優先升級到 project-local `.crew/products/{product_id}-memory.md`，不要複製到公開 plugin bundle。

## 與 state 的邊界

Verify memory 只幫助「怎麼驗」。

真正「驗證結果是什麼」只能寫：

- `state.json.results.verify`
- `steps.verify`
- `plan.md` 檢查報告摘要

Memory 不得取代 evidence、state 或 Human UAT。
