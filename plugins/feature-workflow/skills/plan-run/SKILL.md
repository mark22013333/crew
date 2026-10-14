---
name: plan-run
description: 先問使用者要用哪種方式推進 CREW Feature —— 互動逐站、同 session 一次審查連跑（核准一次 Review Packet 後在本對話連跑到目標站）或 trusted-host 簽章，含時限、Gate 綁定、停止點詢問、暫停／續跑／接管。當使用者提到 /plan-run、「一次審查後自動實作」、「Review Once 長時間執行」、「連跑到 build」時觸發此 Skill。
argument-hint: "[--mode interactive|session|trusted-host] [--until build|arch] [--max-duration 4h|2h|1h] [--test with_test|bdd] [--scenarios none|risky|all] [status|pause|resume|revoke|reclaim]"
---

# plan-run — 先問再做的 Feature 推進入口

> **誠實定位（三處文件一致：本檔、`../../references/review-once-grants.md` 的 dialogue 節、`../../references/review-once.md`）**
> - dialogue grant 的 packet hash 只保證「**套用的＝審過的**」；信任等級等同 Interactive 的 `gate --by human`，**不是不可偽造的核准**。
> - 同 session 模式**不是無人值守**：迴圈在目前對話裡同步執行，session 結束即 paused，`/plan-run resume` 續跑。
> - 本 Skill 不建立背景 Daemon、排程或常駐程序。

## 使用方式

```text
/plan-run                                   # 無旗標：先問要用哪種方式
/plan-run --mode interactive                # 互動逐站
/plan-run --mode session --until build --max-duration 4h --test with_test
/plan-run --mode review-once ...            # review-once 是 session 的別名
/plan-run --mode trusted-host               # 需工作區外簽章 Host 與受保護 adapter
/plan-run status | pause | resume | revoke | reclaim
```

v1 僅 `feature`；不擴及 Bug、UAT、部署、Git commit／push／merge。參照 `../../references/review-once-runner.md`、`../../references/review-once-grants.md`、`../../references/host-capabilities.md`。

## 詢問紀律（本 Skill 所有 `ask_user` 共用）

- 詢問只在 Skill 層的主對話進行；委派角色（test-engineer、backend 等）不得負責提問，worker 的 NEED_HUMAN 一律由 Leader 帶回主對話問。
- **只有本輪明確選擇才算**：沉默、Enter、「繼續」、「ok」、「好」都不算選擇，必須重問同一題；不得沿用先前聊天中說過的「可以」。
- 旗標是跳過詢問的捷徑，不是預設；旗標齊全的題目不再問，缺的題目照問。
- Host 沒有結構化選單時，用**一則對話**列出本輪全部題目與編號選項，請使用者逐題回覆編號。
- **headless**（無法提問：例如權限提示關閉、排程、`claude -p` 非互動）且旗標不齊 → **BLOCK**，訊息列出缺少的旗標，不得代選。
- 停止點的詢問**不提供「跳過」**選項。

---

## 步驟 0：前置與子指令分流

先判斷這個 Feature 是否已有狀態檔：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
if [ -f ".spec/{slug}/state.json" ]; then
  python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" run \
    --action status --slug {slug} --project .
else
  echo "NEW_TASK: .spec/{slug}/state.json 不存在"
fi
```

- `.spec/{slug}/state.json` 不存在（或 `run status` 回「找不到狀態檔」）→ 視為新任務，直接進步驟 1 入口詢問；模式 2、3 會在核准後由 `/plan-start --from-review-once` 建立狀態檔。
- 參數是 `status`／`pause`／`resume`／`revoke`／`reclaim` → 跳到下方「子指令」，不問模式；這些子指令**要求狀態檔已存在**，不存在就回報「此 Feature 尚無 Runner 狀態」並結束。
- 參數有 `--mode` → 跳過步驟 1 的模式題；`review-once` 視為 `session`。
- 目前 Feature 已有 `running`／`paused` 的 Runner → 不得重開新 grant，改提示 `/plan-run status` 或 `/plan-run resume`。

## 步驟 1：入口詢問 —— 要用哪種方式推進

無 `--mode` 時：

```text
ask_user(
  question: "要用哪種方式推進這個 Feature？",
  options: [
    "1. 互動逐站：每站停下來問，本 skill 只回 /plan-next 建議的下一步",
    "2. 同 session 一次審查連跑（建議）：核准一次 Review Packet 後在本對話連跑到目標站；session 結束即 paused，/plan-run resume 續跑；不是無人值守",
    "3. trusted-host 簽章：需工作區外的簽章 Host 與受保護 worker adapter；一般 claude -p／codex exec 不符合"
  ],
  why_required: "決定是否逐站詢問與授權的信任等級，Agent 不可代選；沉默／Enter／「繼續」不算選擇。"
)
```

- headless 且無 `--mode` → BLOCK：「需 `--mode interactive|session|trusted-host`」。

### 模式 1：互動逐站

本 Skill 只讀狀態並回報下一步，不派工、不建立 grant：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" next \
  --slug {slug} --project .
```

