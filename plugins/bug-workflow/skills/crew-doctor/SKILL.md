---
name: crew-doctor
description: CREW 環境健診 —— 一次性檢查必要與選配依賴（Node/Git/Notion/委派能力/瀏覽器工具/config/專案指令），列出綠黃紅燈與修法，並依目前 Host 顯示適用建議。
---

# crew-doctor — CREW 環境健診

一次性檢查 CREW 運作所需的所有依賴與設定，在執行 Skill 前先告訴你
什麼能跑、什麼缺什麼、缺的怎麼補。比「等噴錯再排查」省時得多。

---

## 紀律護欄

> 紀律護欄：`../../references/discipline-preamble.md`（通用紀律）＋ `../../references/anti-rationalizations.md`「crew-doctor 專用」＋ `../../references/boundaries.md`「crew-doctor」段。

---

## 使用方式

```
/crew-doctor              # 完整健診（所有 20 項）
/crew-doctor --quick      # 只跑紅燈項目（8 項必要）
/crew-doctor --fix        # 健診同時嘗試自動修復可修復項目
```

---

## 檢查清單

### 🔴 必要（8 項，缺則某些 Skill 無法運作）

| # | 項目 | 檢查方式 | 缺失時提示 |
|---|------|---------|-----------|
| 1 | Node.js ≥ 18 | `node --version` | 對應 OS 安裝指令 |
| 2 | Git | `git --version` | 對應 OS 安裝指令 |
| 3 | Notion 能力 | 依 `host-capabilities.md` 的 `tool_probe(tool_kind=notion)` | 提示目前 Host 的 Notion plugin/MCP 安裝方式 |
| 4 | 委派能力 | 探測 `delegate_readonly` / `parallel_delegate` 可用層級 | 無平行能力可序列執行，不視為 BLOCK |
| 5 | CLAUDE.md 在當前專案 | `ls CLAUDE.md` | `/init` |
| 6 | bug-workflow 設定檔 | `~/.claude-company/bug-workflow-config.md` | `/bug-setup` |
| 7 | feature-workflow 設定 | `~/.claude-company/feature-workflow/config.md` | `/plan-setup` |
| 8 | 專案註冊 | `~/.claude-company/feature-workflow/projects/{repo-id}.md` | `/project-add` |

### 🟡 強烈建議（3 項，影響核心功能）

| # | 項目 | 檢查方式 | 缺失時影響 |
|---|------|---------|-----------|
| 9 | Playwright 能力 | `tool_probe(tool_kind=browser, preferred_names=[playwright])` | plan-verify 依能力降級 |
| 10 | Maven / Gradle | `which mvn` 或 `which gradle` | plan-build E4 編譯驗證跳過 |
| 11 | CREW hooks 已載入 | 見下方「#11 CREW hooks 已載入」 | 開 session 時不會提醒未結案任務，中斷的任務容易被遺忘（`plan-close` 沒做到） |

### 🟢 選配（5 項，缺少限制部分功能）

| # | 項目 | 檢查方式 | 缺失時影響 |
|---|------|---------|-----------|
| 12 | chrome-devtools 能力 | `tool_probe(tool_kind=browser, preferred_names=[chrome-devtools])` | plan-verify `--deep` 不可用 |
| 13 | DB 工具 | `tool_probe(tool_kind=database, preferred_names=[dbhub])` | DB 直連功能不可用，plan-build DB 工程師退場 |
| 14 | .NET SDK ≥ 8 | `dotnet --version` | Word 報告降級為 python-docx 排版 |
| 15 | python-docx | `python3 -c "import docx"` | 完全無 Word 報告能力（需先裝 .NET 或 docx） |
| 16 | v1 舊結構任務 | 當前專案有 `.spec/*/` 含 `README.md` 但無 `plan.md` 的目錄 | 這些任務走相容模式；過渡期到期後不再支援 → 提示 `/plan-status --migrate {slug}`，並指向 `feature-workflow/references/legacy-v1.md`（**過渡期檢查項，到期連同該檔一併移除**） |

### 🔍 進階檢查（4 項，僅當 #3 Notion MCP 通過時才跑）

