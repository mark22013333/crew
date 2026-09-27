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
- [ ] AC-28 Bug skills 逐批接上 state lifecycle：`bug-start` init、`bug-investigate` 進度、`bug-fix` 修復/驗證、`bug-close` 結案；中斷後 `next/session-brief` 可正確續跑。
- [ ] AC-29 剩餘 provider-specific model callsites（plan/plan-build/plan-review/bug-investigate/bug-fix）完成 profile routing 遷移，不再靠 legacy sonnet/opus 名稱。
- [ ] AC-30 Host-management/setup portability 收斂：將設定路徑與 plugin CLI 類 advisory 分離成 portable config contract / host-specific 管理 adapter；核心 workflow 維持 hard=0。
- [ ] AC-31 v1 legacy retirement 具明確移除條件與版本/日期，不在條件未滿足前刪相容層。
- [ ] AC-1 repo 存在 .agents/plugins/marketplace.json，Codex 可把 mark22013333/crew 當 marketplace source。（結構與官方格式已完成；仍需在有 Codex CLI 的環境做一次實際 marketplace add smoke test）
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
- D-24 [convergence] Model routing 尚有刻意保留的 legacy callsites：plan、plan-build、plan-review、bug-investigate、bug-fix 仍由 lint 允許 sonnet/opus 結構化名稱；下一階段應繼續 profile 化，而不是用新的 runtime 包住舊模型名稱。
- D-25 [convergence] v1 相容層先保留。`legacy-v1.md` 已宣告「一個 minor 或 90 天」但沒有機器可判定的明確 retirement marker；先補明確移除條件，再刪 plan/status/next/build/close 等相容分支。
- D-26 [convergence] state schema 升到 v2 並採 type-aware steps：feature=`start/spec/db/arch/build/security/verify/review/close`；bug=`start/investigate/fix/close`。Bug 的編譯/測試/迴歸證據屬 fix work units，不為了對齊 Feature 而偽造 verify/review phase。
- D-27 [convergence] `crew-state.py next` 對 type=bug 獨立決策：investigate 未完成→`/bug-investigate`；fix 未完成→`/bug-fix`；fix 完成且 UAT pending→`/bug-close`；UAT rejected→回 `/bug-fix`；close 完成→結案。
- D-28 [convergence] schema v1 Bug state normalize 到 v2 時不搬運舊 Feature steps 當 Bug 進度；只保留同義的 start/close，新增 investigate/fix，並可由 `work_unit.skill` 修正 phase。
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
- Bug workflow 的 state lifecycle 尚未像 feature workflow 一樣完整：`bug-investigate` / `bug-fix` 目前沒有正式寫入 `steps.verify/review`；因此 UAT prerequisite 不能直接共用 feature 的 `review=done` 規則。

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
