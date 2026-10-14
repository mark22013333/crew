# plan-run 模式 3：trusted-host 簽章

> 由 `../SKILL.md` 步驟 1 選 3（或 `--mode trusted-host`）並通過 adapter 確認題後進入。
> 本模式需要 Host 在**工作區外**提供受保護的 Human approval 簽章端與 worker adapter；CREW 不附簽章端。一般 `claude -p`／`codex exec --sandbox workspace-write` 不等同檔案級 Scope Sandbox，**不符合**本模式，請改用模式 2（同 session）。
> Host Bridge 對 `autonomy.proof=dialogue` 的 grant 一律 BLOCK；dialogue grant 只能在模式 2 的主對話迴圈使用。

## T1. 準備且只審查一次

1. 以 `delegate_readonly` 探索 Spec、DB、Architecture、測試策略與 allowed paths，不修改正式 `plan.md`、`state.json` 或程式碼；第二層三題（`--until`、`--max-duration`、`--test`）與模式 2 相同，照 SKILL.md 詢問。
2. 建 `.spec/.drafts/{proposal_id}/draft.json`（gitignored），產生 packet：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
python3 "${CREW_PLUGIN_ROOT}/scripts/review-once-packet.py" prepare \
  --draft .spec/.drafts/{proposal_id}/draft.json \
  --output .spec/.drafts/{proposal_id}/packet.json
```

3. 由 Host 的可信任互動展示完整 packet 並取得核准與簽章（`approval.json`＋raw `approval.sig`）。使用者要求修改 → 重產 packet，舊 SHA 無效。**未取得 signed proof 時不得假裝核准或建正式任務。**
4. 時限：signed 路徑沿用簽章事件的 `issued_at`／`expires_at`，**從 Host 簽發起算**（≤4h），不從 packet 產生起算；詳見 `../../../references/review-once-host.md`。

## T2. 建任務與綁定 signed grant

```text
/plan-start --from-review-once --packet <packet.json> --event <approval.json> --signature <approval.sig>
```

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" grant \
  --slug {slug} --action issue \
  --packet <packet.json> --approval-event <approval.json> --signature <approval.sig> --project .
```

省略 `--proof` 即為 signed 原路徑（`autonomy.proof=signed`）。綁定失敗 → 停在未授權狀態，不得執行任何 Spec 或 Build。

## T3. Host Bridge 同步執行

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
# 探測 adapter 契約（不是 sandbox 證明）
python3 "${CREW_PLUGIN_ROOT}/scripts/review-once-host.py" \
  --project . --slug {slug} --adapter {adapter 絕對路徑} --action probe
# 啟動同步迴圈；worker 輸出寫到 .cache 供事後檢視
python3 "${CREW_PLUGIN_ROOT}/scripts/review-once-host.py" \
  --project . --slug {slug} --owner {host-runner-id} \
  --adapter {adapter 絕對路徑} --action start \
  --worker-log .spec/{slug}/.cache/review-once-worker-{run_id}.log
```

- Bridge 依序呼叫 `crew-state.py run`、`review-once-apply.py` 與 Host worker；它不簽章、不核准、不建立 grant。
- Bridge 在同一個 Host Session 啟動子程序，不建立 Daemon，Session 結束後不會背景執行。
- Adapter 設定檔與 worker 執行檔必須由 Host 控制、位於工作區外；`host_guarantees` 四項必須已由 Host **實際實施**，Agent 不得自行寫入 `true`（入口確認題即為此用）。
- 每個 Build 工作單元前後跑 Git-scope 檢查；worker exit=0 但 `build` 未完成，Bridge 仍拒絕標記完成。
- Bridge 每 30 秒記錄合作式 heartbeat；撤銷、到期、暫停及 worker 失敗會終止子程序並保留 checkpoint。
- 停止時依 SKILL.md 的停止點 A～D 詢問，不提供「跳過」。

## T4. 狀態、暫停、撤銷、續跑

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
python3 "${CREW_PLUGIN_ROOT}/scripts/review-once-host.py" \
  --project . --slug {slug} --action status
python3 "${CREW_PLUGIN_ROOT}/scripts/review-once-host.py" \
  --project . --slug {slug} --owner {host-runner-id} --action pause
python3 "${CREW_PLUGIN_ROOT}/scripts/review-once-host.py" \
  --project . --slug {slug} --action revoke
python3 "${CREW_PLUGIN_ROOT}/scripts/review-once-host.py" \
  --project . --slug {slug} --owner {host-runner-id} \
  --adapter {adapter 絕對路徑} --action resume \
  --reconcile --reason "operator verified previous Host worker stopped"
```

- `status` 只讀 checkpoint（含 `grant_proof`、`target_step`），不是子程序仍在跑的證據。
- `resume --reconcile` 只有確認舊 worker 已停止、結果已對帳才可使用；原 session 已死而 Runner 仍為 `running` 時，先依 SKILL.md resume 分流執行 `crew-state.py run --action reclaim`。

Adapter Schema、Host 信任邊界與完整指令見 `../../../references/review-once-host.md`。
