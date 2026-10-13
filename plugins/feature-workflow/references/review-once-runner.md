# Review Once Runner Runtime Contract (PR-C)

## Architecture

`/plan-run` is a **Host-driven synchronous loop**. The deterministic portion is `crew-state.py run` (single writer). It does not spawn agents, call models, promise background execution or replace existing workflow stage logic.

- `run start` requires active Host-signed Grant, not inferred/parked state, matching project/branch and no previous execution.
- `run next` reconciles previous inflight step against `steps.{step}.status`, retains exactly one in-flight dispatch, and outputs a deterministic next action.
- `run heartbeat` records best-effort liveness but **does not renew `expires_at`**. A stale heartbeat is not proof a Host worker has stopped.
- `run pause` records reason and blocks further dispatch.
- `run resume` rechecks signed Grant, 4h expiry and approved plan. A pending inflight operation requires `--reconcile --reason` and explicit proof old worker stopped. `--takeover` only after pause and explicit reason.
- `run status` reads the current checkpoint; it is a status report, not proof of running processes.
- `run next` consumes the grant when `build=done`, `work_unit` clear and approved Gate / latest snapshot checks pass.
- If signature, time, branch or plan contract differs from approved packet, `run` fails closed, marking active execution paused.

## Valid Host Dispatch

```text
Host-approved, signed packet
    ↓ plan-start signed fast-path → crew-state grant issue
    ↓ run start
    ↓ run next: spec   → review-once-apply.py --step spec
    ↓ run next: db     → review-once-apply.py --step db
    ↓ run next: arch   → review-once-apply.py --step arch
    ↓ run next: build  → /plan-build --with-test --review-once
    ↓ run next: completed_build, grant consumed
```

Each `review-once-apply.py` invocation:
- Requires an active Runner checkpoint and matching Host-signed proposal.
- Inserts approved lines at the existing plan.md anchors without changing their six sections or overwriting unrelated content.
- Validates exact Goal/AC/Spec/DB/Architecture content, full plan <=100 lines, SQL draft identity and live Grant; only `crew-state.py` writes `state.json`.
- Calls normal state transitions and a signed `grant approve-requirement` / `approve-architecture` (no fake `--by human`).

`review-once-build.py` checks the real checked-out Git branch and changed product paths against packet's scoped allowlist (pre/post Build). Production write scopes require **Host-enforced access limits**; Git scanning is defense in depth, not prevention.

## Failure behavior

No trusted Host approval broker → no Review Once execution. No long-running dispatch capability → report not supported rather than claim background work. No reliable worker cancellation → do not auto-take over in-flight work. Exception/failure → pause, preserve state, seek explicit reconciliation. The Runner is not a security principal: `owner` is cooperative metadata only, not an authentication secret.

## Tests

Executable tests in `scripts/lint-review-once-runner.py` cover successful Spec→DB→Arch→Build path, duplicate dispatch suppression, incomplete Build, pause/resume, revoke, expired Grant and UAT untouched.
