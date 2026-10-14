# Review Once Host Bridge — protected operator adapter (PR-D)

## What is real in this implementation?

`review-once-host.py` is a **synchronous** real process driver: it uses `crew-state.py run` to dispatch deterministic phases, applies the already signed and reviewed Spec/DB/Arch packet, and launches a real Host-owned Build worker subprocess. It polls the original 4h Grant, checks revocation/paused state, attempts process-group cancellation and verifies both the Git scope and `steps.build=done` before consuming the Grant. Nothing runs after the terminal/session or process has ended.

It does **not** sign Human approval events, create approved grants, or provide its own filesystem sandbox. Those remain Host responsibilities.

這是 `/plan-run` **模式 3（trusted-host）** 專用的執行器（`skills/plan-run/phases/trusted-host.md`）：

- 只接受 `autonomy.proof=signed` 的 grant；`autonomy.proof=dialogue`（同 session 模式）一律 **BLOCK**——dialogue grant 只能由 `/plan-run` 主對話迴圈使用，Bridge 不得把它當成可在背景執行的授權。
- 時限：signed grant 從 **Host 簽發事件的 `issued_at` 起算**（≤4h），不是從 Bridge `start` 起算；簽發後拖延啟動，可用時間會變短。
- 入口確認：`/plan-run` 選模式 3 時，會用 `ask_user` 要求使用者提供 adapter 絕對路徑並確認四項 `host_guarantees` 已由 Host 實際實施；這是取代「讓 Agent 自填布林」的人工確認，仍不是密碼學證明。

## Mandatory trust boundary

The Host must separately implement:

1. **Human approval**: display the *whole* packet and obtain a real Human confirmation. Signing private key must never be accessible to the Agent. `CREW_REVIEW_ONCE_TRUSTED_PUBLIC_KEY` must point to a Host-pinned key outside the workspace; Agent must not control it.
2. **Per-worker write isolation**: an OS/Host-enforced sandbox permitting only packet `scope.allowed_paths`. A text instruction such as "do not edit outside src" and a post-hoc Git diff scan are NOT enforcement. An unmodified `claude -p` or `codex exec --sandbox workspace-write` is not sufficient to prove per-file isolation.
3. **No privilege escalation or silent approvals**: subprocess must deny unsafe git operations, deployment and permission changes; Host must implement the policy, not the LLM.
4. **Cancellation**: Host must allow terminating a running worker; after a Host crash, absence of a process must be confirmed before manual `resume --reconcile`.

If these guarantees are unavailable, use Interactive or `/plan-run` 的同 session 模式（dialogue grant；不是無人值守，session 結束即 paused）. This plugin cannot produce a 4-hour autonomous workflow safely just by enabling a flag.

## Operator configuration

Create the following file **outside the repository**, owned by the Host operator, file mode `0600`, with non-group/world-writable parent directories. Example: `$HOME/.crew/review-once-adapter.json`.

```json
{
  "schema_version": 1,
  "adapter": "trusted-host",
  "worker_argv": [
    "/usr/local/bin/crew-protected-worker",
    "--project", "{project}",
    "--slug", "{slug}",
    "--skill", "{instruction}"
  ],
  "host_guarantees": {
    "protected_human_approval": true,
    "enforced_write_scope": true,
    "worker_cancellation": true,
    "no_unattended_escalation": true
  }
}
```

The executable is an **operator-implemented Host wrapper** that invokes the existing Feature Build skill while enforcing the approved scope and producing real compile/test evidence. This PR does not ship such a production Claude Code / Codex wrapper. Never use `/bin/sh -c` and never expose a permissive generic exec endpoint to the LLM.

The `host_guarantees` fields are assertions by the *trusted operator*, **not cryptographic attestation**. A process that can modify this file, replace the executable, override the verification public key or modify the repo's runtime code could bypass the intended guard. Keep the Host/Agent identities separated for production.

`worker_argv` is passed to `subprocess.Popen` as a literal argument array, **never through a shell**. All three placeholders must be separate entire arguments. A standalone `claude` or `codex` command without the necessary isolation is *not* a supported secure production adapter.

## Execution

After a real Host-signed Human Approval event is stored and bound to a Feature task, with a clean and correct Git branch:

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
# 1) Probe the adapter contract; this is NOT proof of a real sandbox
python3 "${CREW_PLUGIN_ROOT}/scripts/review-once-host.py" \
  --project . --slug {slug} --adapter "$HOME/.crew/review-once-adapter.json" \
  --action probe

# 2) Start one synchronous execution loop (clock already started at the Host-signed event's issued_at)
#    worker stdout/stderr 寫到 .spec/{slug}/.cache/（review-once-build.py 的 scope 檢查已排除 .cache）
python3 "${CREW_PLUGIN_ROOT}/scripts/review-once-host.py" \
  --project . --slug {slug} --owner {host-runner-id} \
  --adapter "$HOME/.crew/review-once-adapter.json" --action start \
  --worker-log .spec/{slug}/.cache/review-once-worker-{run_id}.log

# 3) Status and operator pause/revoke can be invoked separately
python3 "${CREW_PLUGIN_ROOT}/scripts/review-once-host.py" \
  --project . --slug {slug} --action status
python3 "${CREW_PLUGIN_ROOT}/scripts/review-once-host.py" \
  --project . --slug {slug} --owner {host-runner-id} --action pause
python3 "${CREW_PLUGIN_ROOT}/scripts/review-once-host.py" \
  --project . --slug {slug} --action revoke

# 4) Resume only if existing worker is confirmed stopped
python3 "${CREW_PLUGIN_ROOT}/scripts/review-once-host.py" \
  --project . --slug {slug} --owner {host-runner-id} \
  --adapter "$HOME/.crew/review-once-adapter.json" --action resume \
  --reconcile --reason "operator verified previous Host worker stopped"
```

A `status` query only reads the persisted Runner checkpoint (including `grant_proof` and `target_step`) and should not be interpreted as proof that the subprocess is still running. If the Host session died while the Runner is still `running`, first run `crew-state.py run --action reclaim --owner {new} --reason ... --slug {slug} --project .`（running→paused、`SESSION_LOST`）, then reconcile as in step 4. The adapter polls every two seconds by default and records cooperative heartbeat evidence every 30 seconds.

`--action continue` resumes only a *running* Runner with no unresolved in-flight task; for crashed workers, use explicit paused reconciliation. After Build succeeds, `review-once-build.py` still validates all approved source changes and the Host must have run the tests required by the selected `with_test` or `bdd` policy.

## Verified acceptance

`python3 scripts/lint-review-once-host.py`（repo 根 `scripts/`，不隨 plugin 安裝） runs a real RSA-signed proposal against an isolated Git fixture and a real subprocess Host simulator. It verifies complete workflow, no false completion when the worker exits without Build evidence, unapproved path rejection, nonzero exit, grant revoke and fail-closed unsafe operator configuration. It does **not** test actual paid Claude/Codex APIs or provide a sandbox implementation.

The existing CI includes separate `lint-review-once.py`, `lint-review-once-grants.py` and `lint-review-once-runner.py`; this adds an independent `review-once-host` job.
