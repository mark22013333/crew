# CREW Changelog

所有 CREW plugins（bug-workflow、feature-workflow）的變更紀錄。

格式：每個版本一個區塊，以 `## [plugin@version]` 開頭。
尚未發版的變更暫放在最上方的 `## [Unreleased]` 區塊，發版時併入該版號區塊。
`/crew-upgrade` 會讀取此檔案，顯示上次更新以來的變更摘要。

---

## [bug-workflow@4.0.2] - 2026-09-29

> **Portable CREW update workflow。** `/crew-upgrade` 不再讀 Host 私有 plugin cache/registry，也不再保留 `.claude-company` fallback；改由目前 Host 的公開 plugin CLI 執行更新。

### Fixed

- `/crew-upgrade` 改成 Host-aware：
  - Claude Code：`claude plugin marketplace update company-marketplace` + `claude plugin update ...`
  - Codex：`codex plugin marketplace upgrade crew` + `codex plugin list`
- 移除對 `installed_plugins.json`、Host marketplace cache 路徑與已退休 `.claude-company` 的依賴。
- 明確禁止發明不存在的 Codex plugin-specific update 子命令。

### Changed

- Root / Bug / Feature README 新增「更新既有 CREW」說明，提供 `/crew-upgrade` 與 Host-native 手動復原指令。
- `scripts/lint-skill-contract.py` 新增 crew-upgrade portability guard；`scripts/lint-readme-architecture.py` 要求 README 持續保留更新入口。

---

## [feature-workflow@5.0.2] - 2026-09-03

> **移除 `plugin.json` 的 `hooks` 欄位。** 標準路徑 `hooks/hooks.json` 會被 Claude Code
> 自動載入，manifest 再宣告一次會被判為重複，**整份 hook 因此完全不載入**。
> 亦即 5.0.2 之前的 SessionStart hook（`crew-state.py session-brief`）實際上是失效的。

### Fixed

- 移除 `plugin.json` 的 `"hooks": "./hooks/hooks.json"`。Claude Code 的錯誤原文：
  `Duplicate hooks file detected: ./hooks/hooks.json resolves to already-loaded file …
  The standard hooks/hooks.json is loaded automatically, so manifest.hooks should only
  reference additional hook files.`
  檔案本身無需改動，`hooks/hooks.json` 仍會自動載入。

### Changed

- **`scripts/lint-plugin-manifest.py` 新增第 7 項檢查** —— `hooks` 欄位（字串或陣列）
  不得宣告標準路徑 `hooks/hooks.json`；指向額外 hook 檔案仍合法。

---

## [feature-workflow@5.0.1] - 2026-09-03

> **修 `plugin.json` 的 skills 清單。** 5.0.0 刪了三個 skill 目錄但沒同步陣列，
> 導致 plugin 載入時報 `skills path not found`。純清單修正，無功能變更。

### Fixed

- `plugin.json` 的 `skills` 陣列移除三個已在 5.0.0 刪除的路徑：`plan-spec`、`plan-db`、`plan-arch`。
  這三個 skill 在 5.0.0（plan.md 單一文件契約）已併入 `/plan`，目錄不存在，
  Claude Code 載入 plugin 時會在 `/plugin` 介面顯示
  `skills path not found: .../skills/plan-spec` 紅字。
- `plugin.json` 補上漏宣告的 `plan-drift`（5.0.0 新增的 skill，目錄一直存在但從未寫進陣列）。

### 影響範圍

不影響技能可用性 —— Claude Code 以掃 `skills/` 目錄為主，陣列中不存在的路徑只印錯誤、
不中斷其餘 skill 載入（`plan-drift` 未被宣告仍可正常呼叫即為證據）。此版純粹消除該錯誤訊息。

### 為何 CI 沒攔到

`lint-skills.py`、`lint-readme-sync.py` 都以「掃 `skills/` 實際目錄」為基準，
不比對 `plugin.json` 陣列，因此陣列與目錄不一致屬於檢查盲區。

### 防回歸

- **`scripts/lint-plugin-manifest.py`（新增）** —— 補上「manifest 宣告 vs 實際檔案」這個維度，
  檢查六項：skills 陣列宣告但目錄不存在、目錄存在但未宣告、陣列重複宣告、
  宣告的 skill 缺少或空白 `SKILL.md`、`hooks` 路徑不存在、
  `marketplace.json` 的 `source` 與 `plugins/` 未一一對應。
  以 5.0.0 當時的 `plugin.json` 實測，會輸出 4 個錯誤並讓 CI 紅燈。
- **CI job `plugin-manifest`（新增）** —— 於 `lint.yml` 以 python 3.11 執行上述腳本，違規阻擋。
- **CONTRIBUTING.md 新增「新增／刪除 Skill Checklist」** —— 明訂動 `skills/` 目錄時
  同一個 commit 必須同步 `plugin.json` 陣列、兩份 README 指令表與 CHANGELOG。

---

## [bug-workflow@4.0.1] - 2026-09-03

> 與 feature-workflow@5.0.2 同批發布，同一個 `hooks` 重複宣告問題。

### Fixed

- 移除 `plugin.json` 的 `"hooks": "./hooks/hooks.json"`，修正
  `Duplicate hooks file detected` 導致整份 hook 不載入。詳見 feature-workflow@5.0.2 區塊。

---

## [feature-workflow@5.0.0] - 2026-07-28

> **major 版：`.spec/` 結構重構。** 文件只寫程式碼裡看不到的東西，「是什麼」用錨點指過去。
> 一招同時解掉 Token 昂貴與文件漂移兩個問題。含 SessionStart hook 與 v1 遷移路徑。

### ⚠️ 重要變更：安裝後會在你的機器上自動執行程式（SessionStart hook）

