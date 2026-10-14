# Review Once Runner Runtime Contract (PR-C)

## Architecture

`/plan-run` is a **Host-driven synchronous loop**. The deterministic portion is `crew-state.py run` (single writer). It does not spawn agents, call models, promise background execution or replace existing workflow stage logic. 所有 `run` 指令都帶 `--slug {slug} --project .`。

兩種驅動者共用同一份 Runner 契約：

- **同 session 模式（`autonomy.proof=dialogue`）**：`/plan-run` 主對話自己跑迴圈（`skills/plan-run/phases/session.md`）。**不是無人值守**：session 結束即 paused，`/plan-run resume` 續跑。
- **trusted-host 模式（`autonomy.proof=signed`）**：`review-once-host.py` Bridge 驅動（`review-once-host.md`）；Bridge 拒絕 dialogue grant。

Runner 動作：

- `run start` requires an active grant（dialogue or signed）, not inferred/parked state, matching project/branch and no previous execution.
- `run next` reconciles previous inflight step against `steps.{step}.status`, retains exactly one in-flight dispatch, and outputs a deterministic next action. `inflight.command` 對 spec／db／arch 是 `review-once-apply.py --step X`，build 是 `/plan-build --with-test|--bdd [--resume] --review-once`；它是派工契約，不是已執行證據。`run next` 本身會刷新 heartbeat。
- `run heartbeat` records best-effort liveness but **does not renew `expires_at`**. A stale heartbeat is not proof a Host worker has stopped. 同 session 模式只在派 build 前後各呼叫一次；30 秒週期只屬 trusted-host Bridge。
- `run pause` records reason and blocks further dispatch（需同一個 owner）。
- `run resume` rechecks the grant（dialogue 重算 packet hash；signed 重驗簽章）、expiry and approved plan. A pending inflight operation requires `--reconcile --reason` and explicit proof old worker stopped. `--takeover` only after pause and explicit reason.
- `run reclaim --owner NEW --reason R` handles「Runner 仍是 `running` 但原 session 已死」：running→paused、stop_reason=`SESSION_LOST`、記錄舊 owner；之後仍須經 Human 確認舊 worker 停止才可 `resume --takeover --reconcile`。
- `run status` reads the current checkpoint; it is a status report, not proof of running processes.
- `run next` consumes the grant when `build=done`, `work_unit` clear and approved Gate / latest snapshot checks pass → `completed_build`.
- `autonomy.target_step=arch` 時，arch 完成且 architecture Gate 通過 → `completed_plan`、stop_reason=`PLAN_DONE`、grant consumed，不進 build。
- If proof, time, branch or plan contract differs from approved packet, `run` fails closed, marking active execution paused（stop_reason=`GRANT_OR_SCOPE_INVALID`）.

## Valid Dispatch

```text
Human-approved packet（dialogue：主對話核准題；signed：Host 簽章事件）
    ↓ plan-start --from-review-once（dialogue：packet verify；signed：review-once-proof.py）
    ↓ crew-state grant issue（dialogue 時限從此刻起算）
    ↓ run start
    ↓ run next: spec   → review-once-apply.py --step spec
    ↓ run next: db     → review-once-apply.py --step db
    ↓ run next: arch   → review-once-apply.py --step arch
    ↓   （--until arch → completed_plan, PLAN_DONE, grant consumed）
    ↓ run next: build  → /plan-build --with-test|--bdd --review-once
    ↓ run next: completed_build, grant consumed
```

Each `review-once-apply.py` invocation:
- Requires an active Runner checkpoint and a matching approved proposal（dialogue or signed grant）.
- Inserts approved lines at the existing plan.md anchors without changing their six sections or overwriting unrelated content.
- Validates exact Goal/AC/Spec/DB/Architecture content, full plan <=100 lines, SQL draft identity and live Grant; only `crew-state.py` writes `state.json`.
- Calls normal state transitions and `grant approve-requirement` / `approve-architecture` (no fake `--by human`).

`review-once-build.py` checks the real checked-out Git branch and changed product paths against packet's scoped allowlist (pre/post Build). Production write scopes require **Host-enforced access limits**; Git scanning is defense in depth, not prevention.

## Failure behavior

No approved grant → no Review Once execution. No long-running dispatch capability → report not supported rather than claim background work. No reliable worker cancellation → do not auto-take over in-flight work. Exception/failure → pause, preserve state, and ask the Human at the stop point（`skills/plan-run/SKILL.md` 停止點 A～D，不提供「跳過」）. The Runner is not a security principal: `owner` is cooperative metadata only, not an authentication secret.

## Tests

Executable tests live in the repo-root `scripts/lint-review-once-runner.py`（repo 根 `scripts/`，**不隨 plugin 安裝**）。They cover successful Spec→DB→Arch→Build path, duplicate dispatch suppression, incomplete Build, pause/resume, revoke, expired Grant and UAT untouched.
