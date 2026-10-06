# plan-* 共用邏輯

`/plan-start` 與 `/plan`（spec／db／arch 三個 pass）等 `plan-*` skill 共用以下邏輯。

`.spec/{slug}/` 只有三種產物：

| 產物 | 角色 |
|------|------|
| `plan.md` | 給人與 LLM 讀的**唯一文件**（≤100 行） |
| `state.json` | 機器可讀的流程狀態，**唯一權威**，單一寫者 `crew-state.py` |
| `deploy.sql` | **唯一 SQL 事實來源**，給 DBA 執行（含 rollback 註解段） |

> **設計靈魂**：文件只寫**程式碼裡看不到的東西** —— 需求、決策與理由、被否決的方案、驗收條件、已知取捨。
> 「是什麼」（欄位清單、方法簽章、類別清單、DDL、檔案清單）一律用錨點指過去，**不抄寫**。

---

## plan.md 章節契約

### 骨架（由 `/plan-start` 用 Write 建立一次）

```markdown
---
slug: {slug}
name: {任務名稱}
type: feature
verified_at_commit:
verified_at:
drift_policy: normal
---

# {任務名稱}

## 目標與範圍        <!-- crew:goal owner=spec -->

## 驗收條件          <!-- crew:ac   owner=spec -->

## 決策紀錄          <!-- crew:dec  append-only -->

## 已知取捨與風險    <!-- crew:risk append-only -->

## 指路              <!-- crew:map  append-only -->

## 檢查報告摘要      <!-- crew:rep  append-only -->
```

frontmatter 只留**身分**與**漂移**兩類欄位：`slug` / `name` / `type`（`feature` | `bug`）／
`verified_at_commit` / `verified_at` / `drift_policy`（`strict` | `normal` | `off`，預設 `normal`）。

- 流程階段、分支、Notion 頁面 ID 等**一律在 `state.json`**，由 `crew-state.py` 讀寫；任何 skill 都不得把這些欄位手寫進 plan.md frontmatter。
- `verified_at_commit` / `verified_at` 建立時留空，**只有** `/plan-drift` 與 `/plan-close` 在漂移檢查通過後寫入。

### 各節可以寫什麼

| 章節（錨點） | owner | 可以寫 | 禁止寫 | 上限 |
|---|---|---|---|---|
| 目標與範圍 `crew:goal` | spec | 為何做、In Scope／Out of Scope | API 表、欄位清單、類別名 | 12 行 |
| 驗收條件 `crew:ac` | spec | `- [ ] AC-1 {可機器驗證的一句話}` | 實作步驟、selector | 15 行 |
| 決策紀錄 `crew:dec` | 全階段 | `- D-n [階段] 決策｜理由｜被否決方案＋否決理由` | DDL、方法簽章、Mermaid | 30 行 |
| 已知取捨與風險 `crew:risk` | 全階段 | 明知的技術債、邊界外情境 | 已修掉的問題 | 8 行 |
| 指路 `crew:map` | 全階段 | 錨點（見下方「錨點語法」） | 把指到的內容抄一份 | 10 行 |
| 檢查報告摘要 `crew:rep` | review／security／verify | `- [日期] {類型} {結論}｜🔴n 🟡n` | 逐條發現 | 6 行 |

全檔目標 **≤100 行**（典型 70–85 行）。逼近上限時**壓縮既有條目或 supersede**，不要另開檔案。

### 寫入紀律（四層防覆蓋，所有 skill 與 agent 都必須遵守）

**前提**：骨架由 `/plan-start` 用 Write 建立**一次**，之後**一律用 Edit 對錨點註解插入**。
🔴 嚴禁用 Write 整檔改寫、嚴禁把整個章節當 `old_string` 取代 —— 那會靜默吃掉同節其他階段寫的條目。

1. **一節一 owner** —— 只有「目標與範圍」「驗收條件」可被改寫，且只有 spec pass 能碰。
2. **共享節 append-only、以條目為單位** —— dec／risk／map／rep 四節只准新增條目。插入點固定是**該節錨點註解那一整行**（全檔唯一），`new_string` = 原行 ＋ 換行 ＋ 新條目：

   ```text
   old_string:  ## 決策紀錄          <!-- crew:dec  append-only -->
   new_string:  ## 決策紀錄          <!-- crew:dec  append-only -->
                - D-4 [db] 鎖定計數存 Redis｜理由：多節點需共享計數｜否決：in-memory（會漏算）
   ```

   工具層面因此沒有「取代整段」這個動作，新條目排在該節最前面（最新在上）。