**這是 plugin 行為的實質變更，不是單純加一個功能。** 升級到含此變更的版本後，
`bug-workflow` 與 `feature-workflow` 各會註冊一個 **SessionStart hook**——
在你每次開啟 Claude Code session 時（新開、`--resume`、`/clear`），
**不會逐次詢問**，直接在你的本機執行一行指令：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" session-brief --cwd "${CLAUDE_PROJECT_DIR}"
```

決定要不要升級之前，先讀完這張表：

| 面向 | 事實 |
|------|------|
| 讀什麼 | 只讀**當前專案**目錄下的 `.spec/*/state.json`。不掃家目錄、不掃其他專案 |
| 寫什麼 | **不寫任何專案檔案。** 只在系統暫存目錄寫一個 session marker（兩 plugin 同裝時去重用） |
| 網路 | **完全不外送資料。** 純 Python 標準函式庫，程式碼裡沒有任何網路呼叫 |
| 執行者 | 你本機的 `python3`。找不到 `python3` 時整個 hook 靜默失效，不報錯 |
| 輸出 | 未結案任務最多 3 行＋`/plan-next {slug}`；超過 3 個時多印一行「另有 N 個」 |
| 沒東西可報時 | **零輸出、exit 0**，不佔任何 token |
| 失敗時 | 一律靜默 exit 0，**絕不阻擋 session**。內建 1 秒總體時限（讀 stdin 上限 0.2 秒）與非阻塞 stdin 讀取；實測典型耗時約 80ms |
| 怎麼關 | `claude plugin disable <plugin>`（連 Skill 一起關）；或刪掉已安裝目錄的 `hooks/hooks.json` 後重啟（只關 hook） |

動機：中斷的任務會被遺忘，`plan-close` 因此沒做到。在此之前兩個 plugin 全樹零 hook，
完全靠使用者自己記得打 `/plan-status`。

### 新增

- **`plugins/bug-workflow/hooks/hooks.json`、`plugins/feature-workflow/hooks/hooks.json`** —
  SessionStart hook 設定。matcher `startup|resume|clear`（不掛 `compact`，避免自動壓縮後重複提醒），
  `timeout: 5` 秒上限。輸出以 `hookSpecificOutput.additionalContext` 形式注入
  （純 stdout 在 Claude Code 只會顯示成 hook 狀態行、不會進模型 context，故必須包一層 JSON）
- **兩個 `plugin.json` 新增 `"hooks": "./hooks/hooks.json"`** — 明確宣告 hook 設定路徑
- **`crew-doctor` 新增 #11「CREW hooks 已載入」** — 🟡 強烈建議層級，永遠不會是紅燈（hook 只做提醒，
  缺少不影響任何 Skill）。檢查 hook 設定檔存在／`python3` 可執行／指令實跑 exit 0 三項。
  原 #11–18 順延為 #12–19，健診總項數 18 → 19
- **根 README 與兩個 plugin README 新增「SessionStart hook（自動執行揭露）」段** —
  逐項寫明讀什麼、寫什麼、不外送、何時零輸出、怎麼關

### ⚠️ 破壞性變更：`.spec/` 結構從 12–17 檔縮成 3 檔

一個 feature 原本產 12–17 個檔、實測純文字 1893–2385 行。根因是文件大量**抄寫**了
「程式碼才是唯一事實」的內容（欄位清單、方法簽章、類別清單、DDL、檔案清單）——
抄寫本身是 Token 昂貴的主因，而抄本在程式碼一改就變成謊話，且沒有任何檢查抓得到。

新結構：

```
.spec/{slug}/
├── plan.md      六章節，只寫程式碼裡看不到的東西（需求、決策與理由、
│                被否決方案、驗收條件、取捨）；「是什麼」用 @code: 錨點指過去
├── state.json   流程狀態唯一權威，唯一寫者 crew-state.py
└── deploy.sql   唯一 SQL 事實來源
```

實測：`plan.md` 47 行 ＋ `deploy.sql` 28 行 ＋ `state.json` 111 行 = **186 行**，
較舊結構減約 **90–92%**。且 `state.json` 是機器讀的——`/plan-next` 實際餵給模型的
只有 **85 bytes** 的結構化答案，不是 2055 bytes 的 JSON 原文。

**廢除的產物**：`README.md`（任務層）、`spec.md`、`db.md`、`arch.md`、`db.sql`、
`deploy-checklist.md`、`files.md`、`log.md`、`handoff.md`、`.spec/_index.md`；
`review.md`／`security.md` 不再落檔（摘要一行進 plan.md）；
`verify.md` 降為 `.cache/` 暫存；Word/Excel 報告移出主流程改為可選指令。

**廢除的 skill**：`/plan-spec`、`/plan-db`、`/plan-arch` → 併為 `/plan` 的三個 pass
（仍可 `/plan spec|db|arch` 單跑，且單跑不等於可以跳過確認）。

**新增的 skill**：`/plan-drift` —— 檢查 `plan.md` 錨點是否失效。機械型（改名、行號位移）
自動修，語意型逐條請使用者確認；符號消失常代表決策變了，該改的是決策紀錄而非硬改指標。

**新增的硬關卡**：`/plan-close` 結案前跑漂移檢查，FAIL 擋、WARN 逐筆明示放行
（不提供「全部放行」選項——那等於沒問）。通過才蓋 `verified_at_commit` 的章。
這是全流程唯一會擋下結案的檢查，因為錯過這一刻，漂移的文件會被**原樣**推到 Notion
並長期腐爛，把不可信的內容傳播出去比不同步更糟。

### 舊任務怎麼辦（過渡期一個 minor 版或 90 天）

**預設：照舊跑完。** v1 任務（`.spec/{slug}/plan.md` 不存在）會自動走相容模式，
相容邏輯集中在 `feature-workflow/references/legacy-v1.md`，各 skill 只放一行分支引用。
**不建議中途換軌**——遷移搬得動結構，搬不動語意，中途換軌會讓你在收尾階段面對一份半空的
`plan.md`。

**要遷移：`/plan-status --migrate <slug>`。** 只做**機械搬移**：舊文件原封搬進
`archive/`（一個字不改）、`db.sql` 併入 `deploy.sql`、frontmatter 轉 `state.json`、
`plan.md` 各章節留 `TODO(migrate)` 佔位**由人補**。

🔴 **刻意不做自動語意轉換。** 把 425 行的 `spec.md` 壓成 80 行看起來很適合交給 LLM，
但壓縮不可驗證、會幻覺出從未做過的決策，而且原文搬進 `archive/` 後不會有人再去對照。
一份誠實的空白，比一份看似完整的幻覺有用。

`crew-doctor` 新增 #16 偵測 v1 舊任務（健診總項數 19 → 20）。

### 已知限制

- hook 變更**不會熱載入**。安裝或升級後必須**重啟 Claude Code** 才生效；
  `/crew-doctor` #11 在「檔案已在但尚未重啟」時會誤報綠燈
- hook 指令寫死 `python3`。環境若只有 `python3.11` 而無 `python3`，hook 會靜默不執行

---

## [bug-workflow@4.0.0] - 2026-07-28

> **major 版：斷點保險從 `handoff.md` 檔案改為 `state.json`，且結案不再刪除。**
> 與 feature-workflow@5.0.0 同批發布，兩者共用 `crew-state.py` 與 `state-discipline.md`。

### ⚠️ 破壞性變更

- **共用 reference `handoff-discipline.md` 更名為 `state-discipline.md`** —— 內容從
  「怎麼寫 `handoff.md`」改為「怎麼用 `crew-state.py` 維護 `state.json`」。
  保留原有紀律道理（進度即寫、歧義點當場記、已完成必附證據），只換載體；
  新增「唯一寫者」與「自我修復 `rebuild`」兩節
- **`bug-close` 不再刪除斷點檔** —— 舊版結案時 `rm -f handoff.md`；新版改為
  `crew-state.py set --step close --status done`，**保留 `state.json` 並入版控**。
  `/plan-deploy-confirm` 事後要靠它查 `steps.close.status` 與 `deploy` 執行進度，
  刪掉就查不到「這個任務的 SQL 到底跑了沒」
- **bug 型輕量目錄只放 `state.json`**（原本只放 `handoff.md`），用
  `crew-state.py init --type bug` 建立

### 新增

- **`scripts/crew-state.py`（共用 script，權威副本在本 plugin）** —— `.spec/{slug}/state.json`
  的單一寫者。子命令 `init/set/unit/result/next/list/park/unpark/rebuild/validate/session-brief`。
  `flock` 加鎖 ＋ `os.replace()` 原子寫入；`rebuild` 可從 git 與檔案系統重建並標 `inferred`。
  純 stdlib、python 3.11
- **SessionStart hook** —— 見上方 feature-workflow@5.0.0 的揭露段
- **`crew-doctor` #11 CREW hooks 已載入、#16 v1 舊結構任務偵測** —— 健診項數 18 → 20
- **`scripts/check-shared-refs.py` 新增 `SHARED_SCRIPTS`** —— 共用 script 也納入 sha256
  一致性檢查（與 reference 的差別：來源尚未建立時優雅跳過）

### 修正

- **`sync-shared-refs.sh` 的改名陷阱** —— 目標檔不存在時原本直接 `exit 1`，導致共用檔
  無法改名。改為同步模式自動建立、`--check` 模式回報缺失，行為與 `SHARED_SCRIPTS` 迴圈一致
- **`model-policy.md` 角色對照表** —— `/plan-db` 已廢除、`db.md`／`db.sql` 已廢除，
  改為 `/plan` 的三個 pass 與 `deploy.sql`

---

## [feature-workflow@4.26.0] - 2026-07-27

> 模型分工政策落地——探索與文件用 Sonnet、正式實作與高風險判斷用 Opus，且模型一律以結構化 `model` 參數傳入（不再靠自然語言「使用 Opus 模型」）。流程、Agent Teams、`.spec/`、Notion 整合與退出驗證全部不變。

### 新增
- **共用 reference `model-policy.md`（第 6 個共用檔）** — Sonnet／Opus 工作清單、角色→模型對照表、「只有 `/plan-build` 與 `/bug-fix` 可改正式程式碼」邊界、探索→實作交接模板、深度調查交接模板、Dynamic Workflow／Ultracode 相容性說明；納入 `check-shared-refs.py`、`sync-shared-refs.sh`、CONTRIBUTING.md 清單（5→6 檔）
- **plan-build 探索官（scout）** — 步驟 5 分層脈絡改由 Leader 派唯讀 subagent（`model: sonnet`）完成並產出「實作交接」；`build-prompts.md` 新增「探索官模式」prompt 模板與 `{scout_handoff}` 變數
- **team-composition.md 模型配置段** — 角色性質→模型對照（唯讀探索 sonnet／正式實作 opus），明示團隊人數不影響模型選擇

### 改善
- **feature-spec-analyst 改 `model: sonnet`** — 規格分析屬唯讀文件工作；新增責任邊界（可寫 `.spec/`、不改正式程式碼、不啟 Agent Teams／Dynamic Workflow、不自行升級 Opus、不自動往下觸發）
- **plan-spec 改派 `model: sonnet`** — 加硬性規則：必須實際傳入結構化參數、禁止改正式程式碼、禁止自動啟 `/plan-build`、禁止建 Agent Team；規格確認迴圈與 `.spec/{slug}/spec.md` 格式不變
- **plan-review 模型重配** — Logic Reviewer Opus→Sonnet、Quality 維持 Sonnet、Performance 維持 Opus；`--quick` Opus→Sonnet；新增「小變更可三人全 Sonnet 或改跑 `--quick`」判準。Reviewer 3 不改名，安全審查仍歸 `/plan-security`
- **plan-build / build-prompts 改為逐一具名 spawn** — 每個實作角色一次 Agent tool 呼叫並帶 `model: opus`（補上原本連模型行都沒有的前端與測試工程師）；各角色 prompt 的「自行掃描專案學風格」改為「只用探索官交接片段，不得再全域掃描」
- **feature-code-generator 責任邊界** — 維持 `model: opus`，補上「只在明確進入功能開發時使用、依已確認規格與探索官交接實作、最小必要變更、不重新無限制探索」
- **db-designer / backend-designer 維持 `model: opus`** — 補上理由註記，防後續維護者因「只產文件」誤降為 Sonnet
- **plan-common.md** — 既有 model 參數 gotcha 加指標到 `model-policy.md`（不複製政策內容）

## [bug-workflow@3.13.0] - 2026-07-27

> 與 feature-workflow@4.26.0 同批模型分工政策。bug-investigate 全程唯讀 Sonnet、bug-fix 的正式修改交給 Opus 實作者；鐵律、最小 diff 與驗證流程不變。

### 新增
- **共用 reference `model-policy.md`（權威版）** — 內容同 feature 側；共用白名單登記（`check-shared-refs.py`、`sync-shared-refs.sh`、CONTRIBUTING.md）5→6 檔
- **bug-investigate 條件式 Opus 升級（4.5）** — 3-Strike 選項從「繼續／暫停」擴充為「繼續（Sonnet）／升級深度推理（Opus）／暫停」；升級需符合六條件之一（連三假說被否定、跨三模組以上、複雜並行／交易一致性／記憶體／分散式、證據互相矛盾、Sonnet 無法收斂、使用者明確要求），且必須先產出「深度調查交接」，Opus 只回答尚未解答的問題

### 改善
- **bug-investigate Phase 1–2 派唯讀 subagent（`model: sonnet`）** — 加硬性規則：不改正式程式碼、無根因不得進修正、不得因首次假說失敗就升級 Opus、不自動啟 Dynamic Workflow、不依賴 `/effort ultracode`
- **bug-fix 模型分工** — 4a 定位／相似修正搜尋／測試範本（`model: sonnet`）與 4b 正式修改／迴歸測試（`model: opus`）明確拆成兩個 agent（同一 agent 無法中途換模型）；`--verify-only` 不改程式碼故預設 Sonnet，僅在驗證失敗且使用者同意時才啟 Opus 實作者
- **boundaries.md** — bug-investigate／bug-fix 的 🟢🟡🔴 條目補上模型規定（禁止 Sonnet 直接改正式程式碼、禁止 Opus 重做探索、禁止只在 prompt 寫模型）

### 修正
- **`scripts/lint-agent-model.py` 由 advisory 轉 strict 並擴充為 7 條規則** — 結構化 model 標示（含 JSON 形式 `{"model": "opus"}`）、`agents/*.md` frontmatter 政策（規格分析不得 Opus／正式實作不得 Sonnet）、各 skill 角色對照（plan-spec 只准 Sonnet、bug-investigate 的 Opus 只能在升級段、bug-fix 需有 Opus 實作者、`plan-review --quick` 需 Sonnet）、禁止自然語言指定模型、禁止「視情況使用模型」含糊措辭；掃描範圍從 SKILL.md 擴大到 `references/` 與 `agents/`；CI job 改名 `agent-model` 並以 `--strict` 執行（違規阻擋）
- **`docs/prerequisites.md`** — 「Agent Teams 環境變數」段新增 `CLAUDE_CODE_SUBAGENT_MODEL` 防護說明（設 sonnet／opus 會覆寫所有 agent 的模型選擇，需混用請移除或設 `inherit`）

## [feature-workflow@4.25.0] - 2026-07-24

> handoff.md 斷點保險——長任務進度即寫，任何時點中斷（crash、關機、隔天重開）都能被新 session 精確接手。

### 新增
- **共用 reference `handoff-discipline.md`** — 進度即寫紀律（每完成一個工作單元立即更新 `.spec/{slug}/handoff.md`，不做 ctx 偵測、不對抗 auto-compact）、六段交接模板（目標、歧義點置頂、已完成附證據、進行中/未完成、接手前要準備、決策紀錄）、各 skill 工作單元定義
- **四個長任務 skill 掛紀律** — plan-build（Agent Teams leader 負責寫入）、plan-review、plan-security、plan-verify 護欄行引用 handoff-discipline
- **plan-next 升級為接手入口** — 掃描表納入 handoff.md、新增「讀取 handoff.md」節產生接手簡報＋新鮮度交叉驗證（handoff 宣稱與檔案實況不一致時以實況為準並標注過期）；Gotchas 加 handoff 例外（bug 型輕量目錄無 README 也能接手）
- **plan-close 生命週期** — handoff.md 排除於 Notion 同步（plan-common 對應表明列）、結案時於 git add 前刪除

## [bug-workflow@3.12.0] - 2026-07-24

> 與 feature-workflow@4.25.0 同批 handoff.md 斷點保險。

### 新增
- **共用 reference `handoff-discipline.md`（權威版）** — 內容同 feature 側；bug 型任務無 `.spec/` 目錄時建輕量目錄只放 handoff.md（slug 沿用 Git branch 名去前綴）
- **bug-investigate / bug-fix 掛紀律** — 護欄行引用 handoff-discipline（工作單元：一個假說的驗證結果／一個修復步驟）
- **bug-close 清理** — 結案時刪除 handoff.md（連同空目錄）
- **共用白名單登記** — check-shared-refs.py、sync-shared-refs.sh、CONTRIBUTING.md 清單納入 handoff-discipline.md（4→5 檔）

## [feature-workflow@4.24.4] - 2026-07-14

> reconciliation Token 下放（補齊）——處理稽核報告 token 維度剩餘 3 條 feature 側發現。

### 改善
- **plan-verify 瘦身** — 移除與 `examples/verify-report-sample.md` 重複的 inline 驗證報告範例，改為保留引用（555→489 行，降至官方建議 500 行內）
- **plan-build 去重** — 步驟 10「回傳結果」原有「含測試/跳過測試」兩份近乎重複模板，合併為一份、測試差異行內標示（364→335 行）
- **plan-browse 讀取優化** — 模式 1 總覽階段改只讀 README frontmatter/首段摘要，不再逐一讀取全部設計文件全文（任務多時省 token），全文延到深度閱讀
- 語意零損失（fresh agent read-back 逐條驗證、引用 0 斷鏈、本地 CI 全綠）

## [feature-workflow@4.24.3] - 2026-07-14

> reconciliation Token 下放——長內容搬 references/ 降 skill 觸發載入成本。

### 改善
- **SKILL.md 大幅瘦身** — plan-browse 六模式 ASCII 範本（314→121）、plan-review 派工 prompt（292→231）、plan-build deploy SQL 表/模板（408→364）、plan-explore 情境範例下放到 references/；plan-setup 欄位表/建庫步驟引用 db-templates 去重；plan-sync 對照表精簡；plan-verify 報告 Gotchas 移 phases/word-report、補範例引用
- **新增 references**：browse-examples / deploy-sql-guide / explore-examples / review-prompts
- 語意零損失（fresh agent git diff 逐項比對）；skill 觸發時只讀精簡後 SKILL，範本按需載入

## [bug-workflow@3.11.4] - 2026-07-14

> reconciliation Token 下放（補齊）——處理稽核報告 token 維度剩餘 project-add 發現。

### 改善
- **project-add 去重** — 「專案類型判斷」表原與 `references/project-page-templates.md` 雙源重複易漂移，改為引用單一權威來源（較詳細的判定條件先合併進權威源，不遺失細節）（423→410 行）
- 語意零損失（fresh agent read-back 逐條驗證、引用 0 斷鏈、本地 CI 全綠）

## [bug-workflow@3.11.3] - 2026-07-14

> 與 feature-workflow@4.24.3 同批 Token 下放。

### 改善
- **SKILL.md 瘦身** — bug-close Merge 引導（308→259）、bug-start Feature 關聯+分支偵測（380→257）、project-add Git Flow 偵測（488→423）下放到 references/；bug-setup 欄位表引用 db-templates 去重；bug-fix Gotchas 除重複；bug-update 補範例引用
- **新增 references**：merge-guide / feature-linking / git-flow-detection
- 語意零損失（fresh agent git diff 逐項比對）

## [feature-workflow@4.24.2] - 2026-07-13

> reconciliation 一致性補全 + 文件套件名修正。

### 修復
- **文件套件名漏網** — feature README 與 `docs/prerequisites.md` 的 Playwright MCP 安裝指令由不存在的 `@anthropic-ai/mcp-server-playwright` 改為 `@playwright/mcp`（Microsoft 維護）；補上 4.24.0 只修 SKILL.md 的漏網（同事照 README 安裝會失敗）

### 改善
- **範例全量中性化** — 移除殘留客戶專案名改中性假例，涵蓋 SKILL.md/references/README/examples，全 repo 0 殘留
- **argument-hint** — plan-next、plan-start 補上
- **文字/引用一致** — plan-browse 註解涵蓋 .sql、深度閱讀範本補 verify/review/deploy、「規格確認迴圈」正名；plan-build 移除時效性版本指涉；plan-demo 移除前瞻死引用；plan-security 移除過時待辦
- **一致性小修** — plan-db 路徑寫全、plan-spec type=bug 導向、plan-stack 回傳顯示實際解析路徑、plan-setup MCP 已裝跳過

## [feature-workflow@4.24.1] - 2026-07-13

> reconciliation 稽核收尾——正確性類修復（死引用、內部矛盾、錯誤引用、不實宣稱）。

### 修復
- **死引用/缺檔** — plan-close 經 prerequisites 指向的 `notion-backend.md` 在 feature 側不存在，補上並納入共用同步清單；plan-next 移除不存在的 `/plan-start --resume` 推薦；plan-verify 修正懸空引用與未定義的 `$CDP`
- **內部矛盾** — crew-init 前置項數、plan-close API 次數（3-5 vs 7）、plan-demo `--keep`、plan-stack ID 覆蓋規則、plan-review prod_branch 回退各自統一
- **錯誤引用** — plan-review 報告模板 Reviewer 由 security 更正為 performance；plan-setup Agent 名補 `feature-` 前綴（feature-spec-analyst 等）
- **不實宣稱** — plan-demo 不再宣稱 plan-status 會標 `[DEMO]`（實際無此邏輯）
- **與 C9 對齊** — plan-deploy-confirm/plan-status 對齊 plan-close 改用 `git add -f`、由 plan-close 建部署狀態區塊的新做法
- **plan-verify Excel 報告** — `npx --yes exceljs`（無 bin，無法執行）改為可執行方式

### 工程（marketplace 層級）
- 共用 reference 同步清單由 3 個增為 4 個（納入 `notion-backend.md`），防兩份漂移

## [feature-workflow@4.24.0] - 2026-07-13

> 全面 SKILL.md 品質優化（29 個 skill 稽核，181 條已驗證發現，四梯次修復）。詳見 marketplace 內 `plugins/.skill-audit-2026-07-12/` 稽核報告。

### 修復
- **plan-verify MCP 設定錯誤** — 安裝套件由不存在的 `@anthropic-ai/mcp-server-playwright`（npm 404）改為 `@playwright/mcp`（Microsoft 維護）；MCP 模式主流程工具名統一為 Playwright `browser_*`，chrome-devtools 工具名只保留在 `--deep` 段
- **plan-deploy-confirm 部署回報機制失效** — Notion 搜尋原以「狀態為『已結案』」過濾，但 Notion 狀態欄位無此值（合法值僅 未開始/進行中/測試中/已完成），搜尋永遠回空；改以「🚀 部署狀態含待執行」為主判準。plan-close 明文建立「🚀 部署狀態」區塊使契約成立
- **plan-close 結案流程** — `.spec/` 提交改用 `git add -f`（原 `!.spec/{slug}/` 反向忽略無效）；README `status: 已結案` 寫回，對齊 plan-deploy-confirm 本地掃描
- **plan-next 結案偵測** — 改讀 `_index.md`「已完成」區段（原 `status: closed` 全 plugin 無此值、永不命中）
- **plan-security L1-SQL-1** — grep pattern 改字面比對（原 `\$\{` 寫法實測匹配不到 MyBatis `${}`）
- **plan-sync** — 修正對 plan-start 的步驟編號指涉腐化

### 改善
- **新增 `docs/SKILL-TEMPLATE.md`** — 統一段落順序、前置檢查句式、步驟編號規則與觸發詞格式，作為未來新 skill 撰寫依據
- **references 路徑統一** — 19 個 skill 內文引用改為可正確解析的相對路徑寫法（原從 skill 目錄解析不到 plugin 根層 references/）
- **觸發詞收斂** — description 移除單字級英文詞與日常口語（避免與內建工具及日常對話誤觸發），每個 skill 第一觸發固定為斜線指令；19 個 skill 全數新增「何時不用」反向指引段，並標注與內部/環境 skill 的分工邊界
- **步驟編號整數連續化、跨檔指涉改用段落名稱**（抗編號腐化）
- **跨 skill 重複內容抽共用** — 「本地檔案↔Notion 區塊對應表」「MCP 安裝指令」等抽到 references/ 單一來源
- **獨立 marketplace.json 修正** — 補齊過期的 skills 清單（plan-security/plan-verify/plan-next/plan-demo/plan-deploy-confirm）與版本號

## [bug-workflow@3.11.2] - 2026-07-13

> 與 feature-workflow@4.24.2 同批一致性補全。

### 改善
- **範例全量中性化** — 客戶專案名改中性假例（bug-setup/bug-start/bug-close/bug-update/project-add）
- **argument-hint** — bug-start 補上
- **去重與一致** — bug-close merge 衝突 Gotchas/邊界情況去重、bug-update 範例去重、crew-init 三處去重、crew-doctor 退出碼段改健診狀態

## [bug-workflow@3.11.1] - 2026-07-13

> 與 feature-workflow@4.24.1 同批 reconciliation 正確性修復。

### 修復
- **內部矛盾** — crew-init 前置檢查項數（3/5/8）統一；crew-doctor 進階檢查前置條件統一
- **crew-upgrade** — 目錄不存在時早退出（不再對死路徑 grep）；補版本比較指令（`sort -V`）
- **bug-setup** — 專案資料庫 Title 欄由「專案名稱」對齊 db-templates 的「Name」
- **project-add** — 移除硬寫的單一 Notion 後端安裝，改依 `NOTION_BACKEND` 偵測；情境 A 補缺值設定指引
- **#17 rtk** — 經確認環境無 rtk，bug-investigate/anti-rationalizations/bug-patterns 的 `rtk proxy` 全改為 Read tool 讀 log

## [bug-workflow@3.11.0] - 2026-07-13

> 與 feature-workflow@4.24.0 同批 SKILL.md 品質優化。

### 修復
- **crew-doctor MCP 套件名** — 由不存在的 `@anthropic-ai/mcp-server-playwright` 改為 `@playwright/mcp`
- **bug-setup 死引用** — 完成訊息指向不存在的 `/bug-search`，改為 `/bug-investigate`
- **crew-upgrade 路徑斷言** — marketplace 原始碼與 installed_plugins.json 路徑更正為 `~/.claude/plugins/` 為主、`~/.claude-company/` 降為 fallback（原主路徑不存在，版本比對必失敗）

### 改善
- **references 路徑統一、步驟編號整數化、前置檢查句式收斂**（同 feature 批次規範）
- **觸發詞收斂 + 10 個 skill 新增「何時不用」段**
- **補齊 references 專用段** — anti-rationalizations.md / boundaries.md 補上 crew-init、crew-doctor 等被引用卻不存在的段落
- **跨 skill 重複抽共用** — 刪除 5 個 skill 與 prerequisites.md 冗餘的「設定檔」區塊；「定位目標 Bug」「證據收集流程」抽到 references/ 單一來源；紀律護欄樣板壓成單行引用
- **獨立 marketplace.json 修正** — 補齊 crew-doctor/crew-init 並將版本自 3.8.0 對齊到 3.11.0

## [feature-workflow@4.23.0] - 2026-05-28

### 新增
- **verify-docx-cli .NET 子專案** — plugin 內建 multi-target（net8.0;net10.0）.NET CLI 於 `references/dotnet/verify-docx-cli/`，將 verify.md 七段式（封面/簽核/環境/摘要/明細/待處理/附錄）渲染為品牌 Word 驗收報告；支援 intumit / tech-dark / swiss 三套 brand style、TOC field + UpdateFieldsOnOpen、Logo 三層偵測（`--logo` > `~/.claude/feature-workflow/assets/` > plugin 內建）、Cookie/Authorization/API key 自動遮蔽、長回應截斷（>20 行切首尾 10 + 引用 evidence）、OpenXmlValidator 結構驗證 gate；透過 ProjectReference 共用 minimax-docx Core 的 OpenXML helper（`MinimaxCorePath` env var override + `$HOME` fallback）

### 改善
- **plan-verify Step 10 整合 verify-docx-cli** — `phases/word-report.md` 新增 step 10.0c 環境偵測（dotnet ≥8 + minimax-skills Core 偵測，缺 Core 時 AskUserQuestion 分流安裝/設 env/改 python-docx/跳過）；step 10.4a 從抽象「使用 /minimax-docx Skill」改為具體 `dotnet run --framework net8.0` 指令（搭配 `RollForward=LatestMajor`，於僅 net9/net10 runtime 機器也可 roll-forward 執行），含三層 Logo 偵測腳本與首次 build UX 提示；SKILL.md 引擎偵測摘要補上 MinimaxCorePath 與 Core 存在性檢查

### 工程（marketplace 層級）
- **統一過時 config 路徑** — 把新階層式 `~/.claude-company/feature-workflow/` 全面改為 `~/.claude/feature-workflow/`（config-resolver.md / config.template.md / prerequisites.md / plan-setup / plan-stack / plan-verify SKILL.md / word-report.md / 主 README.md）；config-resolver.md 加「從 ~/.claude-company 遷移到 ~/.claude」段（偵測舊路徑時提示手動 `mv`，不自動搬，避免破壞既有 setup）；plan-setup 移除「公司環境優先」分支改用「統一位置」邏輯；舊單一檔案 `~/.claude-company/feature-workflow-config.md` 與 `~/.claude-company/bug-workflow-config.md` 維持向下相容不動

## [feature-workflow@4.22.0] - 2026-05-23

### 新增
- **/plan-deploy-confirm SQL 執行回報（F1）** — 解決 deploy-checklist 機制「文件寫了沒人勾，Notion 永遠顯示『未執行』」的問題；由 DBA / 部署者逐 Step 確認執行狀態（✅/⚠️/❌/⏭️）、收集環境/執行者/備註，寫回 Notion「🚀 部署狀態」區塊；支援 --all-done 批次、--env 預設、--list 列待回報

