---
slug: crew-6-portable-plugin
name: CREW 6.0 Portable Plugin 與 Codex 相容
type: feature
verified_at_commit:
verified_at:
drift_policy: off
---

# CREW 6.0 Portable Plugin 與 Codex 相容

> 將 CREW 從 Claude Code 專用 Plugin 集合演進為可由 Claude Code 與 Codex 共用的 Portable AI SDLC Framework；先完成可安裝封裝，再逐步抽離 Host-specific orchestration。

## 目標與範圍        <!-- crew:goal owner=spec -->
- In Scope：保留現有 feature-workflow / bug-workflow，不重寫既有工作流。
- In Scope：新增 Agent Plugins portable manifest 與 Codex repo marketplace。
- In Scope：保留 Claude Code marketplace 與 .claude-plugin/plugin.json 相容。
- In Scope：建立 Host-neutral model profile / approval gate / orchestration 的後續遷移路線。
- In Scope：所有階段都必須可由後續 Agent 從 Git 狀態接手。
- Out of Scope（Phase 1）：不改 /plan-*、/bug-* 的實際執行語意。
- Out of Scope（Phase 1）：不建立 MCP Server、獨立後端 Runtime、Web UI。
- Out of Scope（Phase 1）：不嘗試讓 Codex 完整模擬 Claude Agent Teams。

## 驗收條件          <!-- crew:ac   owner=spec -->
- [x] AC-11 Phase 2 建立共用 host-capabilities.md，核心 workflow 不直接依賴 Agent tool / Agent Teams / claude mcp list。
- [x] AC-12 project_instructions 同時接受 AGENTS.md 與 CLAUDE.md，Codex 不需建立 Claude 專屬檔案。
- [x] AC-13 新增 host-portability CI，active Skill/reference 重新引入 Host-specific orchestration 時阻擋 PR。
- [x] AC-14 Phase 2 完成後既有 CI 全綠，未破壞 state writer / skill contract / manifest / drift 檢查。
- [x] AC-15 Phase 3A 建立 NONE/FAST/STANDARD/DEEP model profile 與 deterministic router。
- [x] AC-16 Phase 3A 純探索/蒐證工作可路由 FAST；架構/DB/security 保持 DEEP。
- [x] AC-17 Phase 3B state.json 具 approval gates，未核准需求不得進 build。
- [x] AC-18 Phase 3B crew-state.py next/validate 能以 gate 決定是否 BLOCK，不靠 Skill 自律。
- [x] AC-19 Phase 3B Skills 只在使用者明確核准後呼叫 crew-state.py gate，不得由 Agent 自行 approve。
- [x] AC-20 `/plan` arch pass 提供明確人工確認迴圈，只有本輪確認後才寫 architecture=approved；架構修訂會讓舊 approval 失效。
- [x] AC-21 UAT gate 與 `/plan-close` 的語意先完成設計與 smoke test，再決定是否把 close transition 設為 hard block；不得直接沿用 verify=PASS 取代人工 UAT。
- [x] AC-22 已完成 close→UAT hard gate 相容性評估；決策為「此刻不全域啟用」，避免直接破壞 bug workflow。
- [x] AC-23 Bug workflow 建立合法的人類 UAT 寫入點：`/bug-close` 只能在使用者明確接受修復後寫 `uat=approved`；Agent 不得把 C1-C4 或測試結果自動等同 UAT。
- [x] AC-24 UAT gate prerequisite 改為 type-aware：feature 仍要求 review 完成；bug 不得被 feature 的 review prerequisite 卡死。
- [x] AC-25 Feature + Bug 都有合法 UAT 路徑後，再啟用 close→uat runtime hard block，並以 smoke test 驗證兩種 type 都能合法結案、未核准都會 BLOCK。
- [x] AC-26 Phase 1～3B 收斂盤點完成：確認 Phase 4 Runtime/MCP 目前沒有必要，先處理 repo-native 的 state/model/host-management 技術債。
- [x] AC-27 Bug state lifecycle contract 改為 type-aware：runtime 不再讓 `type=bug` 走 feature 的 spec/db/arch/build next 決策，並先以 deterministic smoke test 定義合法轉移。
- [x] AC-28 Bug skills 逐批接上 state lifecycle：`bug-start` init、`bug-investigate` 進度、`bug-fix` 修復/驗證、`bug-close` 結案；中斷後 `next/session-brief` 可正確續跑。
- [x] AC-29 剩餘 provider-specific model callsites（plan/plan-build/plan-review/bug-investigate/bug-fix）完成 profile routing 遷移，不再靠 legacy sonnet/opus 名稱。
- [x] AC-30 Host-management/setup portability 收斂：將設定路徑與 plugin CLI 類 advisory 分離成 portable config contract / host-specific 管理 adapter；核心 workflow 維持 hard=0。
- [x] AC-31 v1 legacy retirement 具明確移除條件與版本/日期，不在條件未滿足前刪相容層。
- [x] AC-1 repo 存在 .agents/plugins/marketplace.json，Codex 可把 mark22013333/crew 當 marketplace source；已以真實 Codex CLI 完成 marketplace add + 兩個 plugin install smoke。
- [x] AC-2 plugins/feature-workflow/plugin.json 符合 Agent Plugins portable manifest 最小格式。
- [x] AC-3 plugins/bug-workflow/plugin.json 符合 Agent Plugins portable manifest 最小格式。
- [x] AC-4 portable manifest version 與 Claude manifest、Claude marketplace、plugin README 版本一致。
- [x] AC-5 lint-plugin-manifest.py 同時驗證 Claude manifest、portable manifest 與兩份 marketplace source。
- [x] AC-6 bump-version.sh 可同步 portable manifest，避免日後版本漂移。
- [x] AC-7 README 明確區分 Claude Code 與 Codex 安裝方式，既有 Claude 安裝方式維持有效。
- [x] AC-8 Phase 1 不改既有 Skill 行為與 Agent model 選擇。
- [x] AC-9 Phase 1 變更可由既有 GitHub Actions lint 工作流驗證，不新增外部服務依賴。
- [x] AC-10 後續 Agent 只需讀本 plan.md 與 git diff/history 即可知道下一階段工作。

