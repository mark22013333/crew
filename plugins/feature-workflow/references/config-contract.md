# CREW Portable Config Contract

> CREW 自己擁有的設定資料以 logical key 存取；Skill 不應把 `~/.claude` 當成核心資料模型。
> Host 安裝狀態、plugin marketplace、`settings.json`、host-native rules **不屬於本 contract**。

---

## 1. Canonical root

解析順序：

1. `CREW_CONFIG_HOME`
2. `$XDG_CONFIG_HOME/crew`
3. `~/.config/crew`

`CREW_CONFIG_HOME` 是 portable override；未設定時使用 XDG-style user config 目錄。

Resolver **不會自動搬檔、不會自動建立目錄、不會修改 legacy 檔案**。

---

## 2. Logical keys

| Logical key | 必要參數 | Canonical path |
|---|---|---|
| `feature/config` | — | `{root}/feature/config.md` |
| `feature/project` | `--repo-id` | `{root}/feature/projects/{sanitized-repo-id}.md` |
| `feature/stack` | `--stack-id` | `{root}/feature/stacks/{stack-id}.md` |
| `bug/config` | — | `{root}/bug/config.md` |
| `bug/learning` | `--project-slug` | `{root}/bug/learnings/{project-slug}.jsonl` |

`feature/project` 的檔名規則沿用現有 CREW：repo id 中的 `/` 或 `\` 轉成 `--`。
`stack-id` 與 `project-slug` 必須是單一安全檔名，不接受路徑穿越。

---

## 3. Read / write 語意

### read

`read` 依序找：

1. canonical portable path
2. 已知 legacy Claude 路徑

找到第一個存在的檔案就回傳。若全部不存在：

- `exists=false`
- `source=missing`
- `path` 仍回 canonical path，讓 caller 能顯示「應建立在哪裡」
- 不自動建立檔案

### write

`write` **永遠回 canonical portable path**，不寫入 legacy 路徑。

這個規則讓 Skill 可以逐支遷移：讀取時相容舊環境，新的寫入逐步集中到 portable root。

---

## 4. Legacy fallback

目前 Claude 現役 fallback **只接受 `~/.claude`**。
`~/.claude-company` 已退役，不讀取、不遷移、不當 compatibility path。

### feature/config

依序：

1. `~/.claude/feature-workflow/config.md`
2. `~/.claude/feature-workflow-config.md`

### feature/project / feature/stack

先找階層式 legacy 目錄：

- `~/.claude/feature-workflow/projects|stacks/...`

若不存在，再回退到舊單一檔案：

- `~/.claude/feature-workflow-config.md`

此時 resolver 回 `representation=legacy_monolith`；caller 必須使用舊 parser 擷取 project/stack 區塊，不能把 monolith 當成獨立 project/stack 檔。

### bug/config

- `~/.claude/bug-workflow-config.md`

### bug/learning

- `~/.claude/bug-workflow/learnings/{project-slug}.jsonl`

---

## 5. CLI contract

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"

python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key feature/config --mode read --format json

python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key feature/project --repo-id github.com/org/repo --mode read --format path

python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key bug/learning --project-slug github.com-org-repo --mode write --format json
```

JSON 至少包含：

- `key`
- `mode`
- `root`
- `canonical_path`
- `path`
- `exists`
- `source`：`portable | legacy | missing`
- `representation`：`hierarchical | legacy_monolith`
- `legacy`

---

## 6. 邊界

本 contract **不解析或管理**：

- Claude / Codex plugin 安裝與更新
- marketplace cache / installed plugin registry
- `~/.claude/settings.json`
- `~/.claude/rules/*`
- 已退役的 `~/.claude-company/*`
- Host 的 hook discovery
- Host-native project instruction 檔名

上述項目屬 host-management adapter 或 `project_instructions` capability，不應塞進 config resolver。
