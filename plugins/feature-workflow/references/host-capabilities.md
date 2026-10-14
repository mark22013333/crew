# CREW Host Capability Contract

> CREW workflow 的語意契約。Skill 描述「要完成什麼能力」，Host adapter 決定「用哪個產品工具完成」。
> 核心流程不得把 `Agent tool`、`Agent Teams`、`TeamDelete` 等產品工具名稱當成流程必要條件。

---

## 原則

1. **Capability 是契約，工具名稱只是 adapter 實作。**
2. **不能精準支援時要安全降級，不得假裝能力存在。**
3. **唯讀／可寫邊界永遠優先於平行度與模型最佳化。**
4. **平行只是最佳化，不得改變 workflow 的正確性。**
5. **模型目標由 `model-policy.md` 決定；Host 能否精準套用由 adapter 回報。**
6. **可用程式／Git／測試驗證的工作不應為了委派而委派。**

---

## Capability 一覽

| Capability | 用途 | 最低保證 |
|---|---|---|
| `project_instructions` | 取得專案架構／規範上下文 | 至少讀到一份專案指令；沒有就明確阻擋 |
| `plugin_root` | 解析目前 plugin 根目錄 | 回傳可讀的 plugin root |
| `delegate_readonly` | 隔離做探索、分析、review | 不修改正式程式碼 |
| `delegate_write` | 隔離做已核准的正式修改 | 只能修改指定 scope |
| `parallel_delegate` | 同時執行互不依賴任務 | 不可因無平行能力而中止；可退化為序列 |
| `tool_probe` | 判斷 MCP／外部工具是否真的可用 | 以實際可呼叫能力判定，不靠某家 CLI 清單 |
| `ask_user` | 取得必要的人類決策 | 不綁特定 UI/tool 名稱 |

---

## 1. project_instructions

### Workflow 語意

需要專案上下文時，寫：

```text
project_instructions(required=true)
```

讀取 Git root 到目前工作目錄範圍內可用的專案指令檔：

- `AGENTS.md`
- `CLAUDE.md`

兩者都存在時都可讀；若有實質衝突，**不得自行挑一份假裝另一份不存在**，應把衝突列為歧義點。
同目錄下的 host-native 自動注入規則可繼續生效，但 CREW Skill 不應硬要求特定檔名。

### Claude Code adapter

- `CLAUDE.md` 是 host-native 專案指令。
- `AGENTS.md` 若存在，CREW 可額外讀取。
- 初始化提示可使用 Claude Code 的 `/init`。

### Codex adapter

- `AGENTS.md` 是 host-native 專案指令。
- `CLAUDE.md` 若存在，CREW 可額外讀取；不要要求使用者為了 Codex 改名。
- 若兩者都不存在，提示建立 `AGENTS.md` 或使用 Codex 專案初始化流程。

---

## 2. plugin_root

Shell 內一律用下列順序解析：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
```

空值 → 明確回報「無法解析 plugin root」，不得猜路徑。

- Codex plugin hook/runtime 提供 `PLUGIN_ROOT`，並相容 `CLAUDE_PLUGIN_ROOT`。
- Claude Code 使用 `CLAUDE_PLUGIN_ROOT`。
- 新增 script 時優先使用 `CREW_PLUGIN_ROOT` 語意；既有 `CLAUDE_PLUGIN_ROOT` 可逐步遷移。

---

## 3. delegate_readonly

### 呼叫契約

新流程優先傳 **routing intent**，由 `crew-model-route.py` 決定 Profile 與 Host mapping：

```yaml
capability: delegate_readonly
role: <角色>
routing:
  task: repository_search
  profile: FAST
  risk: low
  complexity: low
scope:
  write_product_code: false