## 決策紀錄          <!-- crew:dec  append-only -->
- D-11 [phase2] Workflow 只依賴 Host Capability Contract；Claude/Codex 工具名稱是 adapter 實作，不是流程契約。
- D-12 [phase2] 無 subagent → inline、無 multi-agent → sequential、無 per-worker model → routing_degraded；不得假裝能力存在。
- D-13 [phase2] AGENTS.md 與 CLAUDE.md 都是 project_instructions；有衝突必須留下歧義，不自行忽略其中一份。
- D-14 [phase3] Model Profile 先抽象後調參；Phase 3A 只把機械型唯讀工作移到 FAST，高風險角色先維持既有 DEEP。
- D-15 [phase3b] Approval Gate 是 runtime hard rule：requirement 核准前禁止 DB/arch/build；architecture 核准前禁止 build。UAT 先進 schema 但本批不強制 close，待 UAT workflow 整合後再啟用。
- D-16 [phase3b] UAT 與 machine verify / code review 分離：verify=PASS 不等於 uat=approved；uat 只能在 review 完成後由人類決策。Phase 3B-3A 先讓 `next` 等待 UAT，但暫不 hard-block close transition。
- D-17 [phase3b] 暫不全域啟用 `close→uat` hard gate。原因：`/bug-close` 共用同一個 `crew-state.py close` transition，但 bug workflow 目前沒有 `review` step，也沒有合法的 UAT approve 路徑；直接啟用會讓所有 bug 結案被永久 BLOCK。
- D-18 [phase3b] close hard gate 的正確導入順序：先讓 UAT prerequisite type-aware → `/bug-close` 加人類 acceptance gate → 再把 `close` 加入 runtime transition gate。v1 feature 不受此變更影響，因 legacy-v1 相容模式本來就不呼叫 `crew-state.py`。
- D-19 [phase3b] UAT source prerequisite 採 type-aware：feature 必須 `review=done/skipped`；bug 不要求 feature review step，由 `/bug-close` 的本輪 explicit human acceptance 決定 UAT。這不是降低核准標準，而是對齊兩種 workflow lifecycle。
- D-20 [phase3b] `TRANSITION_GATES["close"] = ["uat"]` 正式啟用。`/plan-close` 與 `/bug-close` 每次執行都先 reset `uat=pending`，強制本輪重新取得 Human UAT，避免 stale approval；Feature 的 `/plan-next` 在 review 完成後指向 `/plan-close` 作為 UAT + 結案入口。
- D-21 [convergence] 暫不進 Phase 4 Runtime/MCP。現有 `crew-state.py` + model router + Approval Gate + Host Capability Contract 已能處理目前已知的 deterministic orchestration；尚無需要常駐服務、跨 session server 或 MCP runtime 才能解的實證痛點。
- D-22 [convergence] 最高優先技術債是 Bug state model：`crew-state.py` 的 `STEPS` / `compute_next` 仍是 feature lifecycle，`type=bug` 沒有獨立 next 規則；同時 `bug-start` / `bug-investigate` / `bug-fix` 幾乎沒有實際 state transition，與 `state-discipline.md` 的承諾不一致。
- D-23 [convergence] Host portability 核心已收斂：CI run #97 的 Host portability 為 hard=0；仍有 134 個 advisory / 31 個檔案，其中 82 個是 Claude config path、20 個是 Claude plugin CLI、32 個是 CLAUDE.md。這些主要集中 setup/admin/config，不應拿來當建立 Phase 4 server 的理由。
- D-24 [convergence] Active core Skills 的 provider-specific model callsite 已全部清除：`plan` / `plan-build` / `plan-review` / `bug-investigate` / `bug-fix` 一律使用 task + NONE/FAST/STANDARD/DEEP profile routing；實際 provider model 只存在 Host adapter mapping 層。
- D-25 [convergence] v1 相容層先保留。`legacy-v1.md` 已宣告「一個 minor 或 90 天」但沒有機器可判定的明確 retirement marker；先補明確移除條件，再刪 plan/status/next/build/close 等相容分支。
- D-26 [convergence] state schema 升到 v2 並採 type-aware steps：feature=`start/spec/db/arch/build/security/verify/review/close`；bug=`start/investigate/fix/close`。Bug 的編譯/測試/迴歸證據屬 fix work units，不為了對齊 Feature 而偽造 verify/review phase。
- D-27 [convergence] `crew-state.py next` 對 type=bug 獨立決策：investigate 未完成→`/bug-investigate`；fix 未完成→`/bug-fix`；fix 完成且 UAT pending→`/bug-close`；UAT rejected→回 `/bug-fix`；close 完成→結案。
- D-28 [convergence] schema v1 Bug state normalize 到 v2 時不搬運舊 Feature steps 當 Bug 進度；只保留同義的 start/close，新增 investigate/fix，並可由 `work_unit.skill` 修正 phase。
- D-29 [convergence] `/bug-start` 是 Bug runtime 的最小入口：建立 Notion Bug + `.spec/{slug}/state.json`，但不建立 `plan.md` 或新 Git branch。slug 沿用 `/plan-start` 的英文 kebab-case + collision suffix 規則；Notion 暫時失敗也不得讓 Bug lifecycle 沒有 state。
- D-30 [convergence] `/bug-investigate` 的 resumable work unit 定義為「一個可驗證根因假說」。進入調查即建立 0/1 work unit；每個假說落地後立即更新 done/total/evidence/remaining；只有根因正式確認、報告與必要釐清完成後才 clear unit + investigate=done。
- D-31 [convergence] `/bug-fix` 的 resumable work unit 固定為 3 段：①根因確認/修復範圍鎖定、②程式碼修改（verify-only 時為既有 diff/commit 確認）、③迴歸測試與驗證。每段完成即寫 state；新一輪 fix 開始時 reset UAT=pending，避免 UAT rejected/approved 的舊決策污染新修復版本。
- D-32 [convergence] `/bug-investigate` 已完全移除 provider-specific model callsite：Phase 1=`FAST/evidence_collection`、一般模式比對與 debugging=`STANDARD/debugging`、條件式深度根因=`DEEP/deep_investigation`；Skill 全檔禁止結構化 sonnet/opus/haiku 名稱，由 Router/Host adapter 決定實際 mapping。
- D-33 [convergence] `/bug-fix` 已完全移除 provider-specific model callsite：唯讀定位=`FAST/repository_search`、deterministic build/test=`NONE`、輸出整理=`FAST/test_output_summary`、所有正式程式碼與迴歸測試寫入=`DEEP/high_risk_implementation`；Skill 全檔禁止結構化 sonnet/opus/haiku 名稱。
- D-34 [convergence] `/plan-build` 已完全移除 provider-specific model callsite：Explorer=`FAST/repository_search`；DB/backend/API/frontend/test 等每個可寫角色各自帶 `DEEP/high_risk_implementation` + allowed scope。`parallel_delegate` 只負責排程，不可取代子工作單元各自的 routing contract。
- D-35 [convergence] `/plan-review` 已完全移除 provider-specific model callsite：邏輯/品質 reviewer 與 `--quick`=`STANDARD/routine_review`；效能 reviewer=`DEEP/performance_review`。`parallel_delegate` 只負責排程，每個 reviewer 仍各自帶 routing contract。
- D-36 [convergence] `/plan` 已完全移除 provider-specific model callsite：spec=`STANDARD/requirement_analysis`；DB=`DEEP/schema_design`（schema_migration + transaction sensitive）；arch=`DEEP/architecture`。Active Skill 不指定 sonnet/opus/haiku，Host-specific `agents/*.md` frontmatter 僅視為 adapter mapping。
- D-37 [convergence] Host portability advisory 不以「清到 0」為目標。CI #116 的 134 筆 advisory 分為三類：72 筆 CREW-owned config/project/stack/learnings 路徑，應抽成 portable config contract；30 筆 Claude plugin/marketplace/settings/rules 管理，應保留在 host-management adapter；32 筆 AGENTS.md/CLAUDE.md 專案指令別名/文件例子，由既有 `project_instructions` 契約涵蓋，不為消警告硬改。
- D-38 [convergence] Portable config contract 只抽象「CREW 自己擁有的資料」：feature config、projects、stacks、bug config、learnings。Claude 的 `settings.json`、plugin marketplace/install cache、`~/.claude/rules/*` 與 plugin CLI 不是 CREW config，不得塞進同一 resolver。
- D-39 [convergence] Host-management adapter 應負責 install/update/hook discovery/host-native rules 等產品管理行為；portable workflow 只要求語意能力（例如 config resolve、tool probe、project instructions），不得為了支援 Codex 把 Claude CLI 指令改寫成不存在的通用命令。
- D-40 [convergence] Portable config canonical root 採 `CREW_CONFIG_HOME` → `$XDG_CONFIG_HOME/crew` → `~/.config/crew`。`crew-config.py` 為純解析器：read 先 canonical 再 legacy fallback；write 永遠回 canonical portable path；不得在 resolve 時 mkdir/mv/write。
- D-41 [convergence] Config logical keys 固定為 `feature/config`、`feature/project`、`feature/stack`、`bug/config`、`bug/learning`。舊 feature 單一 `feature-workflow-config.md` 若作為 project/stack fallback，resolver 必須標 `representation=legacy_monolith`，caller 仍走舊 parser，不假裝它是獨立檔。
- D-42 [convergence] `crew-config.py` 與 `config-contract.md` 是兩 plugin 共用資產，納入 shared-ref/script sha256 防漂移；先建立 resolver contract，再逐支 consumer 接線，避免同批重寫 setup/admin。
- D-43 [convergence] `~/.claude-company` 已退役，不再屬 config compatibility surface。Portable resolver 的 Claude fallback 只接受 `~/.claude`；`.claude-company` 即使檔案存在也必須忽略，不讀、不遷移、不寫入。
- D-44 [convergence] `/bug-close` 是第一個 portable config consumer：`bug/learning --mode write` 只取得 canonical path，consumer 自行建立 parent directory 並 append JSONL；Skill 不再知道任何 Host-specific learnings 實體路徑。
- D-45 [convergence] `config-contract.md` 屬 portability/adapter contract，允許列出 legacy fallback，因此 Host portability lint 不把它的路徑列為 consumer advisory；真正 Skill/reference consumer 仍照常掃描。
- D-46 [convergence] Bug learning read 與 write 現在都只透過 `bug/learning` logical key：write 永遠 canonical portable path；read 先 portable canonical 再由 resolver 處理現役 Host fallback。`evidence-collection.md` / `learnings-schema.md` 不再知道任何 Host-specific learnings 實體路徑。
- D-47 [convergence] 跨 plugin `dev_branch` 讀取一律透過 `feature/project --mode read`：hierarchical representation 讀 project frontmatter；`legacy_monolith` 沿用舊表格 parser；missing/空白則降級為通用 merge 提示。Bug consumer 不再自行拼 feature-workflow 實體路徑。
- D-48 [convergence] `/plan-close` 的 Bug 類型額外設定已改用 `bug/config --mode read`；Skill 只讀 resolver 回傳 path，不再自行二選一 `.claude-company` / `~/.claude` bug config。
- D-49 [convergence] `/plan-start` 的 Bug 類型設定檢查也統一使用 `bug/config --mode read`；Feature workflow 的核心 intake/close consumer 不再知道 bug-workflow 的 Host-specific config 實體路徑。
- D-50 [convergence] 共用 `prerequisites.md` 的設定/專案 precheck 只依賴 logical keys：workflow setup 用 `bug/config` + `feature/config`，專案註冊用 `feature/project`；Host fallback 與 legacy_monolith representation 只由 resolver contract 解釋。
- D-51 [convergence] `config.template.md` 只描述 logical storage contract，不宣告 Host-specific 實體路徑：Bug template=`bug/config`；Feature template=`feature/config` + `{portable-config-root}/feature`，並標示 `feature/project` / `feature/stack` 邏輯結構。
- D-52 [convergence] `/plan-deploy-confirm` 讀取 Feature workflow Notion IDs 時只依賴 `feature/config --mode read` logical key；實體 path 與 legacy fallback 由 `crew-config.py` / `config-contract.md` 決定，Skill 不再宣告 `~/.claude/feature-workflow/config.md`。
- D-53 [convergence] `/plan-stack` 的自訂技術棧 storage 描述改以 `feature/stack --stack-id {id} --mode write` logical key 表達；canonical path 由 `crew-config.py` / `config-contract.md` 決定，不再把 `~/.claude/feature-workflow` 當預設實體設定目錄。
- D-54 [convergence] `references/config-resolver.md` 只負責 Feature config 的漸進式載入與 parser 語意；實體 root / fallback / read-write path 統一委派給 `crew-config.py` + `config-contract.md`，並以 `feature/config`、`feature/project`、`feature/stack` logical keys 表達。`feature/project` / `feature/stack` 的 `legacy_monolith` representation 仍沿用舊 parser，內建 stack 仍使用 `stacks/_builtin.md` bundle 語意。
- D-55 [convergence] `/bug-setup` 的設定生命週期改為 resolver-owned storage：既有設定只透過 `bug/config --mode read` 取得 read source；任何首次建立、重新設定或更新後的輸出一律透過 `bug/config --mode write` 寫 canonical portable path。Legacy fallback 僅可讀，不搬移、不覆寫。
- D-56 [convergence] `/project-add` 的 Workflow 主設定只透過 `bug/config` / `feature/config --mode read` 取得 Notion metadata；project mapping 的 canonical ownership 統一為 `feature/project --repo-id {repo-id}`。Read 依 `hierarchical` / `legacy_monolith` 選 parser，write 永遠建立或更新 canonical portable project file；legacy monolith 僅讀、不原地修改。
- D-57 [convergence] `/crew-init` 僅以 resolver read contract 判斷 setup / registration 狀態：階段 1=`bug/config`、階段 2=`feature/config`、階段 4=`feature/project --repo-id {repo-id}`；project registration 依 `hierarchical` / `legacy_monolith` representation 判斷。`crew-init` 不自行寫 config，所有建立／更新仍委派既有 setup/project Skill。
- D-58 [convergence] `crew-doctor` 對 CREW-owned config/project 只做 resolver read 診斷：#6=`bug/config`、#7=`feature/config`、#8=`feature/project --repo-id {repo-id}` + representation；`--fix` 不再自行 mkdir config storage，缺失時回到 `/bug-setup`、`/plan-setup`、`/project-add` 的 canonical writer。Host settings/rules 仍屬 host-management adapter，不混入 config resolver。
- D-59 [convergence] `/plan-setup` 主設定層改為 resolver-owned storage：既有 Feature config 由 `feature/config --mode read` 定位，主設定新建／重新設定一律寫 `feature/config --mode write` canonical path；Bug 共用 Notion metadata 由 `bug/config --mode read` 取得。`stacks/_builtin.md` / projects bundle 本批只維持既有相對建立語意，不新增 resolver key。
- D-60 [convergence] AC-30 closure criteria 以「CREW-owned config violation=0 + Host portability hard=0 + deterministic resolver smoke 全綠」為準，不要求 advisory=0。剩餘 `CLAUDE_PLUGIN_CLI` / `CLAUDE_CONFIG_PATH`（marketplace、plugin install、`settings.json`、Host rules）屬 host-management adapter；`CLAUDE_MD` 屬 `project_instructions` alias，不再視為 AC-30 未完成。
- D-61 [convergence] v1 retirement eligibility 固定為：起點 `feature-workflow@5.0.0 / 2026-07-28`；第一個 `5.1.0+` 發布或 `2026-10-26`（90 天）以先到者為 removal gate。Gate 未達前 `legacy-v1.md`、`plan-status --migrate`、crew-doctor v1 偵測必須存在；gate 達成只解除「不得刪」限制，不會自動 cleanup。
- D-62 [convergence] AC-1 的驗收證據必須是真實 Codex CLI，而非 manifest/lint 推論。Codex CLI 0.158.0 的安裝命令為 `codex plugin add PLUGIN@MARKETPLACE`；`codex plugin marketplace add` 成功解析 CREW repo marketplace 後，`bug-workflow@crew` 與 `feature-workflow@crew` 均實際安裝並由 `codex plugin list` 回報 installed, enabled。
- D-48 [convergence] `/plan-close` 的 Bug config read 已改為 `bug/config --mode read` logical key；Feature 結案照既有 feature 設定流程，Bug 類型額外讀 `bug/config`，但 Skill 不再知道 `bug-workflow-config.md` 的 Host 實體位置。
- D-1 [spec] 範圍判斷：TASK_TYPE=refactor、CHANGE_SCOPE=full、FRONTEND_REQUIRED=false（FRONTEND_TECH=無）、DB_REQUIRED=false（DB_TABLES=無）、NEW_API=false、EXISTING_API_CHANGE=false｜理由：本次為工具鏈與封裝層演進。
- D-2 [spec] 不另建 crew-codex repo｜理由：避免 Skill/reference/scripts 雙份維護與漂移｜否決：Claude/Codex 各一套 repo（維護成本過高）。
- D-3 [spec] 保留 feature-workflow / bug-workflow 兩個 plugin｜理由：目前 domain boundary 清楚｜否決：第一版合併成 crew-sdlc 超大 plugin（破壞性太高）。
- D-4 [spec] root plugin.json 為 portable canonical manifest，.claude-plugin/plugin.json 保留 Claude 專屬宣告｜理由：符合 Agent Plugins portable layout 且不破壞既有安裝。
- D-5 [spec] .agents/plugins/marketplace.json 為 Codex repo marketplace，.claude-plugin/marketplace.json 繼續服務 Claude Code｜理由：Host 可各自保留 presentation / policy。
- D-6 [spec] Phase 1 僅處理 packaging/discovery/CI，不抽 Agent Teams｜理由：先建立可驗證的小步遷移面。
- D-7 [spec] Phase 2 再抽 Host Capability Adapter｜目標：把 Agent tool、Agent Teams、TeamDelete、claude mcp、CLAUDE.md 等 Host-specific 指令從核心流程隔離。
- D-8 [spec] Phase 3 將 model-policy 從 Sonnet/Opus 升級為 NONE/FAST/STANDARD/DEEP profile，再由 Host adapter 對映實際模型。
- D-9 [spec] Phase 3 將 approval gate 升級為 crew-state.py 可強制的 transition rule，而非只靠 SKILL.md 自律。
- D-10 [spec] Phase 4 才評估 crew-runtime / MCP｜理由：沒有實際跨 Host orchestration 痛點前，不先增加常駐服務複雜度。

