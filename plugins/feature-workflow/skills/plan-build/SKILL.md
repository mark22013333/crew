---
name: plan-build
description: 從 .spec/{slug}/plan.md 以多角色 leader-delegate 模式產生程式碼，含退出驗證與錨點有效性檢查；依 Host capability 自動選擇平行或序列執行。當使用者提到 /plan-build、「從 spec 產生程式碼」、「plan-build 產碼」時觸發此 Skill。
argument-hint: "[--with-test|--no-test] [--backend-only] [--dry-run] [--resume]"
---

# plan-build — 多角色程式碼產生

從 `.spec/{slug}/plan.md`（唯一規劃文件）與 `deploy.sql`（唯一 SQL 事實來源）讀取決策與驗收條件，以 `host-capabilities.md` 的 `delegate_readonly` / `delegate_write` / `parallel_delegate` 執行 leader-delegate。Host 有獨立 worker 時 Leader 只協調；若 adapter 降級為 inline，主 Agent 可依序執行角色，但必須保留每個角色的 scope 與驗證契約。

> **本 skill 不產生任何新文件檔**：變更清單的事實來源是 `git diff --name-only`，流程狀態一律經 `crew-state.py` 寫入 `state.json`，程式碼落點以錨點條目寫進 plan.md 的「指路」節。

> **v1 舊任務**：`.spec/{slug}/plan.md` 不存在 → 這是 v1 結構，依
> `../../references/legacy-v1.md` 的相容模式執行，並在開頭提示一次。
> 過渡期限定，到期本段連同該檔一併刪除。
---

## 前置條件

### Host capability

載入 `../../references/host-capabilities.md`。多角色平行執行是最佳化，不是 hard prerequisite：

- 有 `parallel_delegate` → 互不衝突的角色可平行。
- 只有單一 delegate / subagent → 依序委派。
- 沒有 subagent → 主 Agent inline 依角色契約執行。
- Host-specific 的平行執行設定由 adapter 處理；CREW workflow 不直接依賴任何特定產品的 Team 環境變數。

### 規劃內容

**必須**已跑過 `/plan`（至少 arch pass）。判定方式**不是看檔案存在**，而是看狀態：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" list --slug {slug} --format json
```

`steps.arch.status` 不是 `done`／`skipped` → **禁止繼續**，告知使用者先執行 `/plan arch`。
`.spec/{slug}/plan.md` 的「決策紀錄」查無 `D-1 [spec] 範圍判斷` → 同樣禁止繼續，先執行 `/plan spec`。

> **前置檢查**：參照 plugin 根目錄 `references/prerequisites.md`（相對 SKILL.md 為 `../../references/`）檢查專案指令是否存在。

---

## 紀律護欄

> 紀律護欄：`../../references/discipline-preamble.md`（通用紀律）＋ `../../references/anti-rationalizations.md`「plan-build 專用」＋ `../../references/boundaries.md`「plan-build」段；斷點保險改為**進度即寫 `state.json`**（每完成一個角色就跑 `crew-state.py unit`，見『更新狀態與指路錨點』一節）；有「可以跳過」「應該夠了」的衝動時，停下查表確認是否為已知偏離模式。

---

## 使用方式

```
/plan-build                # 完整產生（後端 + 前端，預設不含測試）
/plan-build --with-test    # 包含測試程式碼
/plan-build --no-test      # 明確不含測試（同預設）
/plan-build --dry-run      # 預覽不建立檔案
/plan-build --backend-only # 只產後端
/plan-build --resume       # 從 state.json 的 work_unit 續跑未完成的角色
```

`--resume`：先讀 `crew-state.py list --slug {slug} --format json` 的 `work_unit`，只 spawn `remaining` 列出的角色，已完成的不重跑。`work_unit` 為空 → 視同完整執行。

---

## 流程

### 1. 定位活躍任務

參照 plugin 根目錄 `references/plan-common.md`（相對 SKILL.md 為 `../../references/`）的「定位活躍任務」（`crew-state.py list`），流程位置一律以 `state.json` 為準。

### 2. 讀取規劃內容

讀取 `.spec/{slug}/` 下的**兩份**產物：

| 產物 | 用途 | 必要性 |
|------|------|--------|
| `plan.md` | 目標與範圍、驗收條件（`AC-n`）、決策紀錄（`D-n`）、已知取捨、指路錨點 | **必要** |
| `deploy.sql` | 唯一 SQL 事實來源（表結構、索引、初始資料） | DB_REQUIRED=true 時必要 |

🔴 **不要**再去找 spec／db／arch 三份文件，它們已廢除；plan.md 沒寫的「是什麼」（欄位、簽章、類別清單）一律照「指路」節的錨點去讀**程式碼與 deploy.sql 本身**，不要憑印象補。

### 3. 判斷團隊組成

依據 plugin 根目錄 `references/team-composition.md`（相對 SKILL.md 為 `../../references/`）的判斷規則決定團隊配置。

讀取 plan.md 決策紀錄的 `D-1 [spec] 範圍判斷` 條目，取得 TASK_TYPE、CHANGE_SCOPE、FRONTEND_REQUIRED、DB_REQUIRED 等欄位；DB_MCP_AVAILABLE 依 `host-capabilities.md` 的 `tool_probe(tool_kind=database)` 現場判定。

若 `D-1` 條目缺少 TASK_TYPE / CHANGE_SCOPE → 回退邏輯，只看 FRONTEND_REQUIRED × DB_MCP 兩個欄位判斷。若 `D-1` 被後續條目 supersede（`D-n [階段] 取代 D-1：…`）→ **以最新的取代條目為準**。

### 4. 確認執行計畫

```
即將啟動 CREW 多角色程式碼產生：

