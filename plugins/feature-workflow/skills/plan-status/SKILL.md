---
name: plan-status
description: 列出 .spec/ 目錄中所有活躍與已完成的任務（純本地操作，不呼叫 Notion）。當使用者提到 /plan-status、「.spec 任務狀態」、「CREW 任務列表」時觸發此 Skill。
---

# plan-status — 查看任務狀態

純本地操作。狀態一律由 `crew-state.py` 讀寫（`.spec/{slug}/state.json` 是唯一權威），本 skill 只負責呈現與清理。**不呼叫任何 Notion API**。

> **前置檢查**：參照 plugin 根目錄 `references/prerequisites.md`（相對 SKILL.md 為 `../../references/`）檢查專案指令是否存在。

---

## 使用方式

```
/plan-status                 # 列出所有任務（含已結案）
/plan-status --active        # 只列出未結案的任務
/plan-status --detail        # 詳細模式：每個任務的階段進度與檢查結果
/plan-status --cleanup       # 清除超過 30 天（預設）的已完成任務
/plan-status --cleanup=<N>   # 清除超過 N 天的已完成任務，例：--cleanup=60
/plan-status --park <slug>   # 擱置指定任務
/plan-status --unpark <slug> # 恢復指定任務
/plan-status --migrate <slug> # 把 v1 舊結構任務機械搬移到 v2（過渡期，見 legacy-v1.md）
```

---

## 流程

