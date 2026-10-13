---
name: plan-run
description: 以受保護 Human Review Once 授權持續推進 CREW Feature 到 Build Done，含 4 小時有效期、Gate 綁定、暫停與續跑。當使用者提到 /plan-run、「一次審查後自動實作」、「Review Once 長時間執行」時觸發此 Skill。
argument-hint: "[--mode review-once] [--until build] [--max-duration 4h] [status|pause|resume|revoke]"
---

# plan-run — Review Once Host Orchestrator

> 此 Skill 由 Host **同步**驅動既有 Skills，不會自行建立背景 Daemon。若 Host 不支援受保護 Approval Event／delegated write scope／長時間 Session，**BLOCK 或退回 Interactive**，不得宣稱真正無人值守。

## 使用方式

```text
/plan-run --mode review-once --until build --max-duration 4h
/plan-run status
/plan-run pause
/plan-run resume
/plan-run revoke
```

v1 僅 `feature`、`review_once`、`14400s`、Build Done；不可擴及 Bug、UAT、部署或 Git push/merge。參照 `../../references/review-once-runner.md`、`../../references/review-once-grants.md`、`../../references/host-capabilities.md`。

## 第一階段：準備且只審查一次

1. 以 `delegate_readonly` 探索 Spec、DB、Architecture、測試策略與 allowed paths，不修改正式 `plan.md`、`state.json` 或程式碼。
2. 建立 `.spec/.drafts/{proposal_id}/draft.json`（gitignored），使用 `review-once-packet.py prepare --draft ... --output .../packet.json` 取得 SHA-256 指紋。
3. 向 Human 顯示完整 Goal、AC/Sxx、DB SQL、Architecture、修改檔案路徑、測試策略、明確禁止動作與 **4 小時從核准開始計時**；只有 Host 的可信任互動才能取得核准與簽章。若使用者修改需求，重新產生 packet，舊 SHA 無效。
4. Host 必須保護 private key／信任公鑰路徑，將 `packet.json`、`approval.json` 與 raw `approval.sig` 傳給既有 `/plan-start --from-review-once` 建立 skeleton/task/branch。**未取得 signed proof 時不得假裝核准或建正式任務**。
5. 初始化後由 `crew-state.py grant --action issue` 綁定相同 packet，才可呼叫 `crew-state.py run --action start --owner {runner-owner}`。

## 第二階段：持續執行直到 Build Done

下列所有呼叫都必須帶 `--slug {slug} --project {repo-root}`，runner owner 是同一次 Host 工作階段產生的安全字串：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" run \
  --action start --owner {runner-owner} --slug {slug} --project .
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" run \
  --action next --owner {runner-owner} --slug {slug} --project .
```

`run next` 輸出 JSON 的 `inflight.step`、`inflight.command` 是 **Host 派工契約**，不是已執行證據：

| `inflight.step` | Host 必須實際執行的工作 |
|---|---|
| `spec` | `review-once-apply.py --step spec`，寫入核准 Goal/AC/Spec 並透過既有 Gate 確認 |
| `db` | `review-once-apply.py --step db`，只產核准 SQL，不在 DB 執行 |
| `arch` | `review-once-apply.py --step arch`，套用已核准 Architecture 並合法核准 Gate |
| `build` | 呼叫現有 `/plan-build --with-test --review-once` 或已安裝的 `/plan-build --bdd --review-once`，委派具 allowed scope 的實作者 |

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/review-once-apply.py" \
  --project . --slug {slug} --step spec
```

- 每次派工前檢查授權簽章、當前分支、Spec/Arch 內容是否仍匹配與 4 小時期限，結果 invalid → 停止派工。
- Host 在長時間 delegate 期間每 30 秒若可行呼叫 `run --action heartbeat`，並持續評估授權與是否收到 Human Pause/Revoke；無法中止的 Host worker 必須明確說明限制。
- 每個階段完成後由原工作單元**實際更新** `crew-state.py` 的 `steps/gates/work_unit`，Host 再呼叫 `run next` 對帳並派下一步。
- `run next` 發現未對帳的 `inflight` 只會回報 BLOCKED，不會重複派工。
- 只有 `build=done`、`work_unit` 清空、Gate 正確及授權仍有效，才回 `status=completed_build` 並將 Grant `consumed`。
- **遇到 TEST_FAILED、NEED_HUMAN、範圍衝突或 Host 不支援時必須停止**，不得偽造 `build=done`。不轉進 Security/Verify/Review/close。

## 第三階段：Pause / Resume

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" run \
  --action pause --owner {runner-owner} --reason USER_PAUSED --slug {slug}
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" run \
  --action resume --owner {runner-owner} --slug {slug}
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" run \
  --action status --slug {slug}
```

- 若有未完成 `inflight`，先確保舊 worker 已停止，取得 Host/檔案／測試證據後，才能用 `resume --reconcile --reason "confirmed worker stopped"` 明確繼續相同單元；Build 中斷須遵循既有 `/plan-build --resume`，不可自動生成新的平行 worker。
- `resume --takeover --reason ...` 僅在先前 Runner paused 且 Host 明確確認原 worker 停止時允許 owner 轉移，**不是突破四小時期限**。
- 撤銷需走 `crew-state.py grant --action revoke`；撤銷後不得重放同一 Grant；原有有效 Human UAT 仍獨立。
- 根據 Host 能力在工作階段中持續執行；本 Skill 不建立排程、常駐程序或虛假的背景執行。

## 必守邊界

- Review Once 的 user approval 只批准當時完整 packet，不允許在 Agent 將 AC／架構改變後繼續使用舊授權。
- 永遠先保護授權與 allowed scope，再啟動正式 `delegate_write`。不可把使用者之前說過「可以」當作本輪 Host-signed Human event。
- 未核准的產品修改、正式 SQL 執行、Git push/merge、機密與權限操作全部 BLOCK。