## 已知取捨與風險    <!-- crew:risk append-only -->
- Phase 1 只代表 Codex 能發現/安裝 plugin，不代表所有 Claude-specific Skill 都能原樣執行。
- 現有 SKILL.md 直接引用 Agent tool、Agent Teams、CLAUDE_PLUGIN_ROOT、CLAUDE.md、~/.claude/rules；Phase 2 必須逐支分類。
- Codex 與 Claude 對 subagent/model routing 能力不同，不能以文字假裝兩邊完全等價。
- hooks 可利用 Codex 對 CLAUDE_PLUGIN_ROOT 的相容變數，但長期仍應改用 Host-neutral path abstraction。
- marketplace authentication policy 目前先使用官方文件範例值；若之後 bundle MCP/auth，再依實際認證流程調整。
- 不為了 Artifact-driven 再拆出大量 YAML；維持 plan.md + state.json + deploy.sql 的 compact artifact 哲學。
- 本遷移 plan 尚在規劃/實作中且不以程式碼錨點追蹤，故暫設 drift_policy=off；完成 Host-neutral 遷移後再決定是否轉回 normal。
- Bug workflow 已完成 type-aware state lifecycle：`start → investigate → fix → close`；Bug 的測試/驗證屬 fix work units，不偽造 Feature 的 verify/review phase。
- Host portability advisory 數量不是 KPI：真正 host-native 的安裝/更新/規則路徑應明確標成 adapter，而不是為了數字歸零把產品差異藏起來。

## 指路              <!-- crew:map  append-only -->
- Claude marketplace：`.claude-plugin/marketplace.json`
- Feature Claude manifest：`plugins/feature-workflow/.claude-plugin/plugin.json`
- Bug Claude manifest：`plugins/bug-workflow/.claude-plugin/plugin.json`
- Manifest lint：`scripts/lint-plugin-manifest.py`
- 版本同步：`scripts/bump-version.sh`
- Model policy：`plugins/feature-workflow/references/model-policy.md`
- State runtime：`plugins/feature-workflow/scripts/crew-state.py`
- Phase 1 新增目標：`.agents/plugins/marketplace.json`、`plugins/*/plugin.json`

## 檢查報告摘要      <!-- crew:rep  append-only -->
- [2026-09-27] [plan] 已確認 OpenAI portable plugin 使用 root plugin.json，skills/ 固定路徑自動發現；repo marketplace 使用 .agents/plugins/marketplace.json。
- [2026-09-27] [plan] Codex CLI 支援 `codex plugin marketplace add owner/repo`；legacy .claude-plugin/marketplace.json 仍可相容，但本計畫仍建立正式 .agents marketplace。
- [2026-09-27] [plan] Phase 1 執行順序：portable manifests → Codex marketplace → lint/version sync → README → CI/差異檢查。

- [2026-09-27] [phase1] PR #17 已建立；GitHub Actions run 36297731183 的 10 個 lint job 全部 success。
- [2026-09-27] [phase1] Portable manifests、Codex marketplace、版本同步、manifest lint、README/CONTRIBUTING 已完成；未修改既有 Skill/Agent 執行語意。
- [2026-09-27] [next] 下一接續點：Phase 2 先盤點所有 SKILL.md 的 Host-specific 語句，分類為 core / claude-only / codex-adapter，再設計 Host Capability Contract；不要直接重寫全部 Skill。

- [2026-09-27] [phase2] Host Capability Contract、project_instructions、tool_probe、portable delegation 與 host-portability CI 已完成。
- [2026-09-27] [phase2] 最新 CI run 36298895563 success；Host portability / Agent model / Skill contract / state writer 等 11 個 job 全綠。
- [2026-09-27] [next] Phase 3A：建立 model-routing.json + crew-model-route.py，先把 repository search / evidence collection / log summary 路由 FAST。

- [2026-09-27] [phase3a-2a] `/plan-build` 探索官已改走 routing task=`repository_search` + `profile: FAST`；Claude adapter 由 Router 對映 haiku/low，Codex 對映 inherit/low reasoning。
- [2026-09-27] [phase3a-2a] Commit `5f5a4c8`；GitHub Actions run 36300651665 共 12 個 job 全部 success。
- [2026-09-27] [next] 下一小批只處理 `/bug-investigate` Phase 1 證據蒐集 → FAST；不要同批修改 `/bug-fix` 或 Approval Gate。

- [2026-09-27] [phase3a-2b] `/bug-investigate` Phase 1 證據蒐集已改走 routing task=`evidence_collection` + `profile: FAST`；Phase 2 一般模式比對仍維持 STANDARD，深度根因推理仍只在升級條件成立時進 DEEP。
- [2026-09-27] [phase3a-2b] Commit `415f7c0`；GitHub Actions run 36300764423 共 12 個 job 全部 success。
- [2026-09-27] [next] 下一小批只處理 `/bug-fix` 的唯讀定位／驗證整理 → FAST；正式修復實作者仍維持 DEEP，不碰 Approval Gate。

- [2026-09-27] [phase3a-2c] `/bug-fix` 4a 唯讀定位改走 `task: repository_search` + `profile: FAST`；編譯/測試執行視為 NONE，輸出整理用 `task: test_output_summary` + FAST；任何實際寫產品碼或迴歸測試碼仍維持 DEEP。
- [2026-09-27] [phase3a-2c] Commit `f329d11`；GitHub Actions run 36300907510 共 12 個 job 全部 success。
- [2026-09-27] [phase3a] AC-15/AC-16 完成。FAST 已接到 plan-build explorer、bug-investigate evidence collection、bug-fix read-only locating/verification summary；DB/architecture/security 與正式 write role 保持 DEEP。
- [2026-09-27] [next] 下一階段 Phase 3B：只先設計 state.json approval gate schema 與 crew-state.py transition contract；第一小批不要直接改所有 Skill。

- [2026-09-27] [phase3b-1] state.json 新增 requirement / architecture / uat gates；新任務預設 pending，舊任務若 spec/arch 已完成則 migration-approved，避免升級後卡死既有工作。
- [2026-09-27] [phase3b-1] crew-state.py 新增 `gate` 子命令；`set` 對 DB/arch/build 做 transition hard block；`next` 會停在人類核准點；`validate --require-gate` 可作 exit gate。
- [2026-09-27] [phase3b-1] Commit `42f70cb`；GitHub Actions run 36301348637 共 13 個 job 全部 success，含新的 Approval gates smoke test。
- [2026-09-27] [next] 下一小批只整合 `/plan` spec confirmation → requirement gate，以及 `/plan-build` 前置檢查 → requirement+architecture gate；不碰 UAT gate、不改 bug workflow。