📄 設計來源：.spec/{slug}/plan.md{ + deploy.sql}
🔍 探索官：scout（profile: FAST）— 專案結構/相似功能/風格範本/交叉引用（唯讀；由 Router 對映 Host 模型）
📊 Teammate 配置（全部 model: opus）：
  {• db-engineer       — DB 遷移/索引/效能優化（需 DB MCP）}
  • backend-engineer  — 後端核心（POJO/Mapper/Service）
  • api-engineer      — API 層（Controller/DTO/驗證）
  {• frontend-engineer — 前端頁面（{FRONTEND_TECH}）}

是否產出測試程式碼？
  1. 是 — 包含 test-engineer 角色
  2. 否（預設）— 跳過測試，節省 token

{--dry-run: 預覽模式，不建立檔案}

確認開始？[Y/n]
```

#### 測試可選化判斷規則

- 若團隊組成原本只有 1-2 人且不含 test-engineer → 不顯示此選項
- 若使用者使用 `--with-test` 參數 → 自動選是，不互動
- 若使用者使用 `--no-test` 參數 → 自動選否（同預設），不互動
- 使用者選「是」時，在團隊中加入 test-engineer
- 使用者選「否」或直接 Enter（預設）時，不含 test-engineer
- test-engineer 的加入/移除在 plugin 根目錄 `references/team-composition.md`（相對 SKILL.md 為 `../../references/`）判斷**之後**操作，不修改判斷表本身

### 5. 準備分層脈絡（派唯讀探索官，profile: FAST）

依據 plugin 根目錄 `references/build-context-layers.md`（相對 SKILL.md 為 `../../references/`）的四層策略，為每個 Teammate 準備定制化的脈絡。

> **模型與邊界（硬性規則）**——完整政策見 plugin 根目錄 `references/model-policy.md`（相對 SKILL.md 為 `../../references/`）：
> - 5a–5d 的掃描與讀取工作依 `host-capabilities.md` 使用 **`delegate_readonly`**，role=`explorer`，routing=`task: repository_search`、`profile: FAST`、`risk: low`、`complexity: low`；執行前以 `crew-model-route.py` 驗證並套用 Host mapping（探索官 prompt 模板見 `references/build-prompts.md`「探索官模式」）。
> - 探索官只用唯讀工具，🔴 不得修改任何程式碼；產出「實作交接」（模板見 `model-policy.md`）交給步驟 6 的實作者。
> - 這一步的目的就是**讓 Opus 實作者不必再掃 repository**。探索範圍只有 1–2 個已知路徑的檔案時，Leader 可自行讀取，不必派探索官。

#### 5a. 擷取共用核心（Layer 0）
從 `project_instructions` 擷取技術棧、命名慣例、禁止事項，格式化為 5 行以內。

#### 5b. 準備角色脈絡（Layer 1）
按 Teammate 角色，從 `plan.md`（與 DB 角色的 `deploy.sql`）擷取該角色需要的條目（見 build-context-layers.md 的角色分配表）：驗收條件 `AC-n`、相關的 `D-n` 決策與理由、指路錨點。

#### 5c. 預篩選範本（Layer 2）
1. 用 Glob 找到同層級的候選範本
2. 讀取每個候選，選出最簡單、最標準的
3. 擷取關鍵片段（class 宣告 + 1 個方法 + import 區塊）
4. 附帶學習重點指引

#### 5d. 預備交叉引用清單（Layer 3）
從 `deploy.sql` 與 plan.md 的驗收條件提取跨角色約束（NOT NULL、UNIQUE、必填參數、外鍵、分頁限制）。約束的事實在 `deploy.sql`，不是在文件敘述裡。

### 6. 啟動實作 Agent（逐一具名 spawn，model: opus）

讀取 plugin 根目錄 `references/build-prompts.md`（相對 SKILL.md 為 `../../references/`）取得 Teammate prompt 模板。

根據『判斷團隊組成』一節的角色判斷，選擇單角色或多角色模板，將『準備分層脈絡』一節準備的脈絡嵌入各 role 的 input 中；執行方式交給 Host adapter。

> 模板中的 `{placeholder}` 需替換為實際值。見 build-prompts.md 的變數說明。

#### Teammate prompt 組裝規則

每個 Teammate 的最終 prompt = Layer 0 共用核心 + Layer 1 角色脈絡 + Layer 2 範本片段 + Layer 3 交叉引用 + build-prompts.md 的角色模板

> Layer 2／Layer 3 來自『準備分層脈絡』一節 FAST 探索官產出的「實作交接」，四層都要嵌入，不可省略 Layer 3（跨角色約束：NOT NULL／UNIQUE／必填參數／外鍵／分頁限制）。

#### 模型與 spawn 規則（硬性）

完整政策見 plugin 根目錄 `references/model-policy.md`（相對 SKILL.md 為 `../../references/`）。

- 每個實作角色都用 **`delegate_write`** 獨立工作單元（role 例如 `backend-engineer`），capability request 必須帶 `model: opus` 與 allowed scope。
- 🔴 **不可**用「建立整個團隊並使用 Opus」這種自然語言指定模型 —— 那只是敘述，不保證生效。
- 探索與實作是兩個工作單元：角色的 repository 掃描已在步驟 5 由 FAST 探索官完成，DEEP 實作者**只用交接內容**，🔴 不得重新全域掃描 repository。
- Leader（本 skill）只協調、不寫正式程式碼（見 anti-rationalizations.md B2）。

#### 單角色 vs parallel_delegate 選擇

根據『判斷團隊組成』一節的判斷結果（見 plugin 根目錄 `references/team-composition.md`，相對 SKILL.md 為 `../../references/`）：
- 1 人 → 單一具名 subagent（`{"model": "opus"}`）
- 2+ 人 → 優先 `parallel_delegate`；若 Host 無平行能力則序列 `delegate_write`。跨角色 API 契約由 Leader 彙整後再傳遞，不依賴特定 Team message 工具。

### 7. 更新狀態與指路錨點

程式碼產生完成後（🔴 **不產生任何清單檔**）：

#### 7a. 變更清單以 git 為事實來源

```bash
git diff --name-only          # 尚未 commit 的本次變更
git status --porcelain        # 含未追蹤的新檔
```

需要與規劃基準比對時（`{prod_branch}` 從專案設定讀取；未設定時先取 `origin/HEAD` 指向的分支，若無則依序嘗試 `production` → `master` → `main`）：

```bash
git diff --name-only $(git merge-base HEAD {prod_branch})..HEAD
```

清單只在回報中呈現，🔴 不寫成文件檔 —— 檔案清單改一次程式就過期，git 永遠是對的。

#### 7b. 在 plan.md「指路」節補錨點（每個角色的落點各一行）

依 `references/plan-common.md`「寫入紀律」用 **Edit** 對 `<!-- crew:map  append-only -->` 那一整行插入，格式 `@code:<relpath>#<symbol>` (L{行號})。
🔴 只補**新的落點錨點**，不要把類別清單、方法簽章抄進 plan.md；🔴 不得整節取代，不得動別節。

