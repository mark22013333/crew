# 團隊組成判斷規則

> **兩個資料來源，不要混用**：
> - **流程與身分** → `.spec/{slug}/state.json`（唯一權威，單一寫者 `crew-state.py`）：
>   `type`（`feature` | `bug`）、`phase`、`steps.{步驟}.status` 與 `.reason`、`inferred`。
> - **範圍判斷旗標** → `plan.md` 決策紀錄的 `D-1 [spec] 範圍判斷` 條目：
>   `TASK_TYPE`、`CHANGE_SCOPE`、`FRONTEND_REQUIRED`、`DB_REQUIRED`、`NEW_API` 等。
>
> `state.json` 的 `type` 只分 `feature` / `bug`（見 `crew-state.py init --type` 的選項），
> **不含**上列旗標；把旗標寫進 `state.json` 或 plan.md frontmatter 都是錯的。

## 判斷流程

### Step 1：讀取範圍判斷

```bash
# 任務身分與流程位置（唯一權威）
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" list --slug {slug} --format json
```

再從 `.spec/{slug}/plan.md`「決策紀錄」節讀 `D-1 [spec] 範圍判斷` 條目，取得 TASK_TYPE 和 CHANGE_SCOPE。
若 `D-1` 條目不存在或缺欄位 → 回退到基本判斷（只看 FRONTEND_REQUIRED × DB_MCP 兩個欄位）。
若 `D-1` 被後續條目 supersede（`D-n [階段] 取代 D-1：…`）→ **以最新那條為準**，不是第一條。

### Step 2：按 TASK_TYPE 分流

#### feature（新功能）
走完整判斷流程（Step 3）。

#### adjustment（功能調整）
按 CHANGE_SCOPE 決定：

| CHANGE_SCOPE | 團隊配置 | 模式 |
|-------------|---------|------|
| backend-only | 後端工程師 | Subagent |
| frontend-only | 前端工程師 | Subagent |
| api-only | 後端 + API 工程師 | 2 人 Team 或 2 個 Subagent |
| db-only | DB 工程師（需 DB MCP）| Subagent |
| full | 走 Step 3 完整判斷 | `parallel_delegate` 優先，否則序列 |

#### bugfix（修復）
預設：後端工程師（Subagent）
例外：若 CHANGE_SCOPE = full → 走 Step 3

#### refactor（重構）
預設：後端工程師（Subagent）
例外：若跨多層級 → 後端 + 測試（2 人 Team）

#### performance（效能優化）
預設：
- 若 DB_MCP_AVAILABLE → DB 工程師 + 後端（2 人 Team）
- 若無 DB MCP → 後端工程師（Subagent）

### Step 3：完整判斷（feature 或 CHANGE_SCOPE = full）

在基本判斷（FRONTEND × DB_MCP）之上，增加 NEW_API 判斷：

| FRONTEND | DB_MCP | NEW_API | 團隊組成 |
|----------|--------|---------|---------|
| true | true | true | 5 人（DB + 後端 + API + 前端 + 測試）|
| true | true | false | 4 人（DB + 後端 + 前端 + 測試）|
| true | false | true | 4 人（後端 + API + 前端 + 測試）|
| true | false | false | 3 人（後端 + 前端 + 測試）|
| false | true | true | 4 人（DB + 後端 + API + 測試）|
| false | true | false | 3 人（DB + 後端 + 測試）|
| false | false | true | 3 人（後端 + API + 測試）|
| false | false | false | 後端 + 測試（2 人 Team 或 Subagent）|

### Step 3.5：DB_REQUIRED 處理

`D-1 [spec] 範圍判斷` 條目可能包含 `DB_REQUIRED` 欄位，影響團隊組成和退出驗證。
若 `state.json` 的 `steps.db.status` 為 `skipped`（`reason` 通常是 `DB_REQUIRED=false`），
代表 db pass 已明確跳過，等同 `false`：

| DB_REQUIRED 值 | 團隊組成影響 | 退出驗證影響 |
|---------------|-------------|-------------|
| `true` | 加入 DB 工程師（若 DB MCP 可用） | 驗證 migration SQL 存在 |
| `insert-only` | **不加入** DB 工程師 | 退出驗證時強制產出 `deploy.sql`（E7） |
| `false`（預設） | 不加入 DB 工程師 | 無額外驗證 |

> **insert-only 的典型場景**：新增後台功能頁面需 INSERT auth_program / auth_menu（權限關聯），不需要 CREATE TABLE / ALTER TABLE，但部署時必須執行 INSERT SQL。這類 SQL 不需要 DB 工程師，但若沒有獨立 deploy.sql 檔案，上線時極易遺漏。

### Step 4：確認計畫

顯示判斷依據，讓使用者確認或覆寫：

```
🔍 探索官：scout（model: sonnet，唯讀）
📊 Teammate 配置：後端工程師（Subagent 模式，model: opus）

判斷依據（來源：plan.md D-1 範圍判斷｜state.json type=bug）：
  - TASK_TYPE = bugfix → 預設 Subagent
  - CHANGE_SCOPE = backend-only
  - FRONTEND_REQUIRED = false
  - NEW_API = false

需要調整嗎？（如需完整多角色配置，輸入角色調整）[Y/n]
```

## 模型配置

判斷出的**團隊人數與角色**不影響模型配置；模型只看「這個角色做什麼」。完整政策見共用
reference `model-policy.md`：

| 角色性質 | 對應角色 | 參數 | 可改正式程式碼 |
|---------|---------|------|----------------|
| 唯讀探索（掃結構、找相似功能、選風格範本、追呼叫關係、整理角色上下文、分析編譯／測試輸出） | 探索官 scout | `model: sonnet` | ✗ |
| 建立或修改正式程式碼 | DB／後端／API／前端／測試工程師 | `model: opus` | ✓ |

規則：

- 探索使用 `delegate_readonly`、實作使用 `delegate_write`；模型目標以結構化參數傳入（`model: sonnet` / `model: opus`），不寫在 prompt 文字裡。
- 探索先做、實作後做；同一個 agent 不能中途換模型，所以**探索與實作必然是不同 agent**。
- 不論只有 1 個實作角色或 5 個角色，這張表都一樣適用；Host 有 `parallel_delegate` 時平行，否則序列。

---

## Bug-workflow 相容

bug 型任務（從 `/bug-investigate` 進入，或 `/plan-start` 建立時選 bug）走的是**同一套**產物：
`plan.md` ＋ `state.json` ＋ 必要時 `deploy.sql`，只是 `state.json` 的 `type` 為 `bug`。
沒有另一份 bug 專用的規劃文件。

範圍判斷讀取優先順序：
1. `.spec/{slug}/plan.md` 決策紀錄的 `D-1 [spec] 範圍判斷`（若已被 supersede，取最新那條）
2. 無 `D-1` 但 `state.json` 的 `type` 為 `bug` → TASK_TYPE 視為 `bugfix`，CHANGE_SCOPE 從決策紀錄的 `[spec]`／`[arch]` 條目與根因所在層級推斷
3. 都推不出來 → 詢問使用者（**不要**用「哪些檔案存在」猜）