- [2026-09-27] [phase3b-2a] `/plan` spec confirmation 已接 requirement gate：spec 修訂先 reset requirement=pending；只有使用者在本輪明確回覆 OK/確認後，才先寫 spec=done 再 gate requirement=approved，並以 validate --require-gate requirement 收尾。
- [2026-09-27] [phase3b-2a] `/plan-build` 前置條件新增 runtime validate requirement + architecture；任一 gate 未通過立即 BLOCK，且明文禁止 plan-build 自行 approve architecture。
- [2026-09-27] [phase3b-2a] Commit `8098ba9`；GitHub Actions run 36301550205 共 13 個 job 全部 success。
- [2026-09-27] [next] 下一小批只整合 `/plan` arch pass 的人工確認迴圈 → architecture gate；架構被修改時先 reset pending。完成後再評估 AC-19 是否可勾選；不碰 UAT、不碰 bug workflow。

- [2026-09-27] [phase3b-2b] `/plan` arch pass 已加入 architecture confirmation：實質架構修訂先 reset architecture=pending；只有使用者在本輪明確確認後，才先寫 arch=done，再 gate architecture=approved，最後 validate --require-gate architecture。
- [2026-09-27] [phase3b-2b] Approval Gate CI 現在只解析 bash code block 裡真正可執行的 approve 命令；active Skill 中只有 `/plan` 可以執行 approval，禁止說明文字不再造成假陽性。
- [2026-09-27] [phase3b-2b] Feature commit `4f1dadb`；lint 修正 commit `7c0948f`；GitHub Actions run 36302263923（#88）共 13 個 job 全部 success。
- [2026-09-27] [phase3b] AC-17～AC-20 完成：requirement + architecture 兩道人類 Gate 已由 runtime hard rule + Skill 明確確認迴圈共同執行。
- [2026-09-27] [next] 下一小批先只盤點 `/plan-close`、`/plan-verify` 與目前 UAT 語意，設計 UAT gate contract 與 smoke test；先不直接強制 close，避免把 verify=PASS 錯當成人工 UAT。

- [2026-09-27] [phase3b-3a] 新增 `feature-workflow/references/uat-gate.md`：Machine Verify、Code Review、Human UAT 三層語意分離，明訂 `verify=PASS` ≠ `uat=approved`。
- [2026-09-27] [phase3b-3a] `crew-state.py` 規定 uat gate 只有 `review=done/skipped` 後才能做非 pending 決策；review 完成但 UAT 未通過時，`/plan-next` 不再直接建議 `/plan-close`。
- [2026-09-27] [phase3b-3a] `/plan-verify` 明文禁止寫 `gates.uat`；`/plan-close` 加入 advisory UAT 檢查，但此批仍未把 close 放進 `TRANSITION_GATES`，保留 legacy compatibility。
- [2026-09-27] [phase3b-3a] Commit `6524013`；GitHub Actions run 36304354314（#90）共 13 個 job 全部 success，Approval gates smoke test 含 UAT timing / next / compatibility。
- [2026-09-27] [next] 下一小批只評估是否正式啟用 close→uat hard block：先盤點 `/plan-close` legacy/bug 相容性與 `/bug-close` 邊界，再決定；不要直接改 transition。

- [2026-09-27] [phase3b-3b-analysis] close hard gate 相容性盤點完成：v1 feature 不受影響（legacy mode 不呼叫 crew-state.py）；v2 feature 已有 review→UAT 路徑；bug workflow 會受全域 gate 直接破壞。
- [2026-09-27] [phase3b-3b-analysis] `/bug-close` 直接呼叫 `crew-state.py set --step close --status done`，但 bug workflow 沒有 `--step verify` / `--step review` transition；目前 `uat` 又要求 review done，因此 bug 無法合法 approve UAT。
- [2026-09-27] [phase3b-3b-analysis] 決策：暫不修改 `TRANSITION_GATES["close"]`。先完成 AC-23/AC-24，再於 AC-25 一次啟用 runtime hard block。
- [2026-09-27] [next] 下一小批只做 type-aware UAT prerequisite + `/bug-close` 明確人類 acceptance → `uat=approved`；仍先不 hard-block close。

- [2026-09-27] [phase3b-3c] `crew-state.py` 的 UAT prerequisite 已改為 type-aware：feature 仍要求 review done/skipped；type=bug 不再硬套 feature review step。
- [2026-09-27] [phase3b-3c] `/bug-close` 新增本輪 Human UAT acceptance：只有使用者明確「接受／OK／確認／可以」才能寫 uat=approved；提出修改則寫 rejected 並立即停止結案。
- [2026-09-27] [phase3b-3c] C1-C4、測試 PASS、迴歸測試、Notion 驗證 checkbox、目標狀態=已完成都明文不得自動等同 UAT approved；waive 也只能由使用者明確要求且必須留 reason。
- [2026-09-27] [phase3b-3c] Commit `02ac58b`；GitHub Actions run 36312991689（#93）共 13 個 job 全部 success。
- [2026-09-27] [next] 下一小批才正式啟用 `TRANSITION_GATES["close"] = ["uat"]`，並補 Feature + Bug 的 close hard-block smoke test；不再同批擴充其他 workflow。

- [2026-09-27] [phase3b-3d] Runtime 已正式加入 `TRANSITION_GATES["close"] = ["uat"]`；Feature / Bug 的 `close=done` 在 UAT pending/rejected 時一律 BLOCK，approved/waived 才能通過。
- [2026-09-27] [phase3b-3d] `/plan-close` 現在是 Feature Human UAT + 結案入口；`/plan-next` 在 review 完成後即使 UAT pending 也會指向 `/plan-close`，但 runtime 會在核准前硬擋真正的 close transition。
- [2026-09-27] [phase3b-3d] `/plan-close` 與 `/bug-close` 每次都先 reset uat=pending，再要求本輪使用者 acceptance，避免沿用前一次結案嘗試的 stale approval。
- [2026-09-27] [phase3b-3d] Feature commit `6186c67`；smoke-test 對齊 commit `00d2565`；GitHub Actions run 36317931121（#96）共 13 個 job 全部 success。
- [2026-09-27] [phase3b] AC-17～AC-25 全部完成：requirement / architecture / UAT 三道人類決策 Gate 已由 runtime hard rule 強制。
- [2026-09-27] [next] Phase 3B 已完成。下一小批不要直接做 Phase 4 Runtime/MCP；先做一次「Phase 1～3B 收斂盤點」：找出仍殘留的 Host-specific / legacy / state lifecycle 缺口，判斷哪些值得進 Phase 4，哪些應留給後續版本。AC-1 的 Codex CLI 實機 smoke 仍保持未勾選，沒有實際 CLI 就不得宣稱完成。

- [2026-09-27] [convergence-1] Phase 1～3B 收斂盤點完成。Host portability CI #97：hard=0、advisory=134（31 files）；advisory 分布為 CLAUDE_CONFIG_PATH=82、CLAUDE_PLUGIN_CLI=20、CLAUDE_MD=32，主要集中 setup/admin/config 面。
- [2026-09-27] [convergence-1] 發現最高優先 correctness gap：`crew-state.py compute_next` 沒有依 type 分流，`type=bug` 仍會依 spec→db→arch→build 的 Feature 流程判位；而 bug-start/investigate/fix 並未真正寫入對應 state lifecycle。
- [2026-09-27] [convergence-1] Provider-neutral routing 尚未完全收尾：model lint 仍刻意允許 plan / plan-build / plan-review / bug-investigate / bug-fix 的 legacy sonnet/opus callsites。
- [2026-09-27] [convergence-1] 決策：Phase 4 Runtime/MCP 延後。現階段缺口可由 repo-native deterministic runtime + Skill contract 修正，新增 server 只會把未收斂的 lifecycle 再包一層。
- [2026-09-27] [next] 下一小批只設計並實作 **Bug type-aware state lifecycle contract + smoke test**：先讓 runtime 的 `next/phase/steps` 對 bug 有正確語意；不要同批修改所有 bug skills。完成後再逐支把 bug-start/investigate/fix 接上。
- [2026-09-27] [note] AC-1 仍未完成：尚未在有 Codex CLI 的環境實際執行 marketplace add/install smoke test，不得以結構驗證或 CI 取代。

- [2026-09-27] [convergence-2] `crew-state.py` 升至 schema v2，Feature/Bug steps 與 phase 改為 type-aware；CLI 會拒絕跨 type step/phase。
- [2026-09-27] [convergence-2] Bug runtime lifecycle 定為 `start → investigate → fix → close`；`next` 不再回 Feature 指令，UAT rejected 會回 `/bug-fix`。
- [2026-09-27] [convergence-2] 新增 `scripts/lint-state-lifecycle.py` 與 CI `State lifecycle` job，驗證 Feature/Bug 隔離、Bug transition、UAT close gate、schema v1→v2 normalization。
- [2026-09-27] [convergence-2] Commit `922d873`；GitHub Actions run 36320796124（#99）共 14 個 job 全部 success。
- [2026-09-27] [next] AC-28 採逐支接線。下一小批只處理 `/bug-start`：建立/定位 slug 後呼叫 `crew-state.py init --type bug`，補最小 Skill contract/CI；不要同批修改 bug-investigate 或 bug-fix。

- [2026-09-27] [convergence-3] `/bug-start` 已接 `crew-state.py init --type bug`：建立最小 `.spec/{slug}/state.json`，不建立 plan.md、不建立新 branch；branch/commit/page-id 有資料才寫入。
- [2026-09-27] [convergence-3] slug 規則與 `/plan-start` 對齊：問題簡述→英文 kebab-case，同名 `.spec` 加數字後綴；state collision 禁止使用 `init --force`。
- [2026-09-27] [convergence-3] Notion API 暫時失敗時仍建立本地 Bug state（page id 留空），避免 intake 成功但 runtime 無斷點。
- [2026-09-27] [convergence-3] Commit `fb26755`；GitHub Actions run 36323564244（#101）共 14 個 job 全部 success。
- [2026-09-27] [next] AC-28 繼續逐支接線。下一小批只處理 `/bug-investigate`：進入時寫 investigate=in_progress／work_unit，根因調查正式完成時寫 investigate=done；中斷時 next 應回 `/bug-investigate --resume`。不要同批修改 `/bug-fix`。