#### 7c. 寫進度到 state.json（唯一狀態權威）

每完成一個角色就寫一次（中斷後 `--resume` 靠它續跑）：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" unit --slug {slug} \
  --skill plan-build --done {已完成角色數} --total {角色總數} --label 角色 \
  --remaining "{未完成角色，逗號分隔}" --evidence "{已產出的檔案或指令輸出}"
```

全部角色完成後收尾（`--clear` 清掉工作單元，代表沒有斷點）：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" unit --slug {slug} --clear
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" set --slug {slug} \
  --step build --status done --phase build --last-commit "$(git rev-parse HEAD 2>/dev/null)"
```

🔴 **禁止**在本 skill 寫 plan.md frontmatter 的 `verified_at_commit` / `verified_at` —— 剛改完程式碼就自己蓋章等於作廢。蓋章只有 `/plan-drift` 與 `/plan-close` 能做。

### 8. 偵測設定檔變更（僅回報，不落檔）

#### 8a 收集變更清單

來源：『更新狀態與指路錨點』一節 7a 的 `git diff --name-only` 輸出（唯一來源，不再有任何清單檔）。

#### 8b 比對設定檔模式

將收集到的檔案路徑逐一比對設定檔模式清單（13 種常見設定檔模式，如 mapper XML、application.yml、Dockerfile 等）。完整模式表見 plugin 根目錄 `references/deploy-sql-guide.md`（相對 SKILL.md 為 `../../references/deploy-sql-guide.md`）。

