---
name: plan-sync
description: 手動中途同步 .spec/ 目錄當前進度到 Notion（含 deploy.sql），按需使用、不在常規流程、任務尚未結案。當使用者提到 /plan-sync、「中途同步 spec 進度」、「同步 spec 進度到 Notion」時觸發此 Skill。
---

# plan-sync — 手動中途同步

將 `.spec/{slug}/` 目錄的當前進度同步到 Notion。用於需要在結案前查看 Notion 頁面、或與團隊成員分享進度的場景。**不在常規流程中**，按需使用。

> 同步範圍只有兩個檔：`plan.md`（唯一文件）與 `deploy.sql`（唯一 SQL 事實來源）。
> `state.json` 是本地流程狀態，**不同步 Notion**（Notion 只鏡射一個「開發階段」字串）。

> **v1 舊任務**：`.spec/{slug}/plan.md` 不存在 → 這是 v1 結構，依
> `../../references/legacy-v1.md` 的相容模式執行，並在開頭提示一次。
> 過渡期限定，到期本段連同該檔一併刪除。
---

## 設定目錄

依 plugin 根目錄 `references/config-resolver.md`（相對 SKILL.md 為 `../../references/`）的漸進式載入邏輯讀取設定。本 Skill 需要：
- **第 1 層**：`config.md`（Notion IDs）
- **第 2 層**：`projects/{repo-id}.md`（專案對應）

> **前置檢查**：參照 plugin 根目錄 `references/prerequisites.md`（相對 SKILL.md 為 `../../references/`）執行完整前置檢查（專案指令 + 設定目錄 + 專案註冊）。

解析 plugin root：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
[ -n "$CREW_PLUGIN_ROOT" ] || {
  echo "無法解析 plugin root"
  exit 1
}
```

後續所有 CREW script 都使用 `$CREW_PLUGIN_ROOT/scripts/...`，不得直接依賴 Host marketplace/cache path。

---

## 使用方式

```
/plan-sync                 # 同步當前任務的 plan.md + deploy.sql
/plan-sync plan            # 只同步 plan.md
/plan-sync sql             # 只同步 deploy.sql
```

---

## 流程

### 1. 定位活躍任務

依 plugin 根目錄 `references/plan-common.md`（相對 SKILL.md 為 `../../references/`）的「定位活躍任務」。
`type` 從 `.spec/{slug}/plan.md` 的 frontmatter 讀；Notion 頁面 ID 從 `.spec/{slug}/state.json` 的
`notion.page_id` **唯讀**取得（`crew-state.py list` 的 JSON 不含此欄位，別去那裡找）。

### 2. 檢查 Notion 頁面

若 `notion.page_id` 為空（例如 `/plan-start` 時 Notion 建立失敗）：
- 詢問使用者是否要補建 Notion 條目。
- 若是，執行與 `/plan-start` 的「建立 Notion 條目」步驟相同的建立邏輯。
- 若 `.spec/{slug}/.cache/intake.md` 存在，必須用其中的 `original_request` / `refined_request` 建立「📋 需求描述」intake prefix。
- 若 cache 不存在（舊任務）且無法從既有 Notion 內容恢復 original request，**不得猜原文**；詢問 Human 是否補上，或明確標記「原始需求不可恢復」。
- 建立後把頁面 ID 交給單一寫者寫回（🔴 不要手改 `state.json`）：

  ```bash
  python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" set --slug {slug} --notion-page-id {page_id}
  ```

### 3. 確定同步範圍

掃描 `.spec/{slug}/` 目錄。可同步的核心產物只有兩個檔；`.cache/intake.md` 若存在只是 offline recovery metadata，不算 workflow artifact：

```
可同步的產物：
  ✅ plan.md    → 📋 需求描述 ＋ 📐 技術規格 ＋ 📝 開發日誌
  ✅ deploy.sql → 🗄️ 資料庫設計 → 遷移 SQL

同步所有？[Y/n] 或輸入要同步的項目（plan / sql）
```

`deploy.sql` 不存在（`DB_REQUIRED=false`）→ 該列顯示 ❌ 並跳過，不是錯誤。
若使用者指定了子命令（如 `/plan-sync plan`），只同步指定項目。

### 4. 執行同步

**4-1. Fetch 現有頁面**（1 次 `notion-fetch`）

取得頁面現有內容，避免覆蓋其他區塊。

**4-2. 更新內容**（1 次 `notion-update-page` content）

將選定的產物寫入對應 Notion 區塊（區塊標題以 plugin 根目錄 `references/notion-page-template.md`，相對 SKILL.md 為 `../../references/`，的 5 區塊模板為準）：

| 本地來源 | Notion 區塊 |
|---------|------------|
| Feature：`plan.md`「目標與範圍」＋「驗收條件」 | 📋 需求描述中的 `### 目標與範圍` ＋ `### 驗收條件` |
| Bug：`plan.md`「目標與範圍」＋「驗收條件」 | 🔴 問題描述中保留 `### 原始通報` / `### 確認後問題描述`，在其後更新 spec projection |
| `plan.md`「決策紀錄」＋「已知取捨與風險」＋「指路」 | 📐 技術規格 |
| `plan.md`「檢查報告摘要」 | 📝 開發日誌 |
| `deploy.sql` 全文 | 🗄️ 資料庫設計 → 遷移 SQL |