- [2026-09-27] [convergence-4] `/bug-investigate` 已接 runtime：定位 Notion Bug 後以 `state.notion.page_id` 綁定既有 slug；找不到/多筆都 BLOCK，不自行建立第二份 state。
- [2026-09-27] [convergence-4] 正常進入調查先寫 `investigate=in_progress`，再建立 `work_unit(skill=bug-investigate, done=0, total=1)`；每個假說結果落地即更新 progress/evidence/remaining。
- [2026-09-27] [convergence-4] 中斷時 `next` 會回 `/bug-investigate --resume`；`--resume` 不重設 done/total，直接依 state + Notion 從斷點續跑。3-Strike 暫停也保留未完成 work_unit。
- [2026-09-27] [convergence-4] 只有根因正式確認、調查報告完成且必要釐清已解決後，才 `unit --clear` + `investigate=done`；exit gate 要求 next=`/bug-fix`。
- [2026-09-27] [convergence-4] Commit `7bf0d33`；GitHub Actions run 36324177901（#103）共 14 個 job 全部 success。
- [2026-09-27] [next] AC-28 下一小批只處理 `/bug-fix`：進入時 fix=in_progress + work_unit；正式修改/測試/驗證依工作單元即時寫 state；修復與迴歸驗證完成才 fix=done，next 應進 `/bug-close`。不要同批做 model-routing AC-29。

- [2026-09-27] [convergence-5] `/bug-fix` 已接 runtime：定位既有 Bug state 後，正常開始會 reset uat=pending、寫 fix=in_progress，建立 3 個 resumable work units。
- [2026-09-27] [convergence-5] fix work units 固定為：1/3 根因確認與範圍鎖定、2/3 程式碼修改（verify-only 可記既有 diff/commit 已確認）、3/3 迴歸測試與驗證；每段落地即寫 state。
- [2026-09-27] [convergence-5] 只有 3/3 完成且驗證證據已寫 Notion 後，才 unit --clear + fix=done；exit gate 要求 UAT=pending、next=/bug-close。UAT rejected 後重新進 fix 也會先 reset pending，避免舊決策卡住新版本。
- [2026-09-27] [convergence-5] Commit `ec0740c`；GitHub Actions run 36328195823（#105）共 14 個 job 全部 success。
- [2026-09-27] [convergence] AC-27/AC-28 完成：Bug runtime 與 Skills 已從文件承諾變成真正可恢復的 `start → investigate → fix → close` lifecycle。
- [2026-09-27] [next] 下一小批開始 AC-29，但仍採逐支收斂：先盤點 `bug-investigate` / `bug-fix` 尚存的直接 sonnet/opus callsite，將其中最安全的一支改為 profile routing；不要同批碰 plan/plan-review。

- [2026-09-27] [convergence-6] `/bug-investigate` 的 legacy model callsite 已收斂：Phase 2 模式比對與一般假說推理改為 `task=debugging + profile=STANDARD`；3-Strike 深度升級改為 `task=deep_investigation + profile=DEEP`。
- [2026-09-27] [convergence-6] 深度調查派工改走 `crew-model-route.py` + `delegate_readonly` 結構化 routing；Host 無 per-worker routing 時只能回報 `routing_degraded=true`，不得假裝已套用特定 provider model。
- [2026-09-27] [convergence-6] `lint-agent-model.py` 現在要求 bug-investigate 同時具 FAST/STANDARD/DEEP，並禁止結構化 sonnet/opus/haiku；防止未來退回 provider-specific callsite。
- [2026-09-27] [convergence-6] Commit `99ef528`；GitHub Actions run 36330914393（#107）共 14 個 job 全部 success。
- [2026-09-27] [next] AC-29 下一小批只處理 `/bug-fix`：把正式實作者與迴歸測試寫入角色從 legacy `model: opus` 改成 `task=high_risk_implementation + profile=DEEP`；保留 FAST/NONE 現有分工，不碰 plan/plan-review。

- [2026-09-27] [convergence-7] `/bug-fix` 正式寫入角色已從 legacy `model: opus` 改為 `task=high_risk_implementation + profile=DEEP + risk=high + complexity=high`；執行前由 `crew-model-route.py` 取得 Host mapping。
- [2026-09-27] [convergence-7] 新增/修改迴歸測試程式碼與 verify-only 失敗後轉寫入，都沿用同一個 high_risk_implementation + DEEP 路徑；FAST 唯讀定位、NONE deterministic test、FAST output summary 不變。
- [2026-09-27] [convergence-7] `lint-agent-model.py` 現在要求 bug-fix 具 FAST/NONE/DEEP 與 repository_search/test_output_summary/high_risk_implementation，並禁止結構化 sonnet/opus/haiku。
- [2026-09-27] [convergence-7] Commit `4543944`；GitHub Actions run 36331326081（#109）共 14 個 job 全部 success。
- [2026-09-27] [next] AC-29 下一小批只處理 `/plan-build`：保留 explorer=FAST，將 DB/後端/API/前端/測試正式實作者從 legacy opus 改為 `task=high_risk_implementation + profile=DEEP`；不要同批碰 `/plan` 或 `/plan-review`。

- [2026-09-27] [convergence-8] `/plan-build` 的 DB/backend/API/frontend/test 等正式實作者已從 legacy opus 改為 `task=high_risk_implementation + profile=DEEP + risk=high + complexity=high`；Explorer 保留 `repository_search + FAST`。
- [2026-09-27] [convergence-8] 單一 `delegate_write` 與 `parallel_delegate` 的每個子工作單元都必須各自帶 routing + allowed scope；Host 無 per-worker routing 時只能回報 `routing_degraded=true`。
- [2026-09-27] [convergence-8] DB MCP 分支、backend-only 分支與確認畫面同步移除 provider-specific model 描述；`lint-agent-model.py` 要求 plan-build 具 FAST/DEEP + repository_search/high_risk_implementation，並禁止結構化 sonnet/opus/haiku。
- [2026-09-27] [convergence-8] Commit `d58454c`；GitHub Actions run 36331690057（#111）共 14 個 job 全部 success。
- [2026-09-27] [next] AC-29 下一小批只處理 `/plan-review`：邏輯/品質 reviewer 轉 `routine_review + STANDARD`，效能 reviewer 轉 `performance_review + DEEP`，`--quick` 維持單一 STANDARD reviewer；不要同批碰 `/plan`。

- [2026-09-28] [convergence-9] `/plan-review` 邏輯/品質 reviewer 已改為 `task=routine_review + profile=STANDARD`；效能 reviewer 改為 `task=performance_review + profile=DEEP`。
- [2026-09-28] [convergence-9] `--quick` 維持單一 `logic-reviewer`，但 routing 改為 `routine_review + STANDARD`；完整審查的 parallel_delegate 只做排程，每個 reviewer 子工作單元各自帶 routing。
- [2026-09-28] [convergence-9] `/plan-security` 只以 `security_review + DEEP` 描述邊界，不再從 plan-review 直接指定 provider model。
- [2026-09-28] [convergence-9] `lint-agent-model.py` 現在要求 plan-review 具 STANDARD/DEEP + routine_review/performance_review，並禁止結構化 sonnet/opus/haiku。
- [2026-09-28] [convergence-9] Commit `fbeee17`；GitHub Actions run 36331908566（#113）共 14 個 job 全部 success。
- [2026-09-28] [next] AC-29 最後一小批只處理 `/plan`：spec requirement analysis 轉 STANDARD、db schema design / arch 轉 DEEP，移除最後 sonnet/opus callsite；完成後才勾 AC-29。

- [2026-09-28] [convergence-10] `/plan` spec pass 已改為 `task=requirement_analysis + profile=STANDARD + risk/complexity=medium`；只有 Router policy 真正升級時才進 DEEP，不因文件長度自行升級。
- [2026-09-28] [convergence-10] DB pass 已改為 `task=schema_design + profile=DEEP + risk/complexity=high + sensitive=schema_migration,transaction`；arch pass 改為 `task=architecture + profile=DEEP + risk/complexity=high`。
- [2026-09-28] [convergence-10] `/plan` 的 model Gotcha 改為 task/profile/risk/complexity contract；`lint-agent-model.py` 現在要求 STANDARD/DEEP + requirement_analysis/schema_design/architecture，並禁止結構化 sonnet/opus/haiku。
- [2026-09-28] [convergence-10] Commit `bd6ab42`；GitHub Actions run 36332180495（#115）共 14 個 job 全部 success。
- [2026-09-28] [convergence] AC-29 完成：plan / plan-build / plan-review / bug-investigate / bug-fix 五支核心 Skill 均已 provider-neutral；實際模型選擇只由 model-routing.json + Host adapter mapping 決定。
- [2026-09-28] [next] 下一小批進 AC-30 前先做 host-management advisory 分群：只盤點 CLAUDE_CONFIG_PATH / CLAUDE_PLUGIN_CLI / CLAUDE_MD 的 134 筆 advisory，分成「portable config contract 可消除」與「真正 host-specific 管理 adapter 應保留」；先不大改 setup/admin Skill。

- [2026-09-28] [convergence-11] AC-30 advisory 分群完成：Host portability CI #116 仍為 hard=0、advisory=134 / 31 files。
- [2026-09-28] [convergence-11] 134 筆分為：72 筆 portable config contract 候選、30 筆真正 host-management adapter、32 筆 project-instructions alias / 文件相容說明。
- [2026-09-28] [convergence-11] 72 筆候選集中在 CREW-owned feature config/projects/stacks、bug config、learnings；這些應由單一 deterministic resolver 提供 logical key/path，不應讓各 Skill 自己拼 `~/.claude*` 路徑。
- [2026-09-28] [convergence-11] 30 筆 host-management 包含 `claude plugin ...`、marketplace/installed_plugins、`settings.json`、Claude native rules/plugin install path；這些保留 Host adapter，不納入 portable config resolver。
- [2026-09-28] [convergence-11] 32 筆 CLAUDE.md advisory 多數已同時提 AGENTS.md 或明確經 `project_instructions`；保留為文件/adapter 例子，不以 advisory=0 為成功條件。
- [2026-09-28] [next] AC-30 下一小批只設計並實作 **portable config contract + deterministic resolver smoke test**：先定 logical namespaces（feature config/projects/stacks、bug config/learnings）與 legacy fallback；不要同批重寫 crew-init/project-add/plan-setup 等 18+ 檔案。

