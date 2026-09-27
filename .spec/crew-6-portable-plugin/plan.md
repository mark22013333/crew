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
- [ ] AC-15 Phase 3A 建立 NONE/FAST/STANDARD/DEEP model profile 與 deterministic router。
- [ ] AC-16 Phase 3A 純探索/蒐證工作可路由 FAST；架構/DB/security 保持 DEEP。
- [ ] AC-17 Phase 3B state.json 具 approval gates，未核准需求不得進 build。
- [ ] AC-18 Phase 3B crew-state.py next/validate 能以 gate 決定是否 BLOCK，不靠 Skill 自律。
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