- **Intake prefix immutable**：Feature 的 `### 原始需求` / `### 確認後任務描述`，以及 Bug 的 `### 原始通報` / `### 確認後問題描述`，都由 `/plan-start` intake 擁有；本 skill 不得用 plan.md 覆蓋。
- 若既有頁面缺 intake prefix 且 `.cache/intake.md` 存在 → 先用 cache 補回 original/refined，再更新 spec projection。
- 若既有頁面已有 intake prefix → 原文逐字保留，只更新 `### 目標與範圍`、`### 驗收條件`。
- **原樣搬運，不重寫**：plan.md 章節內容照抄，不要在同步時「順手潤稿」或補充 —— 那會讓 Notion 與 plan.md 講不同的話。
- 「指路」節的 `@code:` / `@sql:` 錨點照原文寫入，🔴 **不要**把錨點指到的程式碼展開貼進 Notion。
- 本 skill 只同步使用者選定的項目，且不建立「🚀 部署狀態」區塊（該區塊僅由 `/plan-close` 初始化）。
- Notion update 成功後重新 fetch/確認目前 type 對應的兩個 intake headings 都存在；若本次使用了 `.cache/intake.md`，確認成功後才刪除 cache。

**4-3. 更新 Properties**（1 次 `notion-update-page` properties）

「開發階段」屬性取自 `.spec/{slug}/state.json` 的 `phase`（**唯讀**；階段的唯一權威是 state.json，不是 plan.md）。
寫完後把鏡射結果記回狀態檔，讓下次同步知道 Notion 上目前顯示什麼：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" set \
  --slug {slug} --mirrored-status "{寫進 Notion 的開發階段字串}" --synced-now
```

### 5. 回傳結果

```
同步完成！

📊 Notion 頁面：{URL}
📄 已同步：plan.md（{已同步的章節}）、deploy.sql（{M} 個部署步驟）
📂 開發階段：{state.json 的 phase}
📊 Notion API 呼叫：{N} 次

提示：此為中途同步，結案時請使用 /plan-close 做完整同步。
```

---

## 何時不用

sync 組——本 skill 是「未結案的中途同步」；結案批次同步用 /plan-close；單一 bug 頁更新用 /bug-update。

- 要結案（最終同步）→ /plan-close
- 更新單一 bug 頁 → /bug-update
- 部署 SQL 執行回報 → /plan-deploy-confirm

---

## Gotchas

- **中途同步不更新知識庫**：`plan-sync` 只更新 Notion 任務頁面的內容和 Properties，知識庫同步是 `plan-close` 的工作。回傳結果中需明確提示「知識庫將在結案時同步」。
- **`notion.page_id` 為空時的模板選擇**：補建 Notion 條目時，需從 `plan.md` frontmatter 的 `type` 欄位（`feature` / `bug`）判斷套用哪個模板。若 frontmatter 解析失敗讀不到 `type`，應詢問使用者而非預設。
- **同步是單向的（本地 → Notion），但 intake prefix 例外**：spec projection 以 plan.md 為事實來源；`### 原始需求` / `### 確認後任務描述` 是 intake-owned persistent source，不得被 plan.md 覆蓋。
- **對應表兩處要一致**：`/plan-close` 也把 plan.md ＋ deploy.sql 同步到同一組 Notion 區塊。改本節的對應表時要同步確認 `plan-close` 的版本，否則同一份 plan.md 會在中途同步與結案同步落到不同區塊。

---

## 邊界情況

- **`notion.page_id` 為空**：引導補建 Notion 條目
- **plan.md 六章節都還是空的**：提示先執行 `/plan` 產出規劃內容
- **`state.json` 缺失或壞掉**：跑 `crew-state.py rebuild --slug {slug}`，並在回報中標「狀態為推測」
- **Notion 頁面內容與模板不符**：先保護現有原始需求內容；有 intake cache 時可補成新模板，沒有時不得猜原文，再嘗試模糊匹配其他區塊
- **Notion API 失敗**：顯示具體錯誤，建議檢查網路或稍後重試