3. **改變主意用 supersede，不刪舊條目** —— `- D-7 [arch] 取代 D-3：…（原因：…）`。決策史正是這份文件唯一不會過期的價值。
4. **每條自帶 `[階段]` tag** —— `[spec]` `[db]` `[arch]` `[build]` `[security]` `[verify]` `[review]` `[close]`，後階段一眼看出不是自己寫的。

`AC-n` 與 `D-n` 是 plan.md ↔ state.json 的 join key：**全檔遞增、不重用、不重編號**。

### 錨點語法

正規形 `@code:<relpath>[#<symbol>]` 與 `@sql:deploy.sql#<table>`：

```text
- D-5 [arch] 鎖定計數改走 Redis｜理由：多節點 in-memory 會漏算｜否決：本機快取
  → `@code:src/main/java/com/x/service/LoginAttemptService.java#recordFailure` (L88)
- 表結構見 `@sql:deploy.sql#login_attempt`
```

- 預設用 **T2（路徑＋符號）**；只有整檔級別的指路才用 T1（僅路徑）。
- **`(L88)` 刻意放在 token 外面** —— 行號只是給人看的提示，`check-spec-drift.py` 只回報新行號、不會 FAIL。符號名在寫程式當下就在上下文，不需要算行號。
- 極少數關鍵不變量可用 T3：`@code:<path>#<symbol>@sha1:ab12cd`（內容指紋，僅 WARN）。
- 逃生閥：行內 `<!-- drift-ignore: D2 reason=已改用新介面 -->`（`reason` 必填）；整份關閉用 frontmatter `drift_policy: off`。

---