### 1. 掃描任務

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" list --all --format json
```

`--active` 時去掉 `--all`（script 即不含已結案任務）。回傳每筆含 `slug`／`name`／`type`／`phase`／`closed`／`parked`／`inferred`／`updated`／`stale_days`／`next`。

- 輸出為空陣列 → 提示先執行 `/plan-start`
- 非 0 exit（例：取不到檔案鎖）→ 照 script 訊息明說「無法讀取任務狀態」並附原因，不要改用猜測

**不要自行掃 frontmatter 或重建索引**：`crew-state.py list` 即時掃 `.spec/*/state.json`，沒有快取可漂移。

### 2. 格式化輸出

依 `closed` / `parked` 分成三組。`inferred` 為 true 的任務在該列尾標 `⚠️ 推測`。

```
📋 任務狀態

## 進行中（{N} 個）

| # | 類型 | 名稱 | 階段 | 停滯 | 下一步 |
|---|------|------|------|------|--------|
| 1 | 🔧 feature | 推播標籤查詢 | build | 3 天 | /plan-build --resume |
| 2 | 🐞 bug | SSO 登入錯誤 | verify | 1 天 | /plan-verify |

## 擱置中（{N} 個）

| # | 類型 | 名稱 | 擱置時階段 | 擱置原因 |
|---|------|------|-----------|---------|
| 1 | 🔧 feature | 資料匯出 | db | 等 DBA 回覆 |

## 已完成（{N} 個）

| # | 類型 | 名稱 | 完成日期 |
|---|------|------|---------|
| 1 | 🔧 feature | 訂閱推播統計 | 2026-03-10 |
```

#### 詳細模式（--detail）

額外唯讀讀取 `.spec/{slug}/state.json`（**只讀，不寫**）取 `steps`、`work_unit`、`results`、`resume_hint`：

```
### 1. 🔧 推播標籤查詢（push-tag-query）
   階段：build｜分支：feature/push-tag-query｜Notion：{notion.page_id 有值時附連結，無則「未建立」}
   步驟：start ✅  spec ✅  db ⏭️ 跳過(DB_REQUIRED=false)  arch ✅  build ⏳ 3/7  security ⬜  verify ⬜  review ⬜  close ⬜
   結果：verify —｜review —｜security —
   下一步：/plan-build --resume（build 中斷於 3/7 檔案）
```

步驟圖示對應 `steps.{name}.status`：`done` ✅／`in_progress` ⏳／`skipped` ⏭️（附 `reason`）／`failed` ❌／`pending` ⬜。

### 3. 擱置／恢復

一律交給單一寫者，**不要自己改任何檔案**：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" park   --slug <slug> --reason "<原因>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" unpark --slug <slug>
```

`--reason` 為選填；使用者沒說原因就不帶。script 的輸出（`✅ {slug} 已擱置…` / `✅ {slug} 已復工｜下一步：…`）照實轉述即可。擱置中的任務不會出現在 session 開場提醒。

### 4. 清理模式（--cleanup）

未指定 `<N>` 時預設 30 天；天數從 `steps.close.at`（結案時間）算起。

```
以下已完成任務超過 30 天：

| # | 名稱 | 完成日期 | 天數 |
|---|------|---------|------|
| 1 | 訂閱推播統計 | 2026-02-10 | 34 天 |

是否清除？（會刪除 .spec/ 目錄，Notion 資料不受影響）[y/N]
```

確認後才動手（**未確認一律不刪**）：

1. 刪除 `.spec/{slug}/` 目錄
2. 若該任務已於 `/plan-close` 用 `git add -f` 加入版本控制（見 plan-close 的 Gotchas），一併 `git rm -r --cached .spec/{slug}/` 取消追蹤；`plan-start` 產生的 `.gitignore` 規則不需還原或修改

### 5. 遷移模式（--migrate，過渡期）

把 v1 舊結構任務搬到 v2。判定與適用情境見 `../../references/legacy-v1.md`
（**先讀它再動手** —— 大多數 v1 任務更適合「照舊跑完」而不是遷移）。

🔴 **只做機械搬移，不做語意轉換。** 這條沒有例外。

**動手前先確認**，列出將搬走哪些檔案，使用者回覆才執行：

```
準備遷移 push-tag-query（v1 → v2）：

  搬到 archive/：spec.md(313行) db.md(99行) arch.md(583行) log.md(254行) files.md(121行)
  合併：db.sql + deploy.sql → deploy.sql（去重）
  轉換：README.md frontmatter → plan.md frontmatter + state.json
  新建：plan.md（六章節骨架，內容留 TODO 佔位由你補）

原文一個字都不會改。是否執行？[y/N]
```

確認後依序執行：

1. 建 `.spec/{slug}/archive/`，**原封搬入** `spec.md`／`db.md`／`arch.md`／`log.md`／`files.md`／`review.md`／`security.md`／`verify.md`（用 `git mv` 或 `mv`，不改內容、不刪除）
2. `db.sql` 與既有 `deploy.sql` 合併去重 → 單一 `deploy.sql`；衝突時**保留兩者並標注**，讓人決定，不要自己挑一個
3. `README.md` frontmatter 的身分欄位 → `plan.md` frontmatter；狀態欄位 → `crew-state.py init` ＋ `set`（🔴 不手寫 JSON）
4. 建 `plan.md` 六章節骨架（與 `/plan-start` **完全相同**），每個內容章節放一行佔位：
   `TODO(migrate): 從 archive/{來源檔} 補` —— 標明去哪找原文
5. 回報搬了什麼、哪幾節待補

🔴 **禁止**用 LLM 把 archive 的內容摘要、壓縮或改寫進 `plan.md`。理由見 `legacy-v1.md`
「為什麼不做自動語意轉換」——壓縮不可驗證，且會幻覺出從未做過的決策。

**已結案的 v1 任務不遷移**（`_index.md` 標已完成，或無進行中跡象）：直接整包搬進
`archive/` 即可，不必建 `plan.md`。

---

## 何時不用

- 查 background task 執行狀態 → 非本 skill
- 查 Jira 單狀態 → jira-from-pm 或 jira MCP
- 要推薦下一步該做什麼 → /plan-next
- 看規劃文件內容 → /plan-browse
- 文件與程式碼是否同步 → /plan-drift

---

## Gotchas

- **狀態不自己寫**：park／unpark／階段變更全部走 `crew-state.py`。本 skill 若直接編輯 `state.json` 或 plan.md frontmatter，會繞過原子寫入與併發鎖，是欄位漂移的來源。
- **壞掉的 state.json 會被靜默略過**：`list` 掃不到的目錄不會出現在輸出。若使用者說「有個任務不見了」，跑 `crew-state.py rebuild --slug <slug>` 重建，重建結果會標 `inferred`。
- **「不擱置已結案任務」要本 skill 自己擋**：`crew-state.py park` 不檢查 `closed`，對已結案任務照樣寫入成功。擱置語意是「稍後繼續」，已結案的沒有繼續的必要 → 呼叫 `park` 前務必先用 `list --all` 確認該任務 `closed` 為 false，是 true 就拒絕並說明理由。
- **`--cleanup` 是刪檔操作**：一定要先列出清單、取得使用者明確確認，且只刪已結案且超期的任務。

---

## 邊界情況

- **`.spec/` 不存在或無任務**：提示先執行 `/plan-start`
- **Git branch 已刪除**：詳細模式顯示 `resume_hint.branch` 但標「分支不存在」
- **`--park`／`--unpark` 指定不存在的 slug**：script 回 exit 1，照其訊息回報並列出可用任務
- **`--unpark` 指定非擱置任務**：script 會直接把 `parked` 設為 null（冪等操作、exit 0）；輸出時說明該任務原本就未擱置