| # | 項目 | 檢查方式 |
|---|------|---------|
| 17 | Notion 可讀 | 用 `notion-search` 試查 1 個現有頁面 |
| 18 | 任務追蹤工具可達 | 從設定檔讀 ID，試 `retrieve-a-data-source` |
| 19 | 設定檔欄位完整 | bug-workflow-config.md 必含「任務追蹤工具」「專案資料庫」ID |
| 20 | 共用 reference 漂移 | 若 marketplace 原始碼在本機，跑 `check-shared-refs.py` |

#### #11 CREW hooks 已載入

兩個 CREW plugin 各裝一個 **SessionStart hook**，在每次開啟 session 時於**本機**執行
`scripts/crew-state.py session-brief`，讀取**當前專案**的 `.spec/*/state.json`，列出未結案任務。
**不外送任何資料、不寫入專案檔案**；無 `.spec/` 或全部結案時零輸出。詳見 plugin README 的
「SessionStart hook（自動執行揭露）」段。

檢查步驟（三項全綠才算通過）：

| 步驟 | 指令 | 綠燈條件 |
|------|------|---------|
| a. hook 設定檔存在 | `ls "$(claude plugin list --json \| ...)"` 或直接找已安裝路徑下的 `hooks/hooks.json` | 兩個 plugin 各有一份 |
| b. python3 可執行 | `python3 --version` | 有輸出（hook 指令用 `python3`，找不到就整個 hook 靜默失效） |
| c. 指令實際可跑 | `python3 <plugin>/scripts/crew-state.py session-brief --cwd . < /dev/null` | exit 0（有未結案任務才有輸出，無則零輸出，兩者皆為正常） |

| 狀態 | 判定 |
|------|------|
| ✅ 綠 | a/b/c 全過 |
| ⚠️ 黃 | a 過但 b 或 c 失敗 → 提示：hook 已註冊但跑不起來，開 session 不會有提醒 |
| ⚠️ 黃 | a 失敗 → 提示：plugin 版本過舊或未重啟。修法：`/crew-upgrade` 後**重啟 Claude Code**（hook 變更不會熱載入） |

此項**永遠不會是紅燈** —— hook 只做提醒，缺少它不影響任何 Skill 執行。

---

## 流程

### 1. 偵測作業系統

```
case "$(uname)" in
  Darwin*) OS=macos ;;
  Linux*)  OS=linux ;;
  MINGW*|MSYS*|CYGWIN*) OS=windows ;;
esac
```

OS 決定缺失提示的指令（例如 `brew install node` vs `winget install Node`）。

### 2. 跑必要項目（#1-8）

依序執行，每項通過或失敗都立即顯示在輸出中。
紅燈項目**不阻擋**後續檢查（要把完整圖像給使用者）。

### 3. 跑強烈建議（#9-11）與選配（#12-16）

執行後標示為 🟡 警告或 🔵 選配。
#11（CREW hooks）純本地檢查，不需 Notion，也不需網路。

### 4. 進階檢查（#17-20，僅當 #3 通過時）

Notion 相關檢查需要實際 API call，每項 1-3 秒。
若 #3 紅燈，跳過 #17-20（沒有 Notion 後端跑不了，含共用 reference 漂移檢查）。

### 5. 產出摘要

```
==========================================
CREW 環境健診摘要
==========================================

🔴 紅燈 0 項
🟡 黃燈 1 項
🟢 綠燈 14 項
🔵 選配 5 項（其中 2 項未安裝）

可用 Skill 評估：
  ✅ bug-investigate / bug-fix / bug-close 可用
  ✅ /plan（spec/db/arch 三 pass）/ plan-build 可用
  ⚠️  plan-verify 降級：Playwright 未裝，無法做瀏覽器驗收
  🔵 plan-verify --deep 不可用：chrome-devtools 未裝（影響有限）

建議下一步：
  1. 安裝 Playwright 解開 plan-verify：
     claude mcp add playwright --scope user -- \
       npx @playwright/mcp@latest
```

### 6. `--fix` 模式

對下列項目嘗試自動修復：

| 項目 | 修法 |
|------|------|
| ~/.claude-company/feature-workflow/ 缺失 | `mkdir -p` |
| ~/.claude-company/feature-workflow/projects/ 缺失 | `mkdir -p` |
| ~/.claude-company/feature-workflow/stacks/ 缺失 | `mkdir -p` |
| 無 parallel delegation | 不需修復；CREW 自動序列執行。若使用者想啟用 Host 的平行能力，再提供該 Host 專屬指引 |