#### 8c 命中時的處置

命中的設定檔**只在對話回報**，列成「上線需一併更版」清單（見『回傳結果』一節的 📋 行），供使用者在部署時對照。

- 🔴 不建立任何 checklist 檔案（已廢除：它是 `deploy.sql` 與 git diff 的 derived view，會自己過期）。
- SQL 的部署步驟數屬狀態，寫進 `state.json`（由 `/plan` 的 db pass 以 `--deploy-total` 登記）；本 skill 若發現 `deploy.sql` 有增修，重新登記一次：
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" set --slug {slug} --deploy-total {Step 數}
  ```

**API 呼叫**：0 次（僅本地操作，Notion 同步交給 `/plan-sync` 或 `/plan-close`）

### 9. 退出驗證（強制，不可跳過）

Leader 在回傳結果前，逐項檢查以下退出條件：

#### 自動驗證項目

| # | 檢查項目 | 驗證方式 | 失敗處理 |
|---|---------|---------|---------|
| E0 | 狀態已更新 | `crew-state.py validate --slug {slug} --expect-phase build` exit 0 | 依訊息修正後重跑；仍失敗 → `crew-state.py rebuild --slug {slug}` |
| E1 | 所有 Teammate 都已完成 | 確認每個 Teammate 回報了完成訊息，且 `work_unit` 已 `--clear` | 等待或重試未完成的 Teammate（`--resume` 可續跑） |
| E2 | 變更清單取自 git | `git diff --name-only` 與 `git status --porcelain` 有本次產出 | 產出為空 → Teammate 實際沒寫檔，回到 E1 處理 |
| E3 | 產出檔案真的存在 | 對 git 列出的每個路徑用 `ls` 或 Read 確認 | 列出缺失檔案，要求使用者決定：重試 / 移除 |
| E4 | 無編譯錯誤（若可驗證） | 若專案有 build 指令（mvn compile / gradle build），執行一次 | 顯示錯誤訊息，標記 ⚠️ 但不阻擋 |
| E5 | 錨點有效性（檔案／符號還在） | `check-spec-drift.py --spec .spec/{slug}/plan.md --format json`，看 D1／D2 | 列出失效錨點，標記 ⚠️ 並建議跑 `/plan-drift`；**不阻擋** |
| E6 | `AC-n` 驗收條件有對應程式碼 | 讀 plan.md「驗收條件」節的 `AC-n`，grep 本次產出檔案確認有相關實作 | 列出無對應的 `AC-n`，標記 ⚠️ |
| E7 | `deploy.sql` 校驗（若 DB_REQUIRED != false） | 見下方 E7 詳細邏輯 | 見下方 E7 詳細邏輯 |

> **測試已跳過時**：若使用者選否（不含測試），E6 仍執行但不檢查測試檔案，驗證結果中標記「測試已跳過」。

#### E5／E6 詳細邏輯（錨點有效性，維持 WARN 不阻擋）

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check-spec-drift.py" \
  --spec .spec/{slug}/plan.md --format json
```