### 改善
- **plan-verify 主檔再瘦身（A4 進階）** — Step 5 逐條驗證（199 行）拆出到 phases/run-verification.md；主檔 746 → 560 行，原始 1094 → 560（總減幅 49%）

## [feature-workflow@4.21.1] - 2026-05-23

### 改善
- **紀律護欄段落加強動作詞** — 6 個 SKILL（plan-build/security/review/verify + bug-fix/bug-investigate）的「## 紀律護欄」段落從「通用紀律見」改為「**執行前必讀**」，加回原版「衝動句 + 停下查表」反合理化提示
- **plan-verify Step 10 加強** — Word 報告 dispatcher 明示「**執行前必讀全文** phases/word-report.md，不可只依摘要執行」，避免 AI 跳過詳細流程
- **discipline-preamble.md 開頭加強** — 加「執行任何步驟前必須先完整讀過本檔」警示與動作指令

> 為何升 patch：純文案加強動作詞，無功能變更；目的是抵消 D1 精簡化可能造成的「AI 不去讀 preamble」風險

## [feature-workflow@4.21.0] - 2026-05-23

### 新增
- **/plan-demo 純本地評估模式（E3）** — 給未設定 Notion 但想評估 CREW 的人 5 分鐘看到完整流程：產出 .spec/demo-{slug}/ 範例（spec/db/arch/files/verify），不啟 Agent Teams / Notion / DB MCP；內建「使用者管理 API」範例