把結果轉成人話（同 `/plan-next`），由使用者自己執行該指令；每站的 Approval Gate 照既有 `/plan` 流程由 Human 核准。

### 模式 2：同 session 一次審查連跑 —— 第二層三題

旗標齊全就跳過；缺哪題問哪題，Host 無多題選單時用一則對話列出三題：

```text
ask_user(
  question: "同 session 連跑的三個設定（請逐題回覆編號）",
  options: [
    "跑到哪一站（--until）：1. build（預設：Spec→DB→Arch→Build）  2. arch（只套用 Spec／DB／Arch，不進 build）",
    "時限（--max-duration）：1. 4h（預設）  2. 2h  3. 1h —— 從 grant 簽發起算，不從 packet 產生起算",
    "測試策略（--test）：1. with_test（預設：產品碼後補測試）  2. bdd（Test-First；packet 必須含 Sxx，探索時依 --scenarios 或 risky 深度產生）"
  ],
  why_required: "目標站、時限與測試策略會寫進 packet 與 grant，核准後不能改；「預設」只是建議標示，仍需本輪明確選擇。"
)
```

- `git commit` **不問、固定不允許**（packet 白名單沒有 git_commit）。
- headless 且任一題缺旗標 → BLOCK：「需 `--until build|arch`、`--max-duration 4h|2h|1h`、`--test with_test|bdd`」。

接著產生 Review Packet，展示整份內容後問核准題：

```text
ask_user(
  question: "核准 packet {packet_sha256 前 12 碼}？（核准後 {N} 內在本對話連跑到 {until}）",
  options: [
    "1. 核准並連跑",
    "2. 修改 → 說明要改哪裡，重產 packet，舊 sha 作廢",
    "3. 取消（零 side effect：不建 .spec、branch、grant）"
  ],
  why_required: "Review Once 只批准這一份完整 packet；hash 只保證套用的＝審過的，等同一次 Human gate 核准。"
)
```

packet 準備、`/plan-start --from-review-once --proof dialogue` 鏈、grant 簽發、主對話迴圈、heartbeat 與 `--until arch` 細節 → [phases/session.md](phases/session.md)。

### 模式 3：trusted-host 簽章 —— 多問一題

```text
ask_user(
  question: "trusted-host 需要 Host 管理的 adapter：請提供 adapter 設定檔絕對路徑，並確認四項 host_guarantees 已由 Host 實際實施",
  options: [
    "1. 已確認：adapter 位於工作區外，protected_human_approval／enforced_write_scope／worker_cancellation／no_unattended_escalation 四項皆由 Host 實施（附路徑）",
    "2. 不確定或只有一般 claude -p／codex exec → 改用模式 2（同 session）",
    "3. 取消"
  ],
  why_required: "host_guarantees 是 operator 宣告、不是密碼學證明；Agent 不得自行把它寫成 true。"
)
```

- headless 且無 `--mode trusted-host` 與 adapter 路徑 → BLOCK。
- 簽章 packet、`approval.sig`、Host Bridge 與 `--worker-log` 細節 → [phases/trusted-host.md](phases/trusted-host.md)。Bridge 對 `autonomy.proof=dialogue` 的 grant 一律 BLOCK。

---

## 停止點（模式 2、3 共用；全部 ask_user，**不提供「跳過」**）

遇到下列情況立即停止派工，不得偽造 `build=done`，不轉進 Security／Verify／Review／close：

**A. TEST_FAILED／E0-E3／E8**

```text
ask_user(
  question: "Build 在 {錯誤碼} 停止：{摘要}。要怎麼處理？",
  options: [
    "1. 續修：/plan-build --resume --review-once（inflight 保留，免 reconcile）",
    "2. 暫停：crew-state.py run --action pause --owner {runner-owner} --reason {原因} --slug {slug} --project .",
    "3. 撤銷授權轉 Interactive：crew-state.py grant --action revoke --slug {slug} --project .，之後逐站核准"
  ],
  why_required: "失敗後的方向會改變授權與工作單元狀態，Agent 不可代選。"
)
```

**B. NEED_HUMAN**（worker 需要人回答的問題，由 Leader 帶回主對話）

```text
ask_user(
  question: "worker 需要你決定：{問題}",
  options: [
    "1. 回答後重試（答案只用於本工作單元，不得超出 packet 範圍）",
    "2. 暫停",
    "3. 撤銷並回 /plan spec 修改規格"
  ],
  why_required: "packet 未涵蓋的決定只能由 Human 做。"
)
```

**C. 範圍衝突**（`review-once-build.py` 偵測到核准路徑外的變更）