- **一律不加 `--strict`、不在本 skill 阻擋**：剛產完碼時符號正在流動（方法還會改名、檔案還會搬），此刻升級為硬關卡的誤殺率最高。硬關卡在 `/plan-close`（那時程式碼已穩定）。
- exit `0` → E5 ✅；exit `1`（有 D1／D2 FAIL）或 `2`（僅 WARN）→ E5 ⚠️，逐條列出 `anchor` 與 script 給的「修法：」原文，建議跑 `/plan-drift`。
- exit `3` 是**環境問題**（非 git 工作區、檔案讀不到）→ 標記「本次未檢查」，🔴 不得說成「有漂移」，也不得說成「檢查通過」。
- 🔴 本步驟**不寫** `verified_at_commit`；`--fix` 也不在這裡跑（機械修屬 `/plan-drift`）。

#### E7 詳細邏輯（deploy.sql 校驗，不重組）

`deploy.sql` 是**唯一 SQL 事實來源**，由 `/plan` 的 db pass 產出。本 skill 只**校驗**，🔴 **不得**再去掃描任何文件的 SQL 區塊重新組裝（那正是同一份 DDL 出現三四次的根源）。

1. 讀 plan.md `D-1 [spec] 範圍判斷` 的 `DB_REQUIRED`
2. `false` 或查無 → 跳過（`state.json` 的 `steps.db.status` 應為 `skipped`）
3. `true` 或 `insert-only` → 逐項校驗 `.spec/{slug}/deploy.sql`：
   - [ ] 檔案存在且非空 —— 不存在 → 🔴 BLOCK，要求先跑 `/plan db`（**不要**自己生一份）
   - [ ] 有 `-- Step N：{描述}` 分段，Step 數與 `state.json` 的 `deploy.steps_total` 一致 —— 不一致 → 用 `crew-state.py set --deploy-total` 更正
   - [ ] 有 Rollback 註解段
   - [ ] plan.md 的 `@sql:deploy.sql#{table}` 錨點都指得到（由 E5 的 script 一併檢查，對應 D5）
   - [ ] 本次產出的程式碼引用的表／欄位，`deploy.sql` 裡都有 —— 缺漏 → ⚠️ 並列出，請使用者決定補 SQL 或改碼