input: <必要上下文>
output_contract: <結構化交付格式>
```

`profile` 是該 call site 預期的 provider-neutral 基準；執行前用 router 驗證。尚未遷移的 Skill 可暫時保留直接 `model: sonnet|opus|haiku`，但新修改不要再新增 provider-specific routing。

### Claude Code adapter

- 使用獨立 subagent / Agent tool。
- 有 `routing` 時先執行 `crew-model-route.py route --host claude`，再把 `host_mapping.model` / `effort` 套到實際 worker。
- 若是尚未遷移的直接 `model`，仍必須用結構化 model 參數實際傳入。
- 不得只在 prompt 文字裡寫模型名稱。

### Codex adapter

- 若目前 harness 提供 multi-agent/subagent 能力，建立獨立唯讀 worker。
- 有 `routing` 時先執行 `crew-model-route.py route --host codex`，使用其 `reasoning_effort`；不要把 Claude model 名稱帶進 Codex。
- 若目前 surface 沒有可用的 subagent 能力，**由主 Agent inline 執行同一工作**，但仍遵守唯讀邊界與 output contract。
- 若 surface 無法精準套用 router mapping，不得宣稱已切換；回報 `routing_degraded=true`，保留語意正確性優先。

---

## 4. delegate_write

### 呼叫契約

```yaml
capability: delegate_write
role: <角色>
model: opus
scope:
  allowed_paths:
    - ...
  write_product_code: true
input: <已核准 spec + handoff>
verification:
  - <build/test command>
```

### 共通硬規則

- 只有 `model-policy.md` 明列可改正式程式碼的流程能使用。
- Requirements / Acceptance Criteria 未核准時不得執行。
- 不得順手修改 scope 外檔案。
- 完成後必須回傳 changed files、tests、assumptions、unresolved issues。

### Claude Code adapter

使用獨立可寫 subagent；能隔離 worktree 時優先隔離。

### Codex adapter

有可用 subagent/multi-agent 時可委派；沒有時由主 Agent 在同一 session 執行。
**沒有獨立 worker 不代表可以跳過 scope 或驗證。**

---

## 5. parallel_delegate

### 呼叫契約

```yaml
capability: parallel_delegate
tasks:
  - role: reviewer-logic
    model: sonnet
  - role: reviewer-performance
    model: opus
conflict_policy: no-shared-writes
fallback: sequential
```

### 共通規則

- 只平行化互不依賴工作。
- 會寫同一檔案的工作不得無協調平行執行。
- Host 沒有團隊模式時，依序呼叫 `delegate_readonly` / `delegate_write` 即可。
- workflow 不得以「Agent Teams 未啟用」作為功能本身的 hard block；最多失去平行效能。

### Claude Code adapter

可用 Agent Teams 時可使用；不可用時退化成多個 subagent 或序列執行。

### Codex adapter

若 multi-agent 已啟用，使用 host 提供的 subagent orchestration；否則序列執行。
Skill 不自行發明不存在的 team lifecycle 指令。

---

## 6. tool_probe

不要再以「某家 CLI 有沒有列出 MCP 名稱」作為唯一判定。

```yaml
capability: tool_probe
tool_kind: database
preferred_names:
  - dbhub