```text
ask_user(
  question: "偵測到核准範圍外的變更：{路徑清單}。要怎麼處理？",
  options: [
    "1. 人工還原範圍外變更後重試",
    "2. 暫停",
    "3. 撤銷授權但保留目前變更（轉 Interactive 人工檢視）"
  ],
  why_required: "不得擴大已核准的 scope；任何擴大都要重審新 packet。"
)
```

**D. 到期／GRANT_OR_SCOPE_INVALID**（Runner 已自動 paused）

```text
ask_user(
  question: "授權已失效（{stop_reason}），Runner 已暫停。下一步？",
  options: [
    "1. revoke 後重審新 packet（重新走模式 2 的三題與核准題）",
    "2. 轉 Interactive：crew-state.py grant --action revoke --slug {slug} --project . 後逐站 /plan-next",
    "3. 停止，保留 checkpoint"
  ],
  why_required: "授權不能延長或沿用，只能重審或改人工逐站。"
)
```

---

## 子指令

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" run \
  --action status --slug {slug} --project .
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" run \
  --action pause --owner {runner-owner} --reason USER_PAUSED --slug {slug} --project .
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" grant \
  --action revoke --slug {slug} --project .
```

- `status`：只讀 checkpoint，回報 `status`（`running`／`paused`／`completed_build`／`completed_plan`）、`stop_reason`（含 `PLAN_DONE`、`SESSION_LOST`、`GRANT_OR_SCOPE_INVALID`）、`autonomy.proof`、`autonomy.target_step`；不是「worker 仍在跑」的證據。
- `pause`：需同一個 owner；session 已死時改用 `reclaim`。
- `revoke`：撤銷後不得重放同一 grant；既有有效的 Human Gate 與 UAT 不受影響。

### resume 分流（先跑 `crew-state.py run --action status --slug {slug} --project .`）

| 狀態 | 處理 |
|------|------|
| `paused` 且有 `inflight` | 問下方「原 worker 已停止？」 |
| `paused` 且無 `inflight`，`run status` 的 owner **等於**本 session owner | 直接 `crew-state.py run --action resume --owner {本 session owner} --slug {slug} --project .`，再回 `phases/session.md` 的迴圈 |
| `paused` 且無 `inflight`，`run status` 的 owner **不等於**本 session owner（換了 session 的常態） | `crew-state.py run --action resume --owner {新 owner} --takeover --reason "previous session ended" --slug {slug} --project .`，再回迴圈；沒帶 `--takeover` 會被拒（擁有權不得未經明示移轉） |
| `running` 但原 session 已死（無法用原 owner pause） | 先 `reclaim`（running→paused、stop_reason=`SESSION_LOST`、記錄舊 owner），再依上三列處理 |
| `completed_build`／`completed_plan` 或 grant `consumed` | 回報已完成，不再派工 |

判斷依據：比對 `run status` 輸出的 owner 與本 session 自己產生的 owner 字串（例如 `dialogue-{YYYYMMDDHHMMSS}`）；新 session 一律產生新 owner，所以前一個 session 留下的 paused Runner 都走「不等於」那列。

**reclaim 注意**：`reclaim` 只會把 `running` 轉成 `paused`，不會推進任何一站，也**不檢查心跳是否過期**。只在確認原 session 已結束時使用；原 session 其實還活著時，它等同從另一個終端強制暫停對方。

```text
ask_user(
  question: "上一個 worker（owner={舊 owner}，inflight={step}）已確認停止了嗎？",
  options: [
    "1. 已確認停止 → resume --takeover --reconcile；build 則接 /plan-build --resume --review-once",
    "2. 不確定 → 停在這裡，先去確認（不接管）",
    "3. 撤銷授權（crew-state.py grant --action revoke --slug {slug} --project .）"
  ],
  why_required: "stale heartbeat 不能證明舊 worker 已停，接管與否只能由 Human 確認，避免兩個 worker 同時寫。"
)
```

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" run \
  --action reclaim --owner {新 owner} --reason "previous session ended" --slug {slug} --project .
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" run \
  --action resume --owner {新 owner} --takeover --reconcile \
  --reason "human confirmed previous worker stopped" --slug {slug} --project .
```

- `resume` 會重驗 grant（dialogue 重算 packet hash；signed 重驗簽章）、時限與已核准 plan；**不是突破時限**，到期即走停止點 D。
- 不得自動生成新的平行 worker。

## 必守邊界

- Review Once 的核准只涵蓋當時那一份完整 packet；AC／架構／scope 有任何改變就要重產 packet 重審，不得沿用舊 grant。
- 核准一律經 `grant --action approve-requirement|approve-architecture`（`review-once-apply.py` 內部呼叫），記為 `by=delegated-review-once`，不得偽裝成 `by=human`。
- 未核准的產品修改、正式 SQL 執行、Git commit／push／merge、機密與權限操作全部 BLOCK；Human UAT 永不自動通過。