### 工程（marketplace 層級）
- **C3 SKILL.md 內容契約 lint** — `scripts/lint-skill-contract.py` 檢查觸發詞段落 + 內部連結可達性，CI skill-contract job

## [feature-workflow@4.20.0] - 2026-05-23

### 新增
- **/plan-next 智慧推薦下一步（B1）** — 讀取 .spec/{slug}/ 既有檔案、Git branch、verify.md 狀態，按決策表推薦下個 plan-* 指令；含 --all 列出所有活躍任務

### 改善
- 主 README 進階文件區段加入 ADR 入口

## [feature-workflow@4.19.0] - 2026-05-23

### 新增
- **驗證記憶時效性檢查（F2）** — 每筆 Selector / 操作 recipe / 等待策略加 `last_verified` 欄位，三段門檻：≤30 天 🟢 直接用、31-90 天 🟡 標示需確認、>90 天 🔴 不採用重新探索

### 改善
- **plan-verify Step 2.5** — 載入記憶時加時效性檢查段落，明示過時記憶比沒記憶更糟
- **plan-verify Step 5.5** — 寫入記憶強制含 `last_verified`
- **plan-verify Step 9.5** — 升級時保留原始 `last_verified`，已刷新者帶今日
- **smartrobot-memory.md 範本** — Selector 表加「最後驗證」欄

