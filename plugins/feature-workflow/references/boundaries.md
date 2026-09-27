# 動作邊界參考

> `.spec/{slug}/` 只有 `plan.md`（六章節）＋ `state.json`（流程狀態唯一權威，單一寫者
> `crew-state.py`）＋ `deploy.sql`（唯一 SQL 事實來源）＋ `.cache/`（一次性報告暫存）。
> 章節契約與寫入紀律見 `plan-common.md`。

## plan-build

### 🟢 ALWAYS（自動執行，不詢問）
- 讀取 `.spec/{slug}/plan.md`（目標與範圍、驗收條件、決策紀錄、指路）與 `deploy.sql`
- 流程位置一律問 `crew-state.py`（`next` / `validate`），不用「哪些檔案存在」反推
- 載入技術棧定義和掃描規則
- 掃描現有程式碼範本
- 每完成一個角色就 `crew-state.py unit` 寫進度（斷點保險）
- 把程式碼落點以錨點條目 Edit 進 plan.md「指路」節
- 執行退出驗證門檻

### 🟡 ASK FIRST（顯示計畫，等使用者確認）
- 啟動多角色實作（步驟 4 的確認提示；探索 `model: sonnet`、實作 `model: opus`；執行方式由 Host adapter 決定）
- Teammate 失敗時的處理策略（重試 / 跳過 / 終止）
- API 契約不一致時的調整方向
- 退出驗證中 WARN 項目的處理

### 🔴 NEVER（禁止，即使使用者要求也應警告）
- 有獨立 worker 可用時 Leader 自己寫應用程式碼；若 Host 明確降級為 inline，主 Agent 只能依單一 `delegate_write` role 的 scope 依序實作
- 在 plan.md 決策紀錄沒有 `[arch]` 條目（`state.json` 的 `steps.arch` 既非 `done` 也非 `skipped`）時開工 —— 這是 hard block
- 自動補寫架構決策條目來繞過上述 hard block
- 用 Write 整檔改寫 plan.md，或把整個章節當 `old_string` 取代
- 在 plan.md 抄寫欄位清單、方法簽章、DDL（一律改用 `@code:` / `@sql:` 錨點）
- 另建任何新的文件檔（變更清單的事實來源是 `git diff --name-only`）
- 修改其他任務（非當前 slug）的 `.spec/` 內容
- 跳過退出驗證中的 BLOCK 項目

---

## plan-review

### 🟢 ALWAYS
- 用 `git diff --name-only`（必要時對基準分支）收集審查範圍
- 讀取 `plan.md` 的驗收條件與決策紀錄作為審查基準
- 執行交叉審查合併步驟
- 完整報告落 `.spec/{slug}/.cache/`（一次性暫存），結論以一條進 plan.md「檢查報告摘要」節，並用 `crew-state.py result --kind review` 寫進 `state.json`

### 🟡 ASK FIRST
- 3 人完整審查（預設）vs --quick 單人審查
- 發現 🔴 嚴重問題後的處理策略

### 🔴 NEVER
- 跳過合併步驟
- 自動降級嚴重度（🔴 → 🟡）
- Reviewer 之間互相呼叫
- 把逐條發現全文塞進 plan.md（該節只放結論摘要，上限 6 行）

---

## plan-verify

### 🟢 ALWAYS
- 連接 Chrome 前確認模式（MCP / Bash / api-only）
- 每條驗收條件都記錄結果（PASS / FAIL / SKIP / MANUAL），逐條對回 plan.md 的 `AC-n`
- 收集截圖到 `.spec/{slug}/screenshots/`
- 完整報告落 `.spec/{slug}/.cache/`（一次性暫存），結論以一條進 plan.md「檢查報告摘要」節，並用 `crew-state.py result --kind verify` 寫進 `state.json`

### 🟡 ASK FIRST
- 第一次連接 Chrome（確認目標分頁）
- --manual 模式的每步驟確認
- FAIL 項目是否需要立即修正

### 🔴 NEVER
- 跳過 FAIL 項目不記錄
- 自動將 FAIL 標記為 SKIP
- 未驗證回應 body 就標記 PASS
- 把驗證報告全文抄進 plan.md（該節只放結論摘要）

---

## plan-security

### 🟢 ALWAYS
- 執行 Layer 1 靜態規則掃描
- 掃描 MyBatis ${} 使用
- 掃描硬編碼密碼/Token
- 檢查 Controller 參數驗證
- 完整報告落 `.spec/{slug}/.cache/`（一次性暫存），結論以一條進 plan.md「檢查報告摘要」節，並用 `crew-state.py result --kind security` 寫進 `state.json`

### 🟡 ASK FIRST
- 發現 🔴 嚴重漏洞時是否立即修復
- 外部依賴 CVE 掃描結果（可能有 false positive）
- 需要新增安全 middleware 或 filter

### 🔴 NEVER
- 忽略 SQL Injection 發現（「只是內部 API」）
- 降級安全問題嚴重度
- 跳過 Layer 1 靜態掃描

---

## plan-demo