## 定位活躍任務

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" list --format json
```

1. 指令帶 slug → 直接用
2. `git branch --show-current` 對得上某任務的分支或 slug → 自動選定
3. 只有一個未結案任務 → 自動選定
4. 多個未結案 → 列出讓使用者選（**不得自行挑一個**）
5. 清單為空 → 提示先執行 `/plan-start`
6. 選定的任務 `parked` 非 null → 先問是否 `/plan-status --unpark <slug>`，確認後才繼續

選定後讀 `.spec/{slug}/plan.md` 取得 `name`、`type` 與既有章節內容。
**流程位置一律以 `state.json` 為準**，不要用「哪些檔案存在」反推階段。
`list` 讀不到任務 → `crew-state.py rebuild --slug <slug>` 自我修復（結果會標 `inferred`）。

---

## 讀取專案上下文

### 專案指令

依共用 `host-capabilities.md` 的 `project_instructions` 讀取 `AGENTS.md`／`CLAUDE.md`，取得技術棧、架構模式、分層規則、命名慣例。

### 技術棧資訊

技術棧 ID 從設定目錄的 `projects/{sanitized-repo-id}.md` 的 `stack` 欄位取得（**不在 plan.md 另存一份副本**），
再依 plugin 根目錄 `references/config-resolver.md` 的第 3 層載入邏輯讀取定義：

- 內建技術棧 → `stacks/_builtin.md`
- 自訂技術棧 → `stacks/{id}.md`

### 現有程式碼參考

使用 Glob/Grep 掃描與需求相關的現有程式碼（1-2 個 Controller、Service、Entity），了解 API 風格、命名慣例。

### 規範檔案

讀取可用的規範檔案：

- `~/.claude/rules/database.md`（DB 設計時）
- `~/.claude/rules/design-patterns.md`（架構設計時）
- `~/.claude/rules/java-performance.md`（效能相關）

---

## 共用 Gotchas

- **`D-1 [spec] 範圍判斷` 條目是 plan-build 的入口**：`FRONTEND_REQUIRED` 和 `DB_REQUIRED` 的值直接決定 plan-build 的團隊組成。格式錯誤（如用中文「是/否」而非 `true/false`）會 fallback 到預設值。它是決策紀錄的第一條，**不可刪除**；要改判斷用 supersede（`D-n [階段] 取代 D-1：…`）。
- **委派的 model 目標**：prompt 中只寫「使用 Opus」不算。Capability request 必須帶結構化 `model`；Host 工具對映與安全降級見 `host-capabilities.md`，角色模型政策見 `model-policy.md`。
- **plan.md 沒有 `.bak` 回退**：舊流程「覆蓋前備份 `{file}.bak`」已不適用 —— plan.md 只能增量 Edit，寫壞了要靠 `git diff` 或 `git checkout` 回退，不是靠備份檔。
- **重跑某個 pass 不等於重寫該節**：重跑時先讀既有條目，只補新的或用 supersede 修正；把同一件事再寫一條新的 `D-n` 是可接受的，把舊條目刪掉不是。
- **`.spec/` 預設在 `.gitignore` 內**：要進版控由 `/plan-close` 以 `git add -f` 處理，其他 skill 不要擅自改 `.gitignore` 規則。

## 共用邊界情況

- **`.spec/` 目錄不存在**：提示先執行 `/plan-start`
- **找不到活躍任務**：提示先執行 `/plan-start`，或用 `/plan-status` 確認任務清單
- **`state.json` 缺失或壞掉**：跑 `crew-state.py rebuild --slug <slug>`，並在回報中標「狀態為推測」
- **前置階段未完成**：提示建議先執行的指令，但不強制阻擋（`crew-state.py next` 會給出正解）

---

## Notion database_id 解析

### 使用場景

所有需要呼叫 `post-page` 建立 Notion 頁面的 Skill 都需要此解析：

- plan-start（建立任務頁面）
- plan-sync（補建 Notion 條目）
- plan-close（同步到知識庫：功能設計庫 / Bug 知識庫）

### 解析步驟

1. 從 config.md 讀取目標資料庫的 Data Source ID
2. 呼叫 `retrieve-a-data-source`，傳入 `data_source_id`
3. 從回傳結果的 `parent` 欄位中取得 `database_id`
4. 使用 `database_id` 作為 `post-page` 的 `parent.database_id`

### 快取策略

- 同一 Skill 執行期間，同一個 Data Source ID 只解析一次
- 解析結果不持久化到檔案（避免 database_id 變更時過期）

### 錯誤處理

- `retrieve-a-data-source` 失敗 → 嘗試直接用 Data Source ID 作為 database_id（向下相容）
- 回傳結果中無 `parent.database_id` 欄位 → 同上

---

### 第 4 層：產品知識庫（需要產品操作知識時）

從 `projects/{id}.md` 的 `product_id` 欄位取得產品 ID。Resolution precedence：

1. 專案 repo `.crew/products/{product_id}.md`
2. plugin `products/{product_id}.md`
3. 都不存在 → 通用模式

project-local knowledge 優先，用來承載公司／客戶／環境特有的路由、helper、元件 recipe 等資訊；公開 plugin bundle 只保留可公開、可泛用的產品知識。

取得：頁面導航地圖、常用 Selector、i18n 對照表、特殊操作 Recipe、API 格式。

### 第 4.1 層：產品級記憶（需要驗證記憶時）

有 product_id 時，產品級記憶依序解析：

1. 專案 repo `.crew/products/{product_id}-memory.md`
2. plugin `products/{product_id}-memory.md`
3. 都不存在 → Layer 3 為空

### 第 4.2 層：E2E framework adapter（需要產生／執行 E2E 時）

若 `projects/{id}.md` 有 `e2e_adapter`，依 `references/e2e-contract.md` 解析：

1. 專案 repo `.crew/adapters/{e2e_adapter}.md`
2. plugin `adapters/{e2e_adapter}.md`
3. 找不到 → generic-playwright

### projects/{id}.md 選填欄位

| 欄位 | 必要性 | 說明 |
|------|--------|------|
| product_id | 選填 | 指向 project-local / plugin product knowledge |
| e2e_adapter | 選填 | E2E framework adapter ID |
| e2e_workspace | 選填 | E2E repo 相對於受測 application repo root 的路徑 |
| e2e_profile | 選填 | E2E 測試預設 Profile ID（不得存 secret） |
| e2e_command | 選填 | 在 E2E workspace 內執行的 runner 指令 |

舊欄位 `e2e_repo` 僅作 read compatibility；新設定使用 flat `e2e_*` contract。完整規則見 `references/e2e-contract.md`。