- [2026-09-28] [convergence-12] 新增共用 `references/config-contract.md` 與 `scripts/crew-config.py`：canonical root=`CREW_CONFIG_HOME`→`XDG_CONFIG_HOME/crew`→`~/.config/crew`，resolver 無副作用。
- [2026-09-28] [convergence-12] Logical keys：feature/config、feature/project、feature/stack、bug/config、bug/learning；read 支援既有 `~/.claude*` fallback，write 永遠只回 portable canonical path。
- [2026-09-28] [convergence-12] feature project/stack 可回退舊單一 `feature-workflow-config.md`，並以 `representation=legacy_monolith` 明示 caller 必須走舊 parser；stack/project-slug path traversal 會被拒絕。
- [2026-09-28] [convergence-12] 新增 `scripts/lint-config-resolver.py` 與 CI `Config resolver` job；shared-ref/sync 清單與 CONTRIBUTING 同步登記 config contract/resolver。
- [2026-09-28] [convergence-12] Commit `e28191a`；GitHub Actions run 36332689092（#118）共 15 個 job 全部 success。
- [2026-09-28] [next] AC-30 consumer 遷移採小步。下一小批只處理 `/bug-close` 的 learnings 寫入：以 `bug/learning --mode write` 取得 portable path，移除兩個 `~/.claude-company/bug-workflow/learnings` hardcode；不要同批改 bug-setup/plan-setup/project-add。

- [2026-09-28] [convergence-13] 依目前實際環境修正 config migration contract：`~/.claude-company` 已退役，從 `config-contract.md` 與 `crew-config.py` 的所有 fallback candidate 移除。
- [2026-09-28] [convergence-13] 現役 Claude fallback 只保留 `~/.claude/feature-workflow/...`、`~/.claude/feature-workflow-config.md`、`~/.claude/bug-workflow-config.md`、`~/.claude/bug-workflow/learnings/...`。
- [2026-09-28] [convergence-13] `lint-config-resolver.py` 會故意建立 `.claude-company` 假檔，確認 resolver 回 missing/canonical 而不是讀取退役路徑，防止歷史 fallback 被重新加入。
- [2026-09-28] [convergence-13] Commit `e7871d1`；GitHub Actions run 36333297598（#120）共 15 個 job 全部 success。
- [2026-09-28] [next] AC-30 下一小批回到原計畫：只遷移 `/bug-close` learnings 寫入，改用 `crew-config.py resolve --key bug/learning --mode write`；不要同批碰 bug-setup/plan-setup/project-add。

- [2026-09-28] [convergence-14] `/bug-close` learnings 寫入已改走 `crew-config.py resolve --key bug/learning --mode write --format path`；resolver 只回 canonical path，Skill 只負責 `mkdir -p dirname(path)` 與 append 單行 JSONL。
- [2026-09-28] [convergence-14] `lint-config-resolver.py` 新增 consumer contract：bug-close 必須呼叫 bug/learning write resolver，且不得再硬編碼 `~/.claude` / `.claude-company` learnings path。
- [2026-09-28] [convergence-14] Host portability 將 `config-contract.md` 視為 adapter/portability contract exemption，避免 intentional legacy fallback 汙染 consumer advisory；bug-close 禁止文案也不再重複實體 legacy path。
- [2026-09-28] [convergence-14] Functional commit `2dab7bd`；lint scope fix `ac90f53`；GitHub Actions run 36333700860（#123）共 15 個 job 全部 success。
- [2026-09-28] [convergence-14] Host portability 維持 hard=0，真正 consumer advisory 由 134 降至 132。
- [2026-09-28] [next] AC-30 下一小批只遷移 Bug learning **read** contract：`references/evidence-collection.md` 的學習搜尋改用 `bug/learning --mode read`；`references/learnings-schema.md` 同步更新 storage/read 範例並移除退役 `.claude-company`。不要同批碰 bug-setup/crew-init/project-add。

- [2026-09-28] [convergence-15] Bug learning read contract 已 portable 化：`evidence-collection.md` 改用 `crew-config.py resolve --key bug/learning --mode read --format path`；不存在時保留 `[ -f "$LEARN_FILE" ]` 靜默跳過語意。
- [2026-09-28] [convergence-15] `learnings-schema.md` 的儲存位置改描述 logical key / portable config root，基本搜尋同樣走 `bug/learning --mode read`；已移除 `.claude-company` 與直接 `~/.claude/.../learnings` 實體路徑。
- [2026-09-28] [convergence-15] `lint-config-resolver.py` 新增 learning-read consumer contract，要求兩份 reference 都使用 resolver，並禁止重新硬編碼 Host-specific learnings path。
- [2026-09-28] [convergence-15] Commit `997b1c1`；GitHub Actions run 36333960262（#125）共 15 個 job 全部 success。
- [2026-09-28] [convergence-15] Host portability 維持 hard=0，consumer advisory 再由 132 降至 131。
- [2026-09-28] [next] AC-30 下一小批只處理跨 plugin dev_branch 讀取：`bug-fix` 與 `references/merge-guide.md` 改用 `feature/project --mode read` resolver 取得 project config；移除兩處 `.claude-company` / `~/.claude` 路徑判斷。不要同批碰 setup/admin。

- [2026-09-28] [convergence-16] `/bug-fix` 分支引導與 `references/merge-guide.md` 的 dev_branch 讀取已改走 `crew-config.py resolve --key feature/project --repo-id {repo-id} --mode read --format json`。
- [2026-09-28] [convergence-16] Resolver 回 `hierarchical` 時讀 project frontmatter；回 `legacy_monolith` 時沿用舊表格 parser；`source=missing` 或 dev_branch 空白時使用既有通用提示，不阻擋 Bug 流程。
- [2026-09-28] [convergence-16] `lint-config-resolver.py` 新增 dev_branch consumer contract，禁止 `/bug-fix` 與 merge guide 重新硬編碼 `.claude-company` / `~/.claude/feature-workflow/projects`。
- [2026-09-28] [convergence-16] Commit `1b9c95a`；GitHub Actions run 36334276167（#127）共 15 個 job 全部 success。
- [2026-09-28] [convergence-16] Host portability 維持 hard=0，consumer advisory 由 131 降至 129。
- [2026-09-28] [next] AC-30 下一小批只遷移 `/plan-close` 的 Bug config 讀取：以 `bug/config --mode read` resolver 取代 `~/.claude-company/bug-workflow-config.md` / `~/.claude/bug-workflow-config.md` 二選一路徑。先不碰 `/plan-start`，也不碰 setup/admin。

- [2026-09-28] [convergence-17] `/plan-close` Bug 類型額外設定已改走 `crew-config.py resolve --key bug/config --mode read --format path`；`[ -f "$BUG_CONFIG_FILE" ]` 才讀 Bug 知識庫等設定。
- [2026-09-28] [convergence-17] Resolver missing 時沿用既有 `/bug-setup` 提示，不允許 Skill 自行 fallback 到 Host-specific `bug-workflow-config.md` 實體路徑。
- [2026-09-28] [convergence-17] `lint-config-resolver.py` 新增 plan-close consumer contract，要求 bug/config read resolver 並禁止 `.claude-company/bug-workflow-config.md` / `~/.claude/bug-workflow-config.md` 回歸。
- [2026-09-28] [convergence-17] Commit `0e92cdc`；GitHub Actions run 36334755517（#129）共 15 個 job 全部 success。
- [2026-09-28] [convergence-17] Host portability 維持 hard=0，consumer advisory 由 129 降至 128。
- [2026-09-28] [next] AC-30 下一小批只遷移 `/plan-start` 的 Bug config read：同樣改用 `bug/config --mode read` resolver，移除 `.claude-company` / `~/.claude` 二選一路徑；不要同批碰 setup/admin。

- [2026-09-28] [convergence-18] `/plan-start` Bug 類型額外設定已改走 `crew-config.py resolve --key bug/config --mode read --format path`；`[ -f "$BUG_CONFIG_FILE" ]` 才讀設定。
- [2026-09-28] [convergence-18] Resolver missing 時提示 `/bug-setup`，Skill 不再自行 fallback 到 `.claude-company/bug-workflow-config.md` 或 `~/.claude/bug-workflow-config.md`。
- [2026-09-28] [convergence-18] `lint-config-resolver.py` 新增 plan-start consumer contract，要求 bug/config read resolver 並禁止 Host-specific bug config path 回歸。
- [2026-09-28] [convergence-18] Commit `87fe946`；GitHub Actions run 36371467333（#131）共 15 個 job 全部 success。
- [2026-09-28] [convergence-18] Host portability 維持 hard=0，consumer advisory 由 128 降至 127。
- [2026-09-28] [next] AC-30 下一小批只遷移共用 `references/prerequisites.md` 的 config precheck：改用 `bug/config`、`feature/config`、`feature/project` resolver logical keys，移除兩 plugin 共 10 筆直接 Host path advisory；維持 shared-ref 同步，不碰 bug-setup/plan-setup/crew-init/project-add 寫入流程。

- [2026-09-28] [convergence-19] 共用 `references/prerequisites.md` 已 portable 化：Workflow 設定存在性改用 `bug/config` + `feature/config --mode read --format json`，不再列舉任何 Host-specific config path。
- [2026-09-28] [convergence-19] 專案註冊 precheck 改用 `feature/project --repo-id {repo-id} --mode read --format json`；hierarchical 讀 frontmatter、legacy_monolith 沿用舊表格 parser、missing 不自行拼 project path。
- [2026-09-28] [convergence-19] bug-workflow / feature-workflow 兩份 prerequisites 同步更新且保持 byte-identical；`lint-config-resolver.py` 新增 shared prerequisites consumer contract。
- [2026-09-28] [convergence-19] Commit `17ebc02`；GitHub Actions run 36372403953（#133）共 15 個 job 全部 success。
- [2026-09-28] [convergence-19] Host portability 維持 hard=0，consumer advisory 由 127 降至 117。
- [2026-09-28] [next] AC-30 下一小批只更新兩份 `references/config.template.md` 的 storage contract：Bug template 改描述 `bug/config`、Feature template 改描述 `feature/config` / portable config root，不再宣告 `.claude-company` 或 `~/.claude/feature-workflow` 實體位置；只改模板文字與 smoke contract，不改 `/bug-setup` / `/plan-setup` 寫入流程。

