# plan-run 模式 2：同 session 一次審查連跑

> 由 `../SKILL.md` 步驟 1 選 2（或 `--mode session`／`--mode review-once`）進入。三題設定與 packet 核准題的文案在 SKILL.md，本檔只描述機制。
>
> **誠實定位**：dialogue grant 的 packet hash 只保證「套用的＝審過的」，信任等級等同 Interactive 的 `gate --by human`，不是不可偽造的核准。本模式**不是無人值守**：迴圈在目前對話裡同步執行，session 結束即 paused，`/plan-run resume` 續跑。

## S1. 唯讀探索與 Review Packet

1. 以 `delegate_readonly` 探索 Spec、DB、Architecture、allowed paths；不修改正式 `plan.md`、`state.json` 或程式碼。
2. 依第二層三題填 draft：
   - `test_policy`：`--test` 的值（`with_test`／`bdd`）。選 `bdd` 時每條需 Test-First 的 AC 必須含 Sxx；深度依 `--scenarios`（none／risky／all），未給旗標時探索用 `risky`（只標高風險或有歧義的 AC）。
   - `db.required`：由探索依 D-1 判斷填入，供 Human 審查，不另外詢問。
   - 不加入 `git_commit`：packet 白名單沒有它，本模式固定不允許 commit。
3. 寫 `.spec/.drafts/{proposal_id}/draft.json`（gitignored）並產生 packet：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
python3 "${CREW_PLUGIN_ROOT}/scripts/review-once-packet.py" prepare \
  --draft .spec/.drafts/{proposal_id}/draft.json \
  --output .spec/.drafts/{proposal_id}/packet.json
```

4. 向使用者展示**整份** packet：Goal、AC／Sxx、DB SQL、Architecture、允許修改的路徑、測試策略、明確禁止的動作、目標站（`--until`）、時限（從 grant 簽發起算）與 `packet_sha256`。
5. 問 SKILL.md 的 packet 核准題。選 2（修改）→ 重產 draft 與 packet，舊 sha 作廢；選 3（取消）→ 結束，零 side effect。只有選 1 才進 S2。

## S2. 建任務與簽發 dialogue grant

1) 在 Skill 層呼叫 `/plan-start` 建 skeleton／task／branch（dialogue 路徑以 `review-once-packet.py verify` 驗 hash，不跑 `review-once-proof.py`）：

```text
/plan-start --from-review-once --proof dialogue \
  --packet .spec/.drafts/{proposal_id}/packet.json --approved-sha {packet_sha256}
```

2) 綁定同一份 packet；`N` 為所選時限秒數（4h=14400、2h=7200、1h=3600）：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" grant \
  --slug {slug} --action issue --proof dialogue \
  --packet .spec/.drafts/{proposal_id}/packet.json --approved-sha {packet_sha256} \
  --max-duration {N} --until {build|arch} --project .
```

- grant 寫入 `autonomy.proof=dialogue`、`autonomy.by=human-dialogue`、`autonomy.target_step={until}`；**時限從這一刻起算**（在 plan-start 之後），不是從 packet 產生起算。
- 第 1 步若 BLOCK（hash 不符、slug／branch 衝突）→ 停在未授權狀態，回報原因，不得改走其他路徑硬建任務。
- 第 2 步失敗 → 不得執行任何 Spec 或 Build。

## S3. 主對話迴圈（上限 6 站）

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" run \
  --action start --owner dialogue-{YYYYMMDDHHMMSS} --slug {slug} --project .
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" run \
  --action next --owner dialogue-{YYYYMMDDHHMMSS} --slug {slug} --project .
```

`run next` 輸出的 `inflight.step`／`inflight.command` 是**派工契約，不是已執行的證據**：

| `inflight.step` | 主對話實際執行 |
|---|---|
| `spec` | `review-once-apply.py --step spec`：寫入核准的 Goal／AC／Spec，經 `grant approve-requirement` 過 Gate |
| `db` | `review-once-apply.py --step db`：只產核准 SQL，不在 DB 執行 |
| `arch` | `review-once-apply.py --step arch`：套用核准 Architecture，經 `grant approve-architecture` 過 Gate |
| `build` | 派 build 前 `run heartbeat` → 在 Skill 層呼叫 `/plan-build --with-test --review-once` 或 `/plan-build --bdd --review-once`（依 packet `test_policy`）→ 派完後再 `run heartbeat` |

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
python3 "${CREW_PLUGIN_ROOT}/scripts/review-once-apply.py" \
  --project . --slug {slug} --step {spec|db|arch}
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" run \
  --action heartbeat --owner dialogue-{YYYYMMDDHHMMSS} --slug {slug} --project .
```

- 每站完成後再呼叫 `run next` 對帳並取下一站；`run next` 本身會刷新 heartbeat，所以只在**派 build 前後各一次**明確呼叫 `run heartbeat`（30 秒週期只屬 trusted-host Bridge）。
- `run next` 發現未對帳的 `inflight` 只回 BLOCKED，不會重複派工。
- worker 回報 NEED_HUMAN → 由 Leader 帶回主對話，走 SKILL.md 停止點 B。
- 迴圈超過 6 站仍未結束 → 視為異常，`run pause` 後回報，不得繼續。

## S4. 結束條件

| `run next` 結果 | 意義 |
|---|---|
| `completed_build` | `build=done`、`work_unit` 清空、Gate 正確且授權有效；grant consumed。之後 Security／Verify／Review／close 照 Interactive 由 Human 推進 |
| `completed_plan`（stop_reason `PLAN_DONE`） | `--until arch` 且 arch 完成、architecture Gate 通過；grant consumed，不進 build。之後用 `/plan-build` 互動執行 |
| `paused`（`GRANT_OR_SCOPE_INVALID`／到期） | 已自動暫停 → SKILL.md 停止點 D |
| TEST_FAILED／E0-E3／E8 | SKILL.md 停止點 A |
| 範圍衝突 | SKILL.md 停止點 C |

## S5. session 結束

- 使用者要離開時，主對話先執行 `run --action pause --reason USER_PAUSED`（帶同一個 owner 與 `--project .`）。
- 來不及暫停（關掉視窗、Host 崩潰）時 Runner 會停在 `running`；下次 `/plan-run resume` 由 SKILL.md 的 resume 分流先 `reclaim`（running→paused、stop_reason `SESSION_LOST`），再經「原 worker 已停止？」確認後續跑。
- 時限不會因暫停而延長；到期後只能重審新 packet 或轉 Interactive。