### 工程（marketplace 層級）
- **D2 Agent model 參數 advisory lint** — 偵測 Agent 呼叫描述附近是否缺結構化 `model:` 標示
- **E1 README 拆解** — 根目錄 578 → 375 行，docs/{prerequisites,windows,dbhub,notion-schema}.md
- **C5 .gitignore** — 排除 `.claude/` / `.playwright-mcp/` / `task_plan.md` / `.spec/*/`，CONTRIBUTING 加規範
- **C4 CHANGELOG 順序 lint** — `scripts/lint-changelog.py` + CI job 防止再次錯亂

## [bug-workflow@3.10.1] - 2026-05-23

### 改善
- **紀律護欄段落加強動作詞**（同 feature-workflow@4.21.1 描述） — bug-fix / bug-investigate
- **discipline-preamble.md 開頭加強** — 兩 plugin 同步

## [bug-workflow@3.10.0] - 2026-05-23

### 新增
- **/crew-init 一鍵首次設定（B3）** — 統合 /bug-setup + /plan-setup + 提示 /init 與 /project-add，含偵測跳過邏輯與 --resume 中斷續跑

### 文件（marketplace 層級）
- **docs/adr/ 5 個關鍵架構決策（E2）** — 001 本地 spec / 002 leader-delegate / 003 Playwright 預設 / 004 共用 reference 重複 / 005 bug-investigate 主入口