- [2026-09-28] [convergence-20] Bug `config.template.md` 已由退役 `.claude-company` 實體位置改為 `bug/config` logical key；實體位置交由 `crew-config.py` + `config-contract.md`。
- [2026-09-28] [convergence-20] Feature `config.template.md` 已由 `~/.claude/feature-workflow/` 改為 `feature/config` + `{portable-config-root}/feature` 邏輯結構，並標示 feature/project / feature/stack。
- [2026-09-28] [convergence-20] `lint-config-resolver.py` 新增兩份 template storage contract，禁止 template 重新宣告 `.claude-company` 或 `~/.claude` storage path。
- [2026-09-28] [convergence-20] Commit `b4de11c`；GitHub Actions run 36373092862（#135）共 15 個 job 全部 success。
- [2026-09-28] [convergence-20] Host portability 維持 hard=0，consumer advisory 由 117 降至 115。
- [2026-09-28] [next] AC-30 下一小批只處理 `/plan-deploy-confirm` 的 Feature config 描述：把 `~/.claude/feature-workflow/config.md` 改為 `feature/config` resolver logical key，補 consumer smoke contract；不要同批改 plan-stack、plan-setup 或其他 setup/admin。

- [2026-09-28] [convergence-21] `/plan-deploy-confirm` 的「任務追蹤工具」資料庫 ID 讀取描述已改為 `crew-config.py resolve --key feature/config --mode read --format path`；Skill 不再宣告 Host-specific Feature config 實體位置。
- [2026-09-28] [convergence-21] `lint-config-resolver.py` 新增 plan-deploy-confirm consumer contract，要求 `feature/config` read resolver + `config-contract.md`，並禁止 `~/.claude/feature-workflow/config.md` / `.claude-company` 回歸。
- [2026-09-28] [convergence-21] Functional commit `2d8f8eb`；GitHub Actions run 36375453153（#137）共 15 個 job 全部 success。
- [2026-09-28] [convergence-21] Host portability 維持 hard=0，consumer advisory 由 115 降至 114。
- [2026-09-28] [scope-note] `plan.md` 既有 D-48 編號重複；屬本批 scope 外，保持原狀未修。
- [2026-09-28] [next] AC-30 下一小批只處理 `/plan-stack` 的 Feature stack storage 描述：把「通常為 `~/.claude/feature-workflow`」改為 `feature/stack` resolver logical key，補 consumer smoke contract；不要同批改 `/plan-setup` 或其他 setup/admin。

- [2026-09-28] [convergence-22] `/plan-stack` 回傳的自訂技術棧 storage 描述已改為 `crew-config.py resolve --key feature/stack --stack-id {id} --mode write --format path`；不再把 `~/.claude/feature-workflow` 宣告為通常位置。
- [2026-09-28] [convergence-22] `lint-config-resolver.py` 新增 plan-stack consumer contract，要求 `feature/stack` + `--stack-id` write resolver 與 `config-contract.md`，並禁止 `~/.claude/feature-workflow` / `.claude-company` 回歸。
- [2026-09-28] [convergence-22] Functional commit `2aaf033`；GitHub Actions run 36376233264（#139）共 15 個 job 全部 success。
- [2026-09-28] [convergence-22] Host portability 維持 hard=0，consumer advisory 由 114 降至 113。
- [2026-09-28] [next] AC-30 下一小批只更新 `plugins/feature-workflow/references/config-resolver.md` 的 storage/compatibility contract：改以 `feature/config`、`feature/project`、`feature/stack` logical keys + `crew-config.py` / `config-contract.md` 為權威，移除已退役 `.claude-company` migration 描述與把 `~/.claude/feature-workflow` 當正式 storage root 的文字；保留漸進式載入/內建 stack parser 語意，不同批修改 `/plan-setup` 或其他 setup/admin。

- [2026-09-28] [convergence-23] `references/config-resolver.md` 已改為 portable logical config contract：storage root / fallback 由 `crew-config.py` + `config-contract.md` 決定，文件只保留 `feature/config` / `feature/project` / `feature/stack` 的漸進式載入與 parser 語意。
- [2026-09-28] [convergence-23] 已移除該 reference 內退役 `.claude-company` migration 與 `~/.claude/feature-workflow` 正式 storage root 描述；`legacy_monolith` 分支、三層載入、`stacks/_builtin.md` 內建 bundle 語意維持不變。
- [2026-09-28] [convergence-23] `lint-config-resolver.py` 新增 config-resolver reference smoke contract，要求 logical keys / read-write / representation / builtin stack 語意並禁止 Host-specific storage path 回歸。
- [2026-09-28] [convergence-23] Functional commit `2d9cc33`；GitHub Actions run 36377211211（#141）共 15 個 job 全部 success。
- [2026-09-28] [convergence-23] Host portability 維持 hard=0，consumer advisory 由 113 降至 104。
- [2026-09-28] [next] AC-30 下一小批開始 setup/admin 寫入流程，但仍只做一支：`/bug-setup`。既有設定偵測改用 `bug/config --mode read`，新設定目的地改用 `bug/config --mode write` canonical path，完全移除 `.claude-company` 與自行選 `~/.claude` 的邏輯，補 consumer smoke contract；不要同批改 `/plan-setup`、`/crew-init`、`/project-add` 或 crew-doctor。

- [2026-09-28] [convergence-24] `/bug-setup` 已改用 `bug/config` resolver contract：`BUG_CONFIG_READ_PATH` 由 `--mode read` 取得，`BUG_CONFIG_WRITE_PATH` 由 `--mode write` 取得；既有 legacy fallback 只作讀取來源，所有新建／更新結果只寫 canonical portable path。
- [2026-09-28] [convergence-24] 寫入前由 Skill 對 `BUG_CONFIG_WRITE_PATH` 執行 parent `mkdir -p`；resolver 維持無副作用。完成訊息也改回報實際 canonical write path，不再宣告 Host-specific 路徑。
- [2026-09-28] [convergence-24] `lint-config-resolver.py` 新增 bug-setup consumer contract，要求 `bug/config` read + write、read/write path 變數、canonical parent mkdir，並禁止 `.claude-company` / `~/.claude` storage path 回歸。
- [2026-09-28] [convergence-24] Functional commit `0bc650e`；GitHub Actions run 36378407237（#143）共 15 個 job 全部 success。
- [2026-09-28] [convergence-24] Host portability 維持 hard=0，consumer advisory 由 104 降至 99。
- [2026-09-28] [next] AC-30 下一小批只處理 `/project-add` 的 config/project storage：Bug config 讀取改用 `bug/config --mode read`；Feature config 讀取改用 `feature/config --mode read`；專案存在性與更新/新增目的地改用 `feature/project --repo-id {repo-id}` 的 read/write resolver contract，hierarchical / legacy_monolith 依 resolver representation 選 parser；移除 `.claude-company` / `~/.claude` 實體路徑與完成訊息硬編碼。不要同批改 `/plan-setup`、`/crew-init`、crew-doctor 或 resolver logical keys。

- [2026-09-28] [convergence-25] `/project-add` 已改為 resolver-owned project registration：`bug/config` / `feature/config` 只負責提供 Workflow / Notion metadata；既有 project mapping 用 `feature/project --mode read --format json` 定位，依 `representation=hierarchical|legacy_monolith` 選 parser。
- [2026-09-28] [convergence-25] 新增／更新 project mapping 一律用 `feature/project --mode write --format path` 取得 canonical path，再由 Skill 建立 parent directory 並寫 frontmatter/body；legacy monolith 只讀，不再原地修改或同步複製到多個 Host-specific 設定檔。
- [2026-09-28] [convergence-25] `lint-config-resolver.py` 新增 project-add consumer contract，要求 bug/feature config read、feature/project read+write、representation 分支與 canonical parent mkdir，並禁止 `.claude-company` / `~/.claude` storage path 回歸。
- [2026-09-28] [convergence-25] Functional commit `39a6156`；GitHub Actions run 36385757815（#145）共 15 個 job 全部 success。
- [2026-09-28] [convergence-25] Host portability 維持 hard=0，consumer advisory 由 99 降至 85。
- [2026-09-28] [next] AC-30 下一小批只處理 `/crew-init` 的 setup/registration 偵測：階段 1 改用 `bug/config --mode read` 判斷 bug-workflow 是否已設定；階段 2 改用 `feature/config --mode read` 判斷 feature-workflow 是否已設定；階段 4 改用 `feature/project --repo-id {repo-id} --mode read` + representation 判斷專案是否已註冊。提示文字不再宣告 Host-specific 產出路徑；`crew-init` 仍只委派 `/bug-setup`、`/plan-setup`、`/project-add`，不自行寫 config。不要同批改 `/plan-setup`、crew-doctor、crew-upgrade 或 resolver logical keys。

- [2026-09-28] [convergence-26] `/crew-init` 階段 1 已改用 `bug/config --mode read --format json` 判斷 bug-workflow setup；階段 2 改用 `feature/config --mode read --format json` 判斷 feature-workflow setup，legacy source 僅表示既有設定可讀，不由 crew-init 搬移。
- [2026-09-28] [convergence-26] 階段 4 已改用 `feature/project --repo-id {repo-id} --mode read --format json`；`hierarchical` 直接視為已註冊，`legacy_monolith` 先用既有 parser 確認 repo row。crew-init 不建立或更新 project mapping，仍委派 `/project-add`。
- [2026-09-28] [convergence-26] `/bug-setup` / `/plan-setup` 提示不再宣告 Host-specific 產出路徑；跨 Host/WSL gotcha 改以 resolver root 為準。`lint-config-resolver.py` 新增 crew-init read-only detection contract，禁止 `.claude-company` / `~/.claude` storage path 回歸。
- [2026-09-28] [convergence-26] Functional commit `8510a50`；GitHub Actions run 36387242501（#147）共 15 個 job 全部 success。
- [2026-09-28] [convergence-26] Host portability 維持 hard=0，consumer advisory 由 85 降至 75。
- [2026-09-28] [next] AC-30 下一小批只處理 `crew-doctor` 的 config/project 診斷：必要項 #6 改用 `bug/config --mode read`、#7 改用 `feature/config --mode read`、#8 改用 `feature/project --repo-id {repo-id} --mode read` + representation；移除 `--fix` 對 Host-specific feature-workflow 目錄的直接 `mkdir -p`，改提示由 `/bug-setup`、`/plan-setup`、`/project-add` 依 canonical resolver contract 修復。不要同批改 `/plan-setup`、crew-upgrade、host settings/rules advisory 或 resolver logical keys。