fallback: unavailable
```

判定順序：

1. 目前 session 是否真的有對應 tool / MCP capability 可呼叫。
2. 若 Host 有安全且穩定的 capability listing，可作輔助。
3. 查不到 → 視為 unavailable；走既有 no-MCP fallback。

**不得因為 `claude mcp list` 不存在，就判定 Codex 一定沒有 DB 工具。**

---

## 7. ask_user

Skill 只描述：

```text
ask_user(question, options, why_required)
```

不要把 `AskUserQuestion` 或其他 UI tool 名稱寫成 workflow 必要條件。
Host 沒有結構化選單時，直接用一般對話提出同一問題。

### 共通規則（所有 Host）

- `options` 以編號列出；**只有本輪明確選到某一項才算答案**。沉默、Enter、「繼續」、「ok」、「照建議」、前一輪的答案都不算，一律重問；標「建議」的選項只是標記，不是預設值，Agent 不得代選。
- 旗標是跳過詢問的捷徑（例：`/plan spec --scenarios`、`/plan-build --with-test`），不是預設值；沒帶旗標就要問。
- 答案若影響流程，只經 `crew-state.py` 寫進 `state.json`，後續 Skill 讀取、不重問。
- `ask_user` 不可用（headless：`--permission-prompts none`、`dontAsk`、排程執行、無互動輸入）且沒有對應旗標 → **BLOCK**，訊息列出所需旗標；不得用猜的補答案。
- Subagent／委派角色不得提問；需要 Human 決策時回報 Leader，由 Skill 層的主對話提問。

### Claude Code adapter

有結構化選單時用它呈現同一組編號選項；沒有時退回一般對話。選單被取消或空回覆視同沒有選擇，重問。

### Codex adapter

用一般對話逐題列出同一組編號選項（一次一題），等使用者回覆編號；「ok／繼續」或任何對不上編號的回覆一律重問，不得自行對映成某個選項。

---

## Review Once 專用 Host 能力（選用；僅 feature-workflow 的 `/plan-run` 使用，bug 型任務由 `crew-state.py` 擋）

- `trusted_human_approval`：分兩級，`state.json.autonomy.proof` 記錄是哪一級。
  - `dialogue`（同 session 一次審查）：Host 在主對話展示整份 Review Packet，Human 以 `ask_user` 明確核准指定 sha；grant 只記 packet hash，之後每站重算 hash 確認「套用的＝審過的」。信任等級等同 Interactive 的 `gate --by human`，**不是不可偽造的核准**。
  - `signed`（trusted-host）：Host 必須展示整份 Review Packet，取得使用者明確審查事件，由工作區外受保護私鑰簽署 canonical event；只有公鑰提供給 verifier，且公鑰路徑由 Host 固定，不允許 Agent 自己覆寫。
- `long_running_dispatch`：Host 保持當前互動 Session 的執行迴圈（主對話迴圈），依 `crew-state.py run --action next` 的 deterministic dispatch 呼叫現有 Skill 或 `review-once-apply.py`；Session 結束即 `paused`，只能由 `/plan-run resume` 明確恢復，不能宣稱 Python 自帶背景 Worker。
- `write_scope_enforcement`：每次 delegate_write 限於 packet 核准路徑；在 Build 進出時使用 `review-once-build.py` 的 Git-scope check。缺此能力即 BLOCK，而不是僅由 Prompt 提醒。
- `cancellation_and_reconciliation`：Host 可停止尚未完成的 worker，持久化 evidence 並以 `run pause/resume --reconcile` 恢復。Runner 的 owner / heartbeat 是**合作式租約**，不是簽章身分驗證。不可推斷 stale heartbeat 表示原 worker 已經停止。

沒有簽章能力的 Host 只能用 `dialogue` 的 session 模式，且**不得稱為無人值守**；連 `long_running_dispatch`／`write_scope_enforcement` 都沒有的 Host 請維持 Interactive。

---

## Adapter 降級矩陣

| 能力缺失 | 正確降級 | 禁止 |
|---|---|---|
| 無 subagent | 主 Agent inline 執行 | 假裝已 spawn |
| 無 multi-agent/team | 序列委派 | 阻擋整個 workflow |
| 無 per-worker model 選擇 | 保留角色/權限，標記 routing degraded | 宣稱已切換模型 |
| 無 MCP listing | 實際 probe 工具可用性 | 用另一家 CLI 指令硬判 |
| 無結構化問答 UI | 一般對話詢問 | 自行替使用者選 |

---

## 寫 Skill 時的規則

核心 `SKILL.md` 應寫：

```text
依 host-capabilities.md 呼叫 delegate_readonly，
model: sonnet，role=explorer。
```

不要寫：

```text
使用 Agent tool 建立 Sonnet subagent。
```

如果內容真的只適用某個 Host，必須明確標成：

```text
[Claude adapter only]
...
```

Host-specific 內容應盡量集中在本檔或專用 adapter reference，不要散落到每支 Skill。