## [feature-workflow@4.18.0] - 2026-05-22

### 新增
- **共用 reference 漂移檢查** — `scripts/check-shared-refs.py` 用 sha256 確保兩 plugin 共用檔案（prerequisites.md / db-templates.md / discipline-preamble.md）內容一致
- **discipline-preamble.md** — 集中反合理化、動作邊界、鐵律三大紀律的通用敘述
- **plan-verify phases/word-report.md** — Step 10 Word 報告產出獨立成檔（393 行）

### 改善
- **可獨立安裝** — 解除對 bug-workflow 的所有跨 plugin 引用，12 個 SKILL.md 與 plan-setup 改為自家路徑
- **紀律段落統一** — 6 個 SKILL（bug-fix/bug-investigate/plan-build/security/review/verify）紀律敘述統一指向 discipline-preamble，順帶解決原本「衝動句」「emoji」分散不一致
- **plan-verify 主檔瘦身** — 1094 → 723 行（-34%），符合 800 行 lint 警告線

### 工程
- **CI lint workflow** — 三條規則：版本一致性 / SKILL.md 格式 / 共用 reference 漂移
- **scripts/bump-version.sh** — 一次同步 plugin.json + marketplace.json + README 三處版本

## [bug-workflow@3.9.0] - 2026-05-22