**不會自動修復**（仍要使用者操作）：
- MCP 安裝（要 `claude plugin/mcp` 指令）
- Notion 授權（互動式 OAuth）
- CLAUDE.md 建立（要 `/init`）
- Notion 資料庫建立（要 `/bug-setup` 互動建立）

`--fix` 修了什麼會明確列出，並建議再跑一次 `/crew-doctor` 確認。

### 7. 健診結果狀態

本 Skill 為 LLM 驅動的健診流程，無腳本可回傳退出碼；健診結果以下列狀態呈現在摘要中：

| 狀態 | 意義 |
|------|------|
| 🟢 綠 | 紅燈全過（不論黃燈、選配如何） |
| 🔴 紅 | 有必要項目（#1-8）未通過 |
| ⚠️ 異常 | 健診本身執行錯誤（檔案 IO、permission），提示無法完成健診 |

---

## 輸出範例

```
==========================================
🔍 CREW 環境健診（v3.9.0）
==========================================

🔴 必要項目（8）
   ✅ Node.js v18.20.4
   ✅ Git 2.45.0
   ❌ Notion MCP 未安裝
      → 修法：claude plugin install notion
      → 安裝後重啟 Claude Code
   ✅ 委派能力：parallel_delegate 可用
   ✅ CLAUDE.md 存在於 /Users/cheng/IdeaProjects/MyProject
   ✅ bug-workflow-config.md 存在
   ✅ feature-workflow/config.md 存在
   ❌ 專案未註冊（找不到 projects/{repo-id}.md）
      → 修法：/project-add

🟡 強烈建議（3）
   ✅ Playwright MCP 已安裝
   ⚠️  Maven / Gradle 未找到
      → 影響：plan-build E4 編譯驗證會跳過
   ✅ CREW hooks 已載入（bug-workflow + feature-workflow，python3 3.11.9）

🔵 選配（5）
   ⚫ chrome-devtools MCP 未安裝（--deep 模式不可用）
   ✅ DBHub MCP 已安裝
   ✅ .NET SDK 8.0.100
   ⚫ python-docx 未安裝（有 .NET 不影響）
   ✅ 無 v1 舊結構任務

🔍 進階檢查（4）
   ⏭️  跳過：紅燈未過（Notion MCP 缺失）

==========================================
摘要：紅燈 2、黃燈 1、綠燈 13、選配 5
建議：先 claude plugin install notion，再 /project-add
==========================================
```

---

## 何時不用

- 程式或測試為何壞掉（非 CREW 環境依賴）→ 個人 `investigate` skill 或 `superpowers:systematic-debugging`
- CREW 首次設定 → `/crew-init`
- 更新 CREW plugins → `/crew-upgrade`
- 一般專案環境問題（非 CREW 依賴）→ 自行排查

## Gotchas

- **工具探測不要綁 CLI 輸出格式**：一律依 `host-capabilities.md` 的 `tool_probe`，以 session 真正可呼叫能力為準
- **跨平台路徑**：Windows 用 `%USERPROFILE%`、Unix 用 `$HOME`
- **Notion API 速率限制**：#17-18 試查若被 throttle，標示為 ⚠️ 不算失敗
- **`--fix` 改 settings.json 風險**：先 cp settings.json.bak，失敗能還原
- **MCP 未啟用 vs 未安裝**：`claude plugin list` 顯示 `enabled` 才算可用

---

## 邊界情況

- **`claude` CLI 本身找不到**：跳出健診，提示「請確認 Claude Code 已安裝」
- **HOME 環境變數異常**：跳出健診，提示「無法定位設定檔目錄」
- **Notion 授權過期**：#17 失敗時提示「請在 Notion 中重新授權」
- **使用者在 plugin marketplace 原始碼裡跑**：#20 才會跑，否則跳過
- **#11 hook 檢查在舊版 plugin 上**：引入 SessionStart hook 之前的版本沒有 `hooks/hooks.json`，找不到屬正常，提示 `/crew-upgrade` 即可，不算故障
- **剛升級但未重啟**：hook 變更不會熱載入，`hooks/hooks.json` 檔案在但 hook 尚未生效，需重啟 Claude Code
