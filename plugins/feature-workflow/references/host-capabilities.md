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