### 新增
- **/crew-doctor** — 一次性健診 18 項依賴與設定，分紅黃綠選配四級顯示，含 --quick / --fix 模式

### 改善
- **discipline-preamble.md** — 集中紀律敘述，bug-fix/bug-investigate 紀律段落改為精簡指向
- **可獨立安裝** — feature-workflow 不再依賴本 plugin 的 references（雙方各自帶共用 reference 副本，CI 防漂移）

---

## [feature-workflow@4.17.0] - 2026-05-19

### 新增
- **Word 報告多風格系統** — plan-verify 產出 Word 驗收報告時可選擇三種風格：Intumit Brand（藍+橘企業風）、Tech Dark（深藍科技風）、Swiss Minimal（黑灰極簡無 Logo）
- **python-docx fallback 引擎** — .NET 未安裝時自動降級使用 python-docx 產出報告，品牌視覺與 minimax-docx 版一致（僅缺 TOC）
- **報告依賴前置檢查** — plan-verify 啟動時偵測 .NET / python-docx 可用性，提前告知使用者報告引擎狀態
- **verify-docx-generator.py** — 新增 Python 報告產出腳本，支援 `--style` 參數切換風格、`--logo` 嵌入公司 Logo

### 改善
- **報告不再提及 Playwright** — 瀏覽器欄位不再寫「Playwright 控制」，附錄移除「工具版本」區塊
- **封面資訊預設值** — 承辦單位預設「碩網資訊股份有限公司」，製作人預設取 OS 使用者名稱
- **風格選擇互動化** — 使用 AskUserQuestion 讓使用者點選風格，無需記參數

## [feature-workflow@4.16.0] - 2026-05-15

### 新增
- **截圖穩定化策略** — 從 SmartRobotE2ETest 萃取的 6 步穩定化流程（ESC×2 + networkidle + retry），所有專案受益
- **元素定位 Fallback** — 6 級定位策略（記憶 → 穩定 selector → 產品知識 → i18n 翻譯 → CSS → URL 導航）
- **WARN 狀態** — verify.md 新增 ⚠️ WARN 狀態（介於 PASS 和 FAIL 之間，環境差異/selector 不穩定）
- **Excel 驗收報告** — `--excel` 選項，ExcelJS 獨立腳本產出 .xlsx（總表 + 步驟 Sheet + 嵌入截圖）
- **i18n 驗證指引** — 支援 zh-TW/zh-CN/en-US/ja-JP 四語系，產品模式用翻譯文字定位、通用模式用穩定 selector
- **產品知識庫** — 新增 `products/` 目錄，SmartRobot 知識庫含頁面導航地圖、Selector、i18n 對照、特殊操作 Recipe
- **驗證記憶系統** — 三層架構（產品級→專案級→任務級），自動記錄 + 結案升級，驗證越做越快
- **E2E Runner 模式** — `--e2e` 選項，匹配現有 E2E 測試直接跑（需 e2e_repo 設定）
- **測試骨架產出** — 驗證完成後可選產出 80% 完成度的 E2E 測試骨架
- **plan-common 第 4 層** — 產品知識庫偵測邏輯，projects/{id}.md 新增 product_id 選填欄位

## [bug-workflow@3.8.0] - 2026-05-15

### 新增
- **investigate 為主入口** — 流程從「start → investigate」改為「investigate（自動建立條目 + 調查）」，bug-start 降為可選的手動入口
- **釐清問題機制** — 調查完成後，若根因涉及商業邏輯疑問或環境差異，條件觸發 1-3 個釐清問題請使用者回答
- **動態建議指令** — 調查回傳結果根據根因確認狀態（已確認/需更多資訊/未確認）動態建議後續指令

### 改善
- **README 流程圖** — 以 bug-investigate 為主入口，bug-start 改為虛線可選路徑
- **根目錄 README** — 同步更新 Phase 2 摘要流程、詳細流程圖、指令表
- **feature-workflow 交叉引用** — plan SKILL.md 和 team-composition.md 的 bug 流程描述同步更新
- **marketplace.json 版本同步** — 修正 bug-workflow 和根目錄 marketplace.json 的落後版本號，補齊遺漏的 skills 清單

## [feature-workflow@4.15.0] - 2026-05-06

### 新增
- **plan-start Notion relation** — Bug 類型本地關聯 Feature 成功後，同步建立 Notion「相關任務」relation
- **plan-start 盲搜 fallback** — 本地 .spec/ 無匹配 Feature 時，走 Notion 層標題比對（同 bug-start Step 6.7）
- **plan-start Feature Branch 偵測** — 關聯 Feature 後偵測開發分支作為修復分支
- **dev_branch 設定** — projects/ frontmatter 新增 dev_branch 欄位，供 bug-close merge 引導使用

## [bug-workflow@3.7.0] - 2026-05-06

### 新增
- **自動關聯來源 Feature** — bug-start 建立 Bug 後，自動從同專案 Feature 中比對標題，設定「相關任務」self-relation（Step 6.7）
- **偵測來源 Feature Branch** — 從關聯 Feature 取得開發分支作為 Bug 修復分支，支援 Git-flow 規範（Step 6.8）
- **bug-fix 分支檢查** — 修復前檢查是否在正確分支，不一致時提示切換（Step 1.5）
- **bug-fix merge 引導** — 修復完成後提示 merge 回 DEV 分支
- **bug-close merge 引導** — 結案前偵測 feature branch，引導 `merge --no-ff` 回 DEV 分支（Step 1.5）
- **bug-setup self-relation** — 首次設定時自動建立「相關任務」self-relation 欄位

### 改善
- **config.template** 欄位對照新增「相關任務」Relation (self) 說明
- **db-templates** 第二輪 Relation 新增步驟 6（self-relation）+ 任務追蹤工具 Schema 說明

## [feature-workflow@4.14.0] - 2026-05-04

### 新增
- **DB_REQUIRED=insert-only 支援** — plan-build 退出驗證（E7）自動從設計文件擷取 SQL，產出 deploy.sql（含執行順序、驗證 SQL、回滾 SQL）
- **deploy.sql 標準格式** — Step 註解、驗證 SQL、回滾 SQL 三段式結構，上線時不會遺漏
- **deploy.sql Notion 同步** — plan-sync / plan-close 自動將 deploy.sql 寫入「🗄️ 資料庫設計 → 部署 SQL」子區塊

### 改善
- **team-composition.md** 新增 Step 3.5 DB_REQUIRED 三值判斷（true / insert-only / false）
- **E7 分級** — DB_REQUIRED=true 時為 BLOCK，insert-only 時為 WARN

## [feature-workflow@4.13.0] - 2026-05-04

