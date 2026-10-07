# UAT Approval Gate Contract

> 本檔定義「人類 UAT」的語意與 Phase 3B 漸進導入策略。
> `/plan-verify` 的機器驗證、`/plan-review` 的程式碼審查、UAT 是三種不同證據，不能互相冒充。

---

## 1. 三層驗收語意

| 層級 | 事實來源 | 回答的問題 | 可以自動完成嗎 |
|---|---|---|---|
| Machine Verify | `state.json.results.verify` + `steps.verify` | 功能是否符合可機器驗證的 AC？ | 可以 |
| Code Review | `state.json.results.review` + `steps.review` | 程式碼品質／邏輯／效能是否可接受？ | 可以由 reviewer agent 執行 |
| Human UAT | `state.json.gates.uat` | 使用者是否接受目前行為、流程與交付結果？ | **不可以** |

**硬規則：`verify=PASS` ≠ `uat=approved`。**

即使所有 AC 都 PASS，也可能存在：

- 業務流程不符合實際操作習慣
- UI/UX 雖符合 AC，但使用者不接受
- 測試環境資料與真實使用情境不同
- 使用者臨時發現需求理解偏差
- 使用者決定暫緩上線

因此 UAT 必須是獨立的人類決策。

---

## 2. UAT Gate schema

沿用共用 Approval Gate：

```json
{
  "gates": {
    "uat": {
      "status": "pending | approved | rejected | waived",
      "at": "ISO-8601 | null",
      "by": "human | <identity> | migration | null",
      "reason": "string | null"
    }
  }
}
```

- `pending`：尚未取得本輪 UAT 決策。
- `approved`：人類明確接受目前交付。
- `rejected`：人類不接受；必須回到修正流程。
- `waived`：明確決定本任務不做 UAT；**必須提供 reason**。

Agent 不得自行把 UAT 設成 `approved` 或 `waived`。

---

## 3. 決策時機（type-aware）

### Feature

```text
review=done
   ↓
human UAT decision
   ↓
uat=approved|rejected|waived
   ↓
plan-close
```

Feature 的 `crew-state.py gate --name uat ...` 只有在 `steps.review.status` 已是 done/skipped 時才接受非 pending 狀態，避免 review 尚未完成就先蓋 UAT 章。

**快速結案**（`/plan-close` 的人類決策，見該 skill『快速結案』一節）可把未完成的 security／verify／review 標成 `skipped`（runtime 要求 `--by` 與 `--reason`）。review 變成 `skipped` 只代表 UAT 可以開始決策，`gates.uat` 仍為 `pending`，`close=done` 照樣被 `TRANSITION_GATES["close"]` 硬擋，直到人類本輪核准；跳過檢查不是 UAT，也不是 waiver。

### Bug

Bug workflow 沒有 Feature 的 `review` lifecycle，因此 **不得硬套 `review=done` prerequisite**：

```text
bug-fix evidence / C1-C4
   ↓
/bug-close 顯示修復摘要
   ↓
human explicit acceptance
   ↓
uat=approved|rejected|waived
   ↓
bug-close
```

Runtime 對 `type=bug` 的 UAT 不要求 `review` source step；真正的決策時機由 `/bug-close` 的明確人類 acceptance 流程執行。

這不是放寬人類核准，而是把 prerequisite 對齊兩種 workflow 的實際 lifecycle。

---

## 4. `/plan-verify` 邊界

`/plan-verify` 只負責機器／瀏覽器驗證、`results.verify`、`steps.verify`、證據與摘要。

`/plan-verify` **不得**：

- 寫 `gates.uat=approved`
- 把「全部 PASS」描述成「UAT 通過」
- 因使用者按 Enter 開始 verify 就推定 UAT 同意
- 因 `--manual` 模式有人逐步操作，就自動視為 UAT

`--manual` 只是驗證執行方式，不是 Approval Gate。

---

## 5. Close hard gate（已啟用）

Feature 與 Bug 都已有合法 Human UAT 路徑後，runtime 正式啟用：

```python
TRANSITION_GATES["close"] = ["uat"]
```

因此 `crew-state.py set --step close --status done` 只有在 `uat=approved|waived` 時才能成功。

### Feature

- review 完成後，`/plan-next` 指向 `/plan-close`，把它當成 Human UAT + 結案入口。
- `/plan-close` 每次執行都先 reset `uat=pending`，避免沿用舊 acceptance，再取得本輪使用者明確決策。
- 接受 → `uat=approved`；要求修改 → `uat=rejected` 並停止。

### Bug

- `/bug-close` 每次執行都先 reset `uat=pending`，顯示修復摘要與 C1-C4，再取得本輪使用者 acceptance。
- 接受 → `uat=approved`；要求修改 → `uat=rejected` 並停止。

### Legacy v1

v1 Feature 相容模式不呼叫 `crew-state.py`，因此不經此 runtime transition gate；這是既有 legacy 隔離策略，不是 UAT waiver。

## 6. 人類決策寫入

UAT 通過：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" gate --slug {slug} \
  --name uat --status approved --by human \
  --reason "user explicitly accepted current delivery"
```

UAT 不通過：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" gate --slug {slug} \
  --name uat --status rejected --by human \
  --reason "user requested changes: ..."
```

明確 waiver：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" gate --slug {slug} \
  --name uat --status waived --by human \
  --reason "..."
```

> 指令只是狀態寫入方式；真正前提永遠是人類剛剛明確做了該決策。
