# plan-verify Phase: 前置條件與 BLOCKED

本檔由 [`../SKILL.md`](../SKILL.md) Step 3.5 / Step 5 引用。

## 核心語意

**前置條件失敗不等於產品功能失敗。**

驗證結果新增 `BLOCKED`：

| 狀態 | 語意 |
|---|---|
| PASS | AC 已被可靠 evidence 證明 |
| WARN | 功能通過，但 evidence / selector / 環境有疑慮 |
| FAIL | 前置條件成立，且受測功能明確不符合 AC |
| BLOCKED | 沒有資格判定功能；環境、登入、fixture、依賴服務等前置條件不成立 |
| SKIP | Out of Scope、不適用、使用者明確略過 |
| MANUAL | 必須由人確認 |

## 常見 BLOCKED

- 登入 helper 回報成功，但真正受保護頁面仍不可用
- 測試資料 seed / fixture 建立失敗
- 必要 UAT / API / DB / VPN 不可達
- 既有固定資料與測試假設不一致
- profile / credential 未設定
- 依賴服務 5xx 導致目標頁無法載入
- cleanup 前置要求不成立，繼續跑會污染共享環境

## Precondition Gate

每個 scenario 在開始驗 AC 前，應先做最小、具判別力的前置條件檢查。

錯誤示範：

```text
login helper 印「登入完成」 → 當成已登入
```

正確方向：

```text
login helper
→ 開啟真正需要權限的頁面
→ 同時驗證 HTTP / DOM 中的受保護資源
→ 成功才進入 AC 驗證
```

## 結果處理

- BLOCKED **不計入 FAIL 數**。
- BLOCKED 會讓整體 verify 結論至少為 `WARN`，除非所有 BLOCKED 都對應已接受的 skip contract。
- `.cache/verify.md` 要明列 blocking reason 與已收集到的 evidence。
- `state.json.results.verify` 應記錄 `blocked={N}`。
- `--recheck` 預設重新跑 FAIL + BLOCKED；SKIP / MANUAL 不自動重跑。
- BLOCKED 不得被 retry 後的偶然成功靜默吞掉；若曾 BLOCKED 但重試成功，報告中保留 diagnostics。

## Safety precondition

若 scenario 會修改共享資料，執行前也要確認：

- 是否有可靠 cleanup
- 是否使用唯一測試資料
- 是否只允許白名單 mutation
- 是否有 forbidden request / forbidden action invariant

若沒有可靠隔離，仍可做本機／人工驗收，但要在結果中明確標示風險，不得把環境污染誤報成功能結果。