檔案格式（Step 分段、驗證 SQL、Rollback 註解段）見 plugin 根目錄 `references/deploy-sql-guide.md`（相對 SKILL.md 為 `../../references/deploy-sql-guide.md`）。

#### 驗證結果分級

- **🔴 BLOCK**（E0, E1, E2, E3, E7 當 DB_REQUIRED=true 且 deploy.sql 缺失）：必須解決後才能標記完成
- **⚠️ WARN**（E4, E5, E6, E7 其餘情況）：在回報中提醒，不阻擋

#### 驗證結果格式

只在對話輸出（🔴 不落檔；事件流由 `state.json` 的 `history` 承接）：

```
退出驗證結果：
  ✅ E0 state.json 驗證通過（phase=build）
  ✅ E1 所有 Teammate 完成
  ✅ E2 git 變更清單：12 個檔案
  ✅ E3 所有檔案存在
  ⚠️  E4 編譯未驗證（專案無標準 build 指令）
  ⚠️  E5 錨點 1 筆失效：@code:.../LoginService.java#lock（D2 符號不在檔內）→ 建議 /plan-drift
  ⚠️  E6 AC-3「支援匯出 Excel」無對應程式碼
  ✅ E7 deploy.sql 校驗通過（2 個 Step，Rollback 段齊全）

  結論：可繼續，但建議處理 E6 後再進 plan-verify
```

### 10. 回傳結果

測試相關兩處依使用者選擇填寫：**選是（含測試）** 用斜線前變體，**預設（跳過測試）** 用斜線後變體，已於行內以 `／` 標出。

```
程式碼產生完成！

📁 變更檔案（git diff --name-only）：N 個
📊 統計：N 個後端 + M 個前端{ + K 個測試 ／ 跳過測試時改為「（測試已跳過）」}

已完成：
  {✅ db-engineer       — Migration SQL + 索引建議 + 效能報告}
  ✅ backend-engineer  — N 個檔案（POJO/Mapper/Service）
  ✅ api-engineer      — N 個檔案（Controller/DTO）
  {✅ frontend-engineer — M 個檔案（JSP/JS/CSS）}
  ✅ test-engineer     — K 個檔案（測試） ／ 跳過測試時改為「⏭️ test-engineer    — 已跳過」
  {✅ API 契約確認 — 一致}

{📋 上線需一併更版的設定檔（{N} 個）：逐檔列出路徑，不落檔}
{🗄️ 部署 SQL：deploy.sql 校驗通過（{N} 個 Step）}
{🧭 指路錨點：已在 plan.md 補 {K} 條}
{💡 提示：可用 /plan-sync 同步到 Notion，或等 /plan-close 結案時統一同步}

⚡ 建議執行 /clear 再進行後續步驟（review / verify / close）
   原因：build 已消耗大量 context，後續步驟全部從 .spec/ 磁碟讀取，不需要本次對話歷史

後續可使用：
  • /plan-verify  — 驗收驗證
  • /plan-review  — 多角色審查
  • /plan-close   — 結案並同步 Notion
```

> 設定檔變更（📋）那行只在『偵測設定檔變更（僅回報，不落檔）』一節命中模式時顯示。

---

## DB MCP 提示詞模版

> 完整的 DB MCP 提示詞模板見 plugin 根目錄 `references/build-prompts.md`（相對 SKILL.md 為 `../../references/`）的「DB MCP 提示詞模版」段落。

『判斷團隊組成』一節依 `tool_probe(tool_kind=database)` 檢查 DB 工具可用性後，根據結果決定是否加入 DB 工程師：
- **已安裝**：加入「成員 0：DB 工程師」（`{"model": "opus"}`）；Subagent 模式（同樣 `model: opus`）嵌入 `{db_mcp_instruction}`
- **未安裝**：不加入 DB 工程師；`{db_mcp_instruction}` 替換為空字串

