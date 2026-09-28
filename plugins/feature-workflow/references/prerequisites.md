# 共用前置檢查

所有 CREW Skill（除 `bug-setup`、`plan-setup`、`project-add` 本身外）在流程開始前必須執行以下檢查。

Setup Skill（`bug-setup`、`plan-setup`）執行第 0 項基礎環境檢查，其餘項目跳過。

---

## 檢查項目

### 0. 基礎環境是否就緒？（僅 setup 時檢查）

`bug-setup` 和 `plan-setup` 在最開頭執行此檢查，確保後續所有 MCP 安裝能正常運作。

**檢查 Node.js：**

```bash
node --version 2>/dev/null
npx --version 2>/dev/null
```

- **兩者皆可用** → 繼續
- **不可用** → 提示並中止：

  **macOS / Linux：**
  ```
  ⚠️ 未偵測到 Node.js。CREW 的 MCP Server（Notion、Playwright、DBHub 等）皆需要 Node.js 執行。

  安裝方式（擇一）：
    • Homebrew：brew install node
    • nvm：curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash && nvm install --lts
    • 官網下載：https://nodejs.org/

  安裝完成後重新啟動終端，再次執行此指令。
  ```

  **Windows：**
  ```
  ⚠️ 未偵測到 Node.js。CREW 的 MCP Server（Notion、Playwright、DBHub 等）皆需要 Node.js 執行。

  安裝方式（擇一）：
    • 官網下載（推薦）：https://nodejs.org/ → 下載 LTS 版 → 安裝時勾選「Add to PATH」
    • winget：winget install OpenJS.NodeJS.LTS
    • WSL2 環境：sudo apt install nodejs npm

  安裝完成後重新啟動 Claude Code，再次執行此指令。
  ```

**檢查 Git：**

```bash
git --version 2>/dev/null
```

- **可用** → 繼續
- **不可用** → 提示並中止：

  **macOS：**
  ```
  ⚠️ 未偵測到 Git。

  安裝方式：xcode-select --install
  ```

  **Windows：**
  ```
  ⚠️ 未偵測到 Git。

  安裝方式：
    • 官網下載（推薦）：https://git-scm.com/download/win
    • winget：winget install Git.Git
  安裝時建議勾選「Git from the command line and also from 3rd-party software」。
  ```

  **Linux：**
  ```
  ⚠️ 未偵測到 Git。

  安裝方式：sudo apt install git（Ubuntu/Debian）或 sudo yum install git（CentOS/RHEL）
  ```

**偵測作業系統的方式：**

```bash
uname -s 2>/dev/null || echo "Windows"
# Darwin → macOS
# Linux → Linux
# MINGW* / MSYS* / CYGWIN* → Windows (Git Bash / MSYS2)
# 指令不存在 → Windows (CMD / PowerShell)
```

### 0.5 Notion 後端偵測（所有需要 Notion 的 Skill）

每個 session 第一次需要 Notion 操作時執行偵測，結果在 session 中復用。

```
1. 嘗試使用 Notion Plugin 工具（如 notion-search）
   → 可用 → NOTION_BACKEND = "plugin"（優先）

2. 不可用 → 嘗試使用 notion-local 工具（如 API-post-search 或 API-get-self）
   → 可用 → NOTION_BACKEND = "local"

3. 都不可用 → 提示安裝（兩種方式擇一）並中止
```

偵測成功後，依據 `NOTION_BACKEND` 參照 `references/notion-backend.md` 的映射表選擇對應工具。

> 此偵測不限於 setup — 任何需要 Notion 操作的 Skill 首次呼叫時都會觸發。

### 1. 專案指令是否存在？

依 `references/host-capabilities.md` 的 `project_instructions` 解析專案指令。

接受：
- `AGENTS.md`
- `CLAUDE.md`

至少一份存在 → 繼續。兩份都存在 → 都可讀；有實質衝突時列為歧義點，不自行忽略其中一份。