- [2026-09-28] [convergence-27] `crew-doctor` 必要項 #6/#7/#8 已改為 resolver read 診斷：`bug/config`、`feature/config`、`feature/project --repo-id {repo-id}`；project registration 依 `hierarchical` / `legacy_monolith` representation 判斷。
- [2026-09-28] [convergence-27] `--fix` 不再直接建立 Feature config/projects/stacks Host-specific 目錄；config/project 缺失分別提示 `/bug-setup`、`/plan-setup`、`/project-add`，讓 canonical writer 決定 storage。Host `settings.json` / rules 類檢查保持在 host-management 範圍，未納入本批。
- [2026-09-28] [convergence-27] `lint-config-resolver.py` 新增 crew-doctor consumer contract，要求三個 logical read key、representation 分支與 setup/project 修復入口，並禁止 `.claude-company` / `~/.claude/feature-workflow/` storage 回歸。
- [2026-09-28] [convergence-27] Functional commit `053b941`；GitHub Actions run 36391425076（#149）共 15 個 job 全部 success。
- [2026-09-28] [convergence-27] Host portability 維持 hard=0，consumer advisory 由 75 降至 69。
- [2026-09-28] [next] AC-30 下一小批只處理 `/plan-setup` 的「主設定層」：既有 Feature 設定偵測改用 `feature/config --mode read`；新主設定目的地改用 `feature/config --mode write` canonical path；匯入 Bug 共用 Notion IDs 時改用 `bug/config --mode read`；完成訊息回報 resolver write path。這一批不要改 `stacks/_builtin.md` / 自訂 stack bundle 的建立語意，不改 project mapping，不改 crew-upgrade、Host settings/rules 或 resolver logical keys。

- [2026-09-28] [convergence-28] `/plan-setup` Step 1 已改用 `feature/config --mode read --format json` 判斷既有設定與 representation，並用 `feature/config --mode write --format path` 取得 `FEATURE_CONFIG_WRITE_PATH`；legacy source 只讀，主設定一律寫 canonical portable path。
- [2026-09-28] [convergence-28] Step 2 已改用 `bug/config --mode read --format json` 取得 Bug 共用 Notion / workspace metadata；Step 7/8 以 `FEATURE_CONFIG_DIR=dirname(FEATURE_CONFIG_WRITE_PATH)` 建立既有階層式 bundle 並回報實際 canonical 主設定 path。`stacks/_builtin.md` / projects bundle 的既有建立語意未另行改寫。
- [2026-09-28] [convergence-28] `lint-config-resolver.py` 新增 plan-setup 主設定 consumer contract，要求 Feature read/write、Bug read、representation 分支、canonical config dir，並禁止 `.claude-company` / `~/.claude/feature-workflow` / `~/.claude/bug-workflow` storage path 回歸。
- [2026-09-28] [convergence-28] Functional commit `3754ac6`；GitHub Actions run 36417568716（#151）共 15 個 job 全部 success。
- [2026-09-28] [convergence-28] Host portability 維持 hard=0，consumer advisory 由 69 降至 62；剩餘 CLAUDE_CONFIG_PATH advisory 已全部落在 marketplace/plugin install、Host settings、Host rules 等 host-management/adapter 範圍，不再屬 CREW-owned config storage。
- [2026-09-28] [next] AC-30 下一小批不先改 code，改做 closure audit：逐一核對 AC-30 + D-37~D-43 的 contract，掃描 active Skill/reference 中 CREW-owned feature config/projects/stacks、bug config/learnings 是否仍有直接 Host path 或繞過 `crew-config.py` 的 consumer/writer；把剩餘 advisory 分類為 CREW config violation vs host-management adapter vs project-instructions alias。若 CREW-owned config violation=0 且 hard=0，補可重現 evidence 並評估勾選 AC-30；不要同批處理 AC-31、Codex CLI smoke、Phase 4 或 merge PR。

- [2026-09-28] [convergence-29] AC-30 closure audit 以 HEAD `d2d18af` 為基準完成；AC-30 已勾選。GitHub Actions #152 的 Host portability 掃描 74 個 active Skill/reference，結果 `hard=0 / advisory=62`。
- [2026-09-28] [convergence-29] #152 的 62 筆 advisory 精確分類為：`CLAUDE_PLUGIN_CLI=20`、`CLAUDE_MD=32`、`CLAUDE_CONFIG_PATH=10`。10 筆 config-path advisory 全部是 marketplace/plugin install path、`settings.json` 或 `~/.claude/rules/*`，符合 `config-contract.md` 明定的 host-management adapter 邊界；32 筆 `CLAUDE_MD` 屬 `project_instructions` alias。
- [2026-09-28] [convergence-29] Legacy storage keyword 候選的 18 個 active Skill/reference 已逐檔以目前 branch 回讀：direct CREW-owned Host path violation=0，18/18 均引用 `crew-config.py`；涵蓋 `feature/config`、`feature/project`、`feature/stack`、`bug/config`、`bug/learning` 及 legacy_monolith parser consumers。
- [2026-09-28] [convergence-29] Config resolver CI #152 同時通過 setup/admin 與 runtime consumer smoke：bug-setup、project-add、crew-init、crew-doctor、plan-setup、plan-stack、plan-start/close、bug-close、dev_branch consumers、shared prerequisites/templates/config-resolver reference 全部綠燈；portable read precedence / canonical write / legacy representation 契約有 deterministic 防回歸。
- [2026-09-28] [convergence-29] 可重現 closure 檢查：`python3 scripts/lint-host-portability.py --strict` 應維持 hard=0；`python3 scripts/lint-config-resolver.py` 應全綠；另以 active Skill/reference 搜尋 `~/.claude[-company]` 的 feature-workflow config/projects/stacks、bug-workflow config/learnings 與 `~/.config/crew/{feature,bug}` direct storage path，排除 `config-contract.md` 後應為 0。
- [2026-09-28] [convergence-29] Closure commit `d9de577`；GitHub Actions run 36419432700（#153）共 15 個 job 全部 success；Host portability 再確認 `hard=0 / advisory=62`。AC-30 closure evidence 已由 audited HEAD + closure commit 自身 CI 雙重驗證。
- [2026-09-28] [next] AC-31 下一小批只建立 v1 retirement contract，不刪相容層：以 `feature-workflow@5.0.0` 發布日 `2026-07-28` 為起點，明確寫出「第一個 `5.1.0` minor 發布日或 `2026-10-26`，以先到者為 removal eligibility」；目前 `5.0.2` / `2026-09-28` 尚未達門檻。更新 `references/legacy-v1.md` 的 `{日期}`、到期條件與清理 checklist，並補 deterministic lint 防止未達條件就刪除 `legacy-v1.md` / `plan-status --migrate` / crew-doctor v1 檢查；不要同批真正移除 v1、處理 AC-1、Phase 4 或 merge PR。

- [2026-09-29] [convergence-30] AC-31 retirement contract 已具體化：`legacy-v1.md` 明列起點 `feature-workflow@5.0.0 / 2026-07-28`，removal eligibility 為 `5.1.0+` 發布或 `2026-10-26`，以先到者為準；原 `{日期}` placeholder 已移除。
- [2026-09-29] [convergence-30] `legacy-v1.md` 到期 cleanup checklist 已明列 atomic removal surface：legacy reference、各 Skill v1 分支、`plan-status --migrate`、crew-doctor v1 檢查與項數、state-writer 過渡期 EXEMPTIONS/guard、README 現行連結與完整 CI；eligibility 到達前禁止部分刪除。
- [2026-09-29] [convergence-30] `lint-state-writers.py` 新增 machine-checkable retirement gate：讀 `feature-workflow/plugin.json` 實際版本，預設以執行日期判斷，並支援 `CREW_LINT_DATE=YYYY-MM-DD` 重現日期條件。Gate 未達時缺 `legacy-v1.md`、`plan-status --migrate` 或 crew-doctor v1 偵測皆會讓 `--strict` 失敗。
- [2026-09-29] [convergence-30] Functional commit `a9ed9dc`；GitHub Actions run 36514170638（#155）15/15 success。State-writer gate 實際輸出：`feature-workflow=5.0.2, check_date=2026-09-29, gate=version>=5.1.0 OR date>=2026-10-26, eligible=false`，且 compatibility presence guard success。
- [2026-09-29] [convergence-30] Host portability 維持 `hard=0 / advisory=62`；AC-31 已勾選完成。v1 相容層目前仍完整存在，沒有提前退休。
- [2026-09-29] [next] 剩餘唯一未完成驗收條件為 AC-1。下一小批只做「真實 Codex CLI marketplace add/install smoke」：先確認執行環境真的有可用 Codex CLI，依執行當下官方 CLI 語法把 `mark22013333/crew` 當 marketplace source，驗證可發現並安裝 portable plugin，記錄 Codex CLI version、實際命令、stdout/stderr 與結果。若環境沒有 Codex CLI 或 marketplace 功能不可用，明確記為未完成，絕不以 manifest/lint 代替真機 smoke；不要同批進 Phase 4、修改已完成 AC-30/31、mark ready 或 merge PR。

- [2026-09-29] [convergence-31] AC-1 真實 Codex CLI smoke 已完成。原工作容器無 `codex` 且外部 DNS 受限，因此改用一次性 GitHub-hosted runner，不以靜態 manifest/lint 代替真機驗證。
- [2026-09-29] [convergence-31] 探索 run 36514738619（#157）安裝 `codex-cli 0.158.0`，成功執行 `codex plugin marketplace add mark22013333/crew --ref feature/crew-6-portable-plugin`；Codex 回報 marketplace `crew` 已加入，snapshot 解析出 `bug-workflow` / `feature-workflow`。同 run 的 `codex plugin --help` 確認真實安裝子命令是 `plugin add`，不是 `plugin install`。
- [2026-09-29] [convergence-31] 安裝 run 36514828460（#158）16/16 success；實跑 `codex plugin add bug-workflow@crew` 與 `codex plugin add feature-workflow@crew` 均成功。`codex plugin list` 回報 `bug-workflow@crew installed, enabled 4.0.1`、`feature-workflow@crew installed, enabled 5.0.2`；實體 cache 亦存在兩份 portable `plugin.json`。
- [2026-09-29] [convergence-31] AC-1 已勾選；至此 AC-1～AC-31 全部完成。一次性 `Codex marketplace smoke (temporary)` CI job 已在本 checkpoint 移除，避免把網路型 smoke 永久加入既有 deterministic lint pipeline。
- [2026-09-29] [next] 不再自動新增 implementation scope。Phase 4 Runtime/MCP 仍維持 D-21 的 deferred 決策；PR #17 保持 draft/open/unmerged。下一步應先做最終 PR evidence review，再由使用者明確決定是否 mark ready 或 merge；未收到明確指示前不得執行這兩個動作。
