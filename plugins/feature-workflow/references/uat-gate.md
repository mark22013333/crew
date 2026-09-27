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

## 3. 決策時機

Phase 3B contract：

```text
review=done
   ↓
human UAT decision
   ↓
uat=approved|rejected|waived
   ↓
plan-close
```

`crew-state.py gate --name uat ...` 只有在 `steps.review.status` 已是 done/skipped 時才接受非 pending 狀態。
理由：避免在驗證／review 尚未完成前先蓋 UAT 章，之後程式又變更。

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

## 5. `/plan-close` 漸進導入

### Phase 3B-3A（目前）

- `crew-state.py next` 在 review 完成但 UAT pending/rejected 時，**不推薦 `/plan-close`**。
- `uat` 只能在 review 完成後決策。
- **尚不把 `close` 加進 `TRANSITION_GATES`**。
- `/plan-close` 必須明確區分 verify/review 與 UAT；legacy compatibility 下仍能直接 close，不代表 UAT 已完成。

這一階段先驗證資料模型與流程語意，不突然讓既有 close automation 全部失敗。

### Phase 3B-3B（下一決策點）

確認既有流程無相容性問題後，再評估：

```python
TRANSITION_GATES["close"] = ["uat"]
```

若啟用，`crew-state.py set --step close --status done` 才會成為真正 UAT hard block。

---

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