### 🟢 ALWAYS
- 產出目錄一律加 `demo-` 前綴，避免污染真實 `.spec/`（前綴就是 demo 的唯一辨識標記）
- 產出物與真實任務同構：`plan.md`（六章節）＋ `state.json`（用 `crew-state.py init` 建）＋ 必要時 `deploy.sql`
- 全程本地寫入，不呼叫 Notion / 多角色委派 / DB 工具

### 🟡 ASK FIRST
- `.spec/demo-{slug}/` 已存在時是否覆寫
- 使用者指定的題目過於複雜時，是否仍用簡化範本產出

### 🔴 NEVER
- 寫入 Notion 或觸發 Notion OAuth
- 啟動多角色委派或連線 DB 工具
- 建立 Git branch

---

## plan-deploy-confirm

### 🟢 ALWAYS
- 逐筆列出 deploy.sql 的每個 Step 供確認
- 記錄執行時間、環境（dev/staging/prod）、執行者
- 確認後寫回 Notion「🚀 部署狀態」區塊

### 🟡 ASK FIRST
- 環境未指定時（未帶 `--env`）
- 部分 Step 執行失敗時的後續處理

### 🔴 NEVER
- 略過任一 Step 的確認直接標記全部完成（除非明確帶 `--all-done`）
- 覆蓋既有的部署狀態記錄而非附加
- 在沒有 deploy.sql 或未執行過 `/plan-close` 的任務上執行回報

---

## plan-next

### 🟢 ALWAYS
- 呼叫 `crew-state.py list --format json` 定位任務、`crew-state.py next --slug <slug> --format json` 取得下一步（`state.json` 是流程位置的唯一權威）
- 照實轉述回傳的 `command` 與 `reason`，`command` 為 `null` 就只轉述 `reason`
- 多個活躍任務時列出讓使用者選擇，或用 `--all` 全部列出

### 🟡 ASK FIRST
- `state.json` 的 `inferred` 為 `true`（狀態由 `rebuild` 推測而來）→ 先請使用者確認狀態正確，再照建議往下走
- `state.json` 與檔案實況矛盾（例：`steps.build` 為 `done` 但 `git diff` 沒有任何程式碼變更）→ 問使用者要跑 `crew-state.py rebuild` 自我修復，還是照 `state.json` 續行
- `parked` 非 null → 先問是否 `/plan-status --unpark <slug>`

### 🔴 NEVER
- 用「哪些檔案存在」反推流程位置（這是舊版做法，已被 `state.json` 取代）
- 改寫 script 回傳的 `command` / `reason`，或另給一個自己想的建議
- 讀不到狀態（非 0 exit）時用猜的補一個建議
- 自行改寫 `state.json`（唯一寫者是 `crew-state.py`，且矛盾要由使用者裁決）

---

## plan-close

### 🟢 ALWAYS
- 結案前跑 `check-spec-drift.py` 當硬關卡，通過才蓋 plan.md frontmatter 的 `verified_at_commit` / `verified_at`
- 一次性批次同步 `plan.md` 與 `deploy.sql` 到 Notion
- 流程狀態一律經 `crew-state.py set --step close --status done` 寫入
- `.spec/` 預設被 gitignore，要進版控用 `git add -f`

### 🟡 ASK FIRST
- 漂移檢查 exit 2（只有 WARN）→ 逐筆請使用者明示放行
- plan.md 仍有未勾選的 `AC-n`，或 `state.json` 的 `results` 有 FAIL 時是否仍要結案
- `deploy.sql` 尚未由 `/plan-deploy-confirm` 回報執行時的處理

### 🔴 NEVER
- 漂移檢查 exit 1 或 exit 3 仍蓋章結案（exit 3 是「這次沒檢查成」，不是通過）
- 用 `--fix` 硬改錨點讓檢查變綠來滿足結案條件
- 把 `drift_policy: off` 當成通過漂移關卡的手段
- 用 Write 整檔改寫 plan.md（結案摘要一樣是 Edit 對錨點插入條目）

---

## plan-drift

### 🟢 ALWAYS
- 依 `check-spec-drift.py --format json` 的**內容**決定走哪一步，不是只看 exit code
- `autofixable: true` 的機械型（`git -M` 改名、行號位移）才自動修，並用 `--fix` 前後的 `diff` 取回實際改動後逐條回報
- 每次都掃有無 `level: ENV`（`E1`）項目，有就回報「無法檢查」＋ script 的「修法：」原文

### 🟡 ASK FIRST
- `autofixable: false` 的語意型（D2 / D4 / D5 / D6 / D7）逐條確認，一次只問一條
- exit 2（只有 WARN）的每一筆是否放行
- 是否啟用逃生閥（行內 `<!-- drift-ignore: … reason=… -->` 或整份 `drift_policy: off`）—— 由使用者決定，不自己塞

### 🔴 NEVER
- 對語意型提供「全部照建議改」的批次選項
- 把符號消失一律當成改名硬改錨點（決策變了該做的是用 `D-n 取代 D-m` supersede 改決策紀錄）
- exit 1、exit 3 或有 ENV 項目時蓋章
- 把 `drift_policy: off` 的任務回報成「全部通過」（那是「未檢查」）
- 用 Write 整檔改寫 plan.md，或順手去改程式碼（本 skill 只動 plan.md）
