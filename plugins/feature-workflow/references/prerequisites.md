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

依序檢查：
1. `~/.claude-company/bug-workflow-config.md`
2. `~/.claude/bug-workflow-config.md`
3. `~/.claude/feature-workflow/config.md`（新階層式格式）
4. `~/.claude-company/feature-workflow-config.md`（舊格式，向下相容）
5. `~/.claude/feature-workflow-config.md`（舊格式，向下相容）

- **至少找到一個** → 繼續
- **全部不存在** → 提示並中止：
  ```
  ⚠️ 尚未完成 Workflow 初始設定。
  請先執行 /bug-setup（Bug 工作流）或 /plan-setup（功能開發工作流）。
  ```

> 若找到舊格式 feature-workflow 設定（第 5、6 項），在控制台顯示一次提示：
> `💡 偵測到舊版設定檔格式。建議執行 /plan-setup --migrate 遷移到階層式目錄結構。`

### 3. 當前專案是否已註冊？

從 `git remote get-url origin` 解析 Git Repo 識別碼，比對設定中的專案對應：
- bug-workflow：比對設定檔「專案對應」表
- feature-workflow（新格式）：檢查 `projects/{sanitized-repo-id}.md` 是否存在
- feature-workflow（舊格式）：比對設定檔「專案對應」表

- **已註冊** → 繼續，取得對應的 Notion 專案名稱
- **未註冊** → 提示（非中止，部分 Skill 仍可使用）：
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