---

## 何時不用

- 編譯專案（mvn / npm build）→ 直接跑 build 指令，非本 skill
- 尚無規劃內容（plan.md 只有骨架）→ 先執行 `/plan`
- 產完後要審查 → `/plan-review`；要驗收 → `/plan-verify`
- 錨點失效要修 → `/plan-drift`（本 skill 只回報 WARN，不修）
- 只要拆分 commit → 個人 `git-smart-commit`（本 skill 只產碼）

---

## Gotchas

- **有獨立 worker 時 Leader 不寫 code**：避免與 worker 同時修改相同檔案。只有 Host adapter 明確降級為 inline 時，主 Agent 才能按 `delegate_write` 的單一角色 scope 依序實作。
- **Teammate 之間的檔案衝突**：雖然設計上各 Teammate 負責不同目錄，但 API 工程師的 DTO 和後端工程師的 Entity 可能放在相近的 package 下。如果兩者同時寫同一個 DTO 類別，後寫的會覆蓋先寫的。確保在 prompt 中明確劃分 DTO 歸屬。
- **Host 沒有 parallel capability**：不是錯誤；依 `host-capabilities.md` 退化為序列委派，正確性不可依賴平行。
- **現有程式碼範本的選擇很關鍵**：給 Teammate 參考的 POJO/Mapper/Service 範本如果選到非典型的（如有特殊 annotation 或非標準命名），Teammate 會學到錯誤風格並複製到所有產出中。優先選最簡單、最標準的範本檔。
- **DB MCP Teammate 超時**：DB 工程師如果查詢的表很多或 DB 回應慢，可能花很長時間。設定合理的任務範圍（只查本功能相關的表，不要全表掃描）。
- **Host-specific worker lifecycle**：清理由 adapter 負責；核心 Skill 不直接呼叫 Team lifecycle 指令。續跑依 `state.json.work_unit`，不要靠 Host session 猜進度。
- **產完碼不准自己蓋章**：`verified_at_commit` 是「文件與程式碼對得上」的承諾。剛動完程式碼的 skill 蓋自己的章，這個欄位就失去意義。本 skill 只回報 E5 的錨點狀態，蓋章交給 `/plan-drift` 或 `/plan-close`。
- **E5 的 WARN 不是可以無視**：不阻擋是因為此刻誤殺率高，不是因為不重要。同一批失效錨點到 `/plan-close` 會變成硬關卡（D1／D2 FAIL 直接擋結案），順手在 `/plan-drift` 修掉最省事。
- **deploy.sql 只有一份、只由 db pass 產**：本 skill 若「找不到 SQL 就自己掃文件組一份」，同一份 DDL 立刻變成兩份且會各自漂移。缺就擋下來要求跑 `/plan db`。

參考 `examples/leader-delegation.md` 了解 Leader 如何有效分配任務和協調 Teammate。

---

## 邊界情況

- **arch pass 未完成**（`state.json` 的 `steps.arch.status` 非 done／skipped）：**hard block** — 停止流程，要求使用者先執行 `/plan arch`
- **`deploy.sql` 不存在但 DB_REQUIRED=true**：**hard block** — 要求先跑 `/plan db`，🔴 不自行組裝 SQL
- **`check-spec-drift.py` 回 exit 3**：標「本次未檢查錨點」＋原因，不阻擋、不改判為漂移
- **無平行委派能力**：自動退化為序列委派，不阻擋
- **--dry-run 模式**：不建立任何檔案，只展示清單和關鍵片段
- **Teammate 失敗**：提供選項：重試 / 跳過 / 終止
- **API 契約不一致**：以 API 工程師為準，其他成員調整
- **避免重疊寫入執行單元**：同一工作階段若已有未完成的可寫 role，先依 `state.json.work_unit` 續跑或收斂，再啟動新的實作單元
- **僅後端模式**：依角色數使用 `delegate_write`（實作者 `model: opus`）或序列委派