兩份都不存在 → 提示並中止：

```
⚠️ 當前專案尚未提供 CREW 可讀的專案指令。
請建立 AGENTS.md 或 CLAUDE.md：
  • Codex：建議 AGENTS.md
  • Claude Code：可用 /init 建立 CLAUDE.md
建立後建議 commit 並 push，讓團隊成員共用。
```

### 2. Workflow 設定是否存在？

不要自行判斷 Host-specific 實體路徑。先用 portable config resolver 解析 Bug / Feature 設定：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"

python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key bug/config \
  --mode read \
  --format json

python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key feature/config \
  --mode read \
  --format json
```

分別讀取兩次 resolver 回傳的 `source / representation / path`：

- **任一 `source != missing`** → 繼續。
- **兩者都是 `source=missing`** → 提示並中止：
  ```
  ⚠️ 尚未完成 Workflow 初始設定。
  請先執行 /bug-setup（Bug 工作流）或 /plan-setup（功能開發工作流）。
  ```
- Feature resolver 若回 `representation=legacy_monolith` → 在控制台顯示一次：
  `💡 偵測到舊版設定檔格式。建議執行 /plan-setup --migrate 遷移到階層式目錄結構。`

Legacy fallback 的實體位置只由 `references/config-contract.md` 與 `crew-config.py` 負責；本 precheck 不得自行列舉或重試 Host path。

### 3. 當前專案是否已註冊？

先沿用 `/project-add` 的規則，從 `git remote get-url origin` 解析 Git Repo 識別碼 `{repo-id}`，再解析 Feature project：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"

python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key feature/project \
  --repo-id "{repo-id}" \
  --mode read \
  --format json
```

專案對應判斷：

- **bug-workflow**：若步驟 2 的 `bug/config` 存在，仍比對該設定檔「專案對應」表。
- **feature/project + `representation=hierarchical`**：讀 project frontmatter，以 `git_repo` 精確匹配 `{repo-id}`，取得 `notion_name`。
- **feature/project + `representation=legacy_monolith`**：沿用既有舊設定「專案對應」表 parser，以 `{repo-id}` 精確匹配。
- **feature/project + `source=missing`**：Feature project 視為未註冊，不自行拼 `projects/{sanitized-repo-id}.md` 路徑。

Bug 或 Feature 任一來源能精確匹配目前 repo → **已註冊**，繼續並取得對應的 Notion 專案名稱。

全部未匹配 → 提示（非中止，部分 Skill 仍可使用）：
```
⚠️ 當前專案尚未註冊到 Notion。
建議執行 /project-add 將專案加入 Notion 專案資料庫。
```

---

## 適用範圍

| Skill | 基礎環境(0) | Notion 偵測(0.5) | 專案指令(1) | 設定檔(2) | 專案註冊(3) |
|-------|:---:|:---:|:---:|:---:|:---:|
| `bug-setup` | ✅ | ✅ | — | — | — |
| `plan-setup` | ✅ | ✅ | — | — | — |
| `project-add` | — | ✅ | — | ✅ | — |
| `bug-start` | — | ✅ | ✅ | ✅ | ✅ |
| `bug-investigate` | — | — | ✅ | — | — |
| `bug-update` | — | ✅ | ✅ | ✅ | ✅ |
| `bug-fix` | — | — | ✅ | — | — |
| `bug-close` | — | ✅ | ✅ | ✅ | ✅ |
| `plan-start` | — | ✅ | ✅ | ✅ | ✅ |
| `plan` | — | — | ✅ | — | — |
| `plan-build` | — | — | ✅ | — | — |
| `plan-verify` | — | — | ✅ | — | — |
| `plan-review` | — | — | ✅ | — | — |
| `plan-close` | — | ✅ | ✅ | ✅ | ✅ |
| `plan-sync` | — | ✅ | ✅ | ✅ | ✅ |
| `plan-status` | — | — | ✅ | — | — |
| `plan-stack` | — | — | ✅ | — | — |
