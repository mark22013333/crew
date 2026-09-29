# Windows 使用者指南

CREW 6 支援在 Windows 上使用，但實際 shell、sandbox、MCP 與 plugin 管理方式取決於你使用的 Host。核心 workflow 依賴的是 Host Capability Contract，不要求 Windows 使用者模擬某一家 Host 的目錄或 team API。

## Host 選擇

### Claude Code

使用你已安裝的 Claude Code surface（CLI / IDE / desktop 整合）。Claude-specific plugin/MCP/settings 指令只屬 Claude adapter。

### Codex

使用目前官方支援的 Codex Windows 安裝方式或 WSL2。不同 Codex 版本的 sandbox/IDE 行為可能不同，以執行當下官方文件為準；CREW 不把 sandbox 實作細節寫進 workflow contract。

---

## 建議工具

| 工具 | 用途 |
|------|------|
| Git | repo-id、diff、branch、commit |
| Python 3 | CREW deterministic runtime scripts |
| Node.js / npm | 只有使用 Node-based MCP / report tooling 時需要 |
| 專案 build tool | Maven / Gradle / npm / dotnet 等依專案而定 |

## Shell 差異

Windows 原生 PowerShell/CMD 與 POSIX shell 指令不同：

- 若某個 Skill/reference 展示 `grep` / `find`，Host adapter 可用 PowerShell 等價能力或 Git Bash / WSL2。
- 不要把 Unix command 名稱本身當 workflow contract；真正需要的是 repository search / file discovery capability。
- Path 由 runtime/tool 正規化，不應把某個 Host home directory 當 CREW-owned config root。

## Portable Config

若希望 Windows 上有明確且穩定的 CREW config 位置，可設定：

```powershell
$env:CREW_CONFIG_HOME = "$HOME\.config\crew"
```

未設定時仍依 portable resolver contract：

1. `CREW_CONFIG_HOME`
2. `XDG_CONFIG_HOME/crew`（若有）
3. `~/.config/crew`

這和 Claude/Codex 自己的 plugin cache、settings、rules 位置是兩回事。

## Project instructions

CREW 接受：

- `AGENTS.md`
- `CLAUDE.md`

Codex 不需要為了 CREW 額外建立 Claude 專屬檔案；Claude Code 也可以讀既有 `AGENTS.md`。

## 外部工具

Browser / DB / Notion 能力以目前 Host 的實際 tool probe 為準。DBHub 的 Host-specific 安裝範例見 [dbhub.md](./dbhub.md)。

> `/bug-setup`、`/plan-setup` 與 `/crew-doctor` 應以 portable resolver / capability contract 判斷環境，不自行假設 Windows 上一定存在某個 `~/.claude...` storage。