### 新增
- **plan-start 退出驗證（S1~S7）** — 建立 Notion 條目後，強制用 notion-fetch 讀回頁面驗證 7 項必填欄位（專案資料庫、修復分支、開發階段等），防止 auto mode 下遺漏欄位

### 改善
- **S1 條件式降級** — Notion API 不可用時 S1 降為 WARN，不阻擋 offline-first 流程
- **S3 刻意 friction** — 修復分支未建立時，即使 auto mode 也強制二次確認
- **驗證失敗自動修復** — Agent 自行補呼叫 notion-update-page，不要求使用者手動操作
- **步驟 6 重構為兩步法** — 頁面建立拆分為 Step A（properties）+ Step B（body），配合退出驗證降級邏輯

## [feature-workflow@4.12.0] - 2026-04-25

### 新增
- **notion-local 後端支援** — 共享 bug-workflow 的 Notion 後端偵測與映射機制，所有 Notion 操作自動適配

## [feature-workflow@4.11.2] - 2026-04-25

### 改善
- **README 新增前置條件段落** — 明確列出 Node.js、Notion Plugin、Agent Teams 三項必要依賴
- **Windows 完整支援** — README 加入 Windows 使用者引導連結

## [feature-workflow@4.11.1] - 2026-04-25

### 改善
- **API 測試紀錄（Evidence）** — Word 驗收報告新增「測試紀錄」段落，包含完整 API 請求指令與回應內容，證明測試確實執行
- **回應截斷顯示** — 回應超過 20 行時，報告顯示前 10 行 + 後 10 行 + 省略提示，完整回應另存 `evidence/` 目錄
- **後台頁面截圖** — 驗證計畫新增「截圖」欄，API 有對應後台頁面時自動截圖存證（AI 從 arch.md 推斷，使用者可覆寫）
- **敏感資訊遮蔽** — Word 報告中的 Cookie / Token 自動遮蔽（前 4 + **** + 後 4），evidence 原始檔保留完整值

## [feature-workflow@4.11.0] - 2026-04-25

### 新增
- **Word 驗收報告** — 驗證完成後可產出正式 Word 驗收報告（封面 + 簽核欄位 + 測試環境 + 驗收明細 + 待處理事項 + 附錄），使用 `/minimax-docx` 產出
- **人話操作敘述** — 驗證時同步記錄人話操作步驟（Playwright 操作 → 人話翻譯），寫入 verify.md 的 `<!-- human_steps -->` 註解
- **封面資訊快取** — `report-config.md` 跨專案快取承辦單位與製作人，首次詢問後自動存檔

### 改善
- **移除 PDF 報告選項** — 簡化為只產 Word（Y/n 詢問），需要 PDF 可從 Word 轉存
- **Playwright 改為預設驗證工具** — chrome-devtools 改為 `--deep` 模式除錯輔助
- **向下相容** — 舊版 verify.md 無 `human_steps` 時自動進入降級模式

## [feature-workflow@4.10.0] - 2026-04-25

### 新增
- **plan-security Skill** — 三層安全掃描（靜態規則 / 上下文感知 / 對抗性思維），含 OWASP Top 10、SQL Injection、XSS 掃描，支援 --quick 和 --fix 模式
- **反合理化表** — 通用 3 條 + plan-build 8 條 + plan-review 3 條 + plan-verify 5 條 + plan-security 4 條
- **三層邊界系統** — plan-build / plan-review / plan-verify / plan-security 的行為邊界定義
- **脈絡工程策略** — 四層脈絡分配（共用核心 / 角色定制 / 範本預篩選 / 交叉引用），改善 Agent Teams delegate 品質
- **智慧團隊組成** — 根據 TASK_TYPE（feature / adjustment / bugfix / refactor / performance）和 CHANGE_SCOPE 動態調整團隊規模
- **技術棧陷阱** — stacks/ 範本新增「陷阱」段落，記錄各技術棧常見錯誤

### 改善
- **plan-build** 新增退出驗證門檻（6 項檢查：Teammate 完成 + files.md + 檔案存在 + 編譯 + API 契約 + 驗收條件）
- **plan-build** 步驟重構，精簡 37%（prompt 模板和判斷邏輯抽到 references/）
- **plan-review** Reviewer 3 從「安全性與效能」拆分為純「效能審查」（安全移至 plan-security）
- **plan-spec** 判斷區塊擴充（新增 TASK_TYPE、CHANGE_SCOPE、NEW_API、EXISTING_API_CHANGE）
## [bug-workflow@3.6.0] - 2026-04-25

### 新增
- **notion-local 後端支援** — 新增 `references/notion-backend.md` 工具映射表，CREW 自動偵測 Notion Plugin 或 notion-local 並選擇對應工具，既有使用者不受影響
- **Notion 後端偵測邏輯** — `prerequisites.md` 新增第 0.5 項，所有需要 Notion 的 Skill 首次呼叫時自動偵測可用後端（優先 Notion Plugin）

### 改善
- **適用範圍表格重構** — 改為矩陣式，清楚標示每個 Skill 需要哪些前置檢查項目

## [bug-workflow@3.5.2] - 2026-04-25

### 改善
- **Node.js / Git 前置檢查** — setup 時自動偵測 Node.js 和 Git，未安裝時依作業系統顯示對應安裝指令（macOS / Windows / Linux）
- **Windows 完整支援** — prerequisites.md 新增 OS 偵測邏輯，所有安裝引導提供 Windows 對應指令
- **README 新增 Node.js 前置條件** — 明確標示 Node.js ≥ 18 為必要依賴，附各平台安裝方式

## [bug-workflow@3.5.1] - 2026-04-25

### 修正
- **crew-upgrade Skill 未被安裝** — plugin.json 在 3.5.0 版本的 cache 中缺少 crew-upgrade 條目，升版觸發重新安裝

## [bug-workflow@3.5.0] - 2026-04-25

### 新增
- **bug-investigate Skill** — 假說驅動的根因調查，五階段流程（證據收集 → 模式比對 → 假說驗證 → 根因確認 → 調查報告），含 3-Strike 升級規則、知識庫搜尋、本地學習搜尋
- **bug-fix Skill** — 修復紀律（鐵律：根因確認才能修）、修復建議、迴歸測試產出、gstack browse UI 驗證
- **Bug 模式表** — 7 種已知 bug 模式（NPE、SQL 異常、第三方 API、併發、設定、快取、前端 UI）
- **反合理化表** — 通用 3 條 + investigate 6 條 + fix 4 條 + close 3 條，防止 AI 偷工減料
- **三層邊界系統** — 每個 skill 的 ALWAYS / ASK FIRST / NEVER 行為定義
- **學習系統** — 跨 session 學習捕捉（JSONL 格式），bug-investigate 時自動搜尋歷史洞察

### 改善
- **bug-close** 新增退出驗證門檻（根因分析 + commit + 迴歸測試 + 驗證勾選）
- **bug-close** 新增學習捕捉步驟（自動判斷是否有可複用的洞察）
- **bug-start** 新增初始證據自動收集（最近 commit + 環境 + 知識庫 + 學習歷史）

