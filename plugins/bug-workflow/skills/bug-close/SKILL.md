---
name: bug-close
description: 修復 Bug 後從 Git diff 自動擷取修復細節並更新 Notion 任務追蹤頁面（僅限 bug 型任務）。當使用者提到 /bug-close、「關閉 bug」、「bug 結案並補修復細節」時觸發此 Skill。
---

# Bug Close — 結案並自動補齊修復細節

修復 Bug 並 commit 後，從 Git 自動擷取修改資訊，更新 Notion「任務追蹤工具」的 Bug 頁面，並在「Bug 知識庫」同步建立精簡條目。

---

## 前置條件

- 已使用 `/bug-start` 建立 Bug 條目（Notion「任務追蹤工具」中有狀態為「進行中」的 🐞 錯誤條目）
- 修復程式碼已 commit

> **前置檢查**：參照 plugin 根目錄 `references/prerequisites.md`（相對 SKILL.md 為 `../../references/`）執行完整前置檢查（專案指令 + 設定檔 + 專案註冊）。

---

## 流程

### 1. 從 Git 擷取修復資訊

依序執行以下指令：

```bash
# 當前分支
git branch --show-current

# 最近 10 筆 commit（供使用者選擇範圍）
git log --oneline -10

# 預設取最近 1 個 commit 的變更
git diff HEAD~1..HEAD --stat

# 完整 diff（用於摘要化）
git diff HEAD~1..HEAD
```

若使用者指定 commit 範圍（如 `HEAD~3..HEAD`），使用指定的範圍。

### 2. Merge 引導（Feature Branch → DEV）

結案前，若偵測到修復在 feature branch 上進行（同時滿足：當前分支是 Bug 的修復分支、屬於 feature/hotfix 分支、能取得 DEV 分支名稱），引導使用者 merge 回開發分支；條件不滿足或使用者選擇跳過則直接進入原有結案流程。完整判斷條件、互動式引導文案、執行步驟見 plugin 根目錄 `references/merge-guide.md`（相對 SKILL.md 為 `../../references/`）。

### 3. 搜尋對應的 Bug 條目

搜尋 Notion「任務追蹤工具」（Data Source ID 見設定檔）中符合條件的條目：

使用 `notion-search` 搜尋：
- 條件：狀態為「進行中」且任務類型包含「🐞 錯誤」

同時取得 Git Repo 識別碼（從 `git remote get-url origin` 解析），用於輔助篩選同一專案下的 Bug。

優先匹配邏輯：
1. 若「修復分支」欄位與當前 Git branch 完全匹配 → 自動選定
2. 若有多個候選，優先顯示與當前 Git Repo 所屬專案相關的條目
3. 若有多個候選 → 列出清單讓使用者選擇
4. 若無候選 → 提示使用者先用 `/bug-start` 建立

### 3.5 綁定 Bug Runtime State + intake recovery

取得選定 Notion page ID，解析 plugin root：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" list --all --format json
```

找出 `state.notion.page_id == 目前 Bug page id` 的 `{slug}`：

- 唯一匹配 → 確認 `type=bug`，後續 UAT/close gate 全部使用此 slug。
- 找到多筆 → **BLOCK**，列出候選，不得猜。
- 找不到 → **BLOCK**；`/bug-close` 需要 deterministic state/UAT gate，不得只靠 Notion 結案。

綁定後，若 `.spec/{slug}/.cache/intake.md` 存在，先執行 `../../references/intake-refinement.md`「Bug intake recovery preflight」：

- 保留既有頁面內容。
- 補回 intake prefix / 缺少的標準 Bug sections。
- fetch 驗證兩個 intake headings **以及五個標準 Bug sections** 全部存在後才刪 cache。
- recovery 失敗 → **BLOCK close**，保留 cache，不得進 UAT/結案。

### 4. 退出驗證門檻

結案前執行 4 項檢查，確保修復品質達標：

| # | 檢查項 | 驗證方式 | 失敗處理 |
|---|--------|---------|---------|
| C1 | 根因分析已填寫 | Notion 頁面「根因分析」區塊非空 | WARN：提醒補填，允許繼續但狀態強制為「測試中」 |
| C2 | 修復 commit 存在 | `git log --oneline -10` 中有相關 commit | BLOCK：必須先 commit |
| C3 | 迴歸測試存在 | `grep -rF "Regression: {Bug 標題}" --include="*Test.java" --include="*.test.*" --include="*.spec.*" .`（`{Bug 標題}` = Notion 頁面標題，需與 `/bug-fix` 產出的 attribution 註解 `// Regression: {Bug 標題}` 用字完全一致；grep 需在專案根目錄執行） | WARN：建議用 /bug-fix 產出 |
| C4 | 驗證項目至少一項勾選 | Notion 頁面 checkbox 狀態 | WARN：提醒驗證 |

驗證結果顯示：

```
退出驗證：
  ✅ C1 根因分析已填寫
  ✅ C2 修復 commit 存在（abc1234）
  ⚠️  C3 無迴歸測試
  ⚠️  C4 驗證項目未勾選

結論：可結案，建議處理 C3 和 C4
```

若 C1 為 WARN → 目標狀態選項中移除「已完成」，只能選「測試中」。

### 5. 互動式補充資訊

詢問使用者（若未在初始輸入中提供）：

1. **根因分類**：`邏輯錯誤` / `資料異常` / `設定問題` / `第三方API` / `效能` / `權限` / `前端UI`
2. **根因說明**：一句話描述為什麼會發生（例如：「employees 表的 status 欄位被誤設為 99 導致查詢不到」）
3. **目標狀態**：`測試中`（預設）或 `已完成`

### 6. 產出修復摘要

根據 git diff 自動產出以下內容：

**修改檔案清單**：從 `--stat` 擷取，格式化為列表
**修改說明**：根據 diff 內容，以分層架構摘要（如 Java 專案的 Controller / Service / DAO 層）
**修改後程式碼**：擷取關鍵的程式碼變更片段（不超過 50 行）

### 6.5 人類 UAT Acceptance（必須明確確認）

為避免沿用前一次結案嘗試的 stale approval，每次進入本節先重設本輪 UAT：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" gate --slug {slug} \
  --name uat --status pending --by crew \
  --reason "bug-close requires fresh human acceptance for current fix"
```

C1-C4、編譯／測試、迴歸測試、Git diff 都只是**修復證據**，不等於使用者接受目前修復。

在任何「已完成」Notion 狀態、知識庫同步與 `close=done` 之前，先把修復摘要與已知 WARN 顯示給使用者，然後明確詢問：

```text
目前修復摘要與驗證結果如上。

你是否接受目前修復結果並允許此 Bug 進入結案？
  • 「接受／OK／確認／可以」→ 記錄 Human UAT approved，繼續結案
  • 告訴我要調整的地方 → 記錄 rejected，停止本次 bug-close，回到修復流程
```

只有使用者在**本輪**明確表示接受，才可以執行：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" gate --slug {slug} \
  --name uat --status approved --by human \
  --reason "user explicitly accepted current bug fix"
```

若使用者不接受或提出修改：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" gate --slug {slug} \
  --name uat --status rejected --by human \
  --reason "user requested additional bug-fix changes"
```

然後**立即停止本次結案**，不得更新 Notion 為「已完成」、不得建立結案知識庫條目、不得寫 `close=done`。

> 🔴 **硬規則**：
> - C1-C4 全綠 **不等於** UAT approved。
> - 測試 PASS、迴歸測試存在、Notion 驗證 checkbox 已勾選，也**不等於** UAT approved。
> - 「目標狀態=已完成」是使用者選擇的 Notion 呈現，不可反推為 UAT 核准。
> - Agent 不得自行 approve，也不得引用前一輪「OK」當成目前修復版本的 acceptance。
> - 若使用者明確要求 waive UAT，可用 `status=waived`，但必須留下具體 reason；Agent 不得主動建議 waiver。

### 7. 更新 Notion Bug 頁面

使用 `notion-update-page` 更新條目：

**Properties 更新**：

| 欄位 | 值 |
|------|-----|
| 狀態 | 使用者選擇（預設「測試中」） |
| 根因分類 | 使用者選擇的分類 |
| 修復分支 | 當前 Git branch（若原本為空） |

**Content 更新**：

使用 `update_content` 指令，搜尋模板中的空白區塊並填入：

1. 「根因分析」區塊：
   - 問題根因 = 使用者提供的根因說明
   - 問題檔案 = 從 diff stat 擷取的檔案路徑
   - 問題程式碼 = diff 中被刪除的關鍵程式碼

2. 「修復方案」區塊：
   - 修改檔案清單 = 格式化的檔案列表
   - 修改說明 = 自動產出的分層摘要
   - 修改後程式碼 = diff 中新增的關鍵程式碼
   - 修復 Commit = commit hash + message
   - 修復分支 = branch 名稱

### 8. 同步到知識庫

在「Bug 知識庫」資料庫建立一筆精簡條目（Data Source ID 見設定檔）：

| 欄位 | 值 |
|------|-----|
| Name | Bug 標題 |
| Tags | 根據 bug 內容自動推測相關標籤 |
| 難易度 | 根據修改檔案數和 diff 行數判斷：≤3 檔案且 ≤50 行 → `普通(2~4h)`，否則 → `困難(4~6h)` |
| 專案資料庫 | 同一專案 |
| 參考連結 | 任務追蹤工具的頁面 URL |

頁面內容為精簡版：
```
**根因**：{根因說明}

**解法**：{修復摘要，2-3 句話}

**關鍵程式碼**：
（修改前後的關鍵差異）
```

若設定檔中「Bug 知識庫」ID 為空，則跳過此步驟。

### 9. 學習捕捉

AI 分析本次 bug 的根因、修復和調查過程，判斷是否有可複用的洞察。

#### 學習類型

| 類型 | 說明 | 範例 |
|------|------|------|
| pattern | 可複用的 bug 模式 | 「此專案的 token 過期 bug 常發生在推播模組」 |
| pitfall | 應避免的陷阱 | 「LINE API 的 503 需要特別處理，不能只處理 401」 |
| architecture | 架構層面的洞察 | 「PushService 和 TokenService 的耦合度太高」 |
| environment | 環境相關的知識 | 「正式環境的 LINE API rate limit 是 100 req/min」 |

#### 學習格式

先依 portable config contract 解析本次寫入位置：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
LEARNING_FILE="$(python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key bug/learning \
  --project-slug "{project-slug}" \
  --mode write \
  --format path)"
```

`--mode write` 永遠回 portable canonical path；**不得**自行改寫成任何 Host-specific legacy learnings path。
接著把學習物件序列化成**單行 JSON**並 append 到 `${LEARNING_FILE}`：

```json
{
  "date": "2026-04-24",
  "skill": "bug-close",
  "bug_title": "推播排程發送失敗",
  "root_cause": "LINE API refresh 回傳 503 未處理",
  "pattern": "third-party-api",
  "type": "pitfall",
  "insight": "LINE API 的 refresh token 端點偶爾回傳 503，retry 邏輯必須涵蓋 503 且加入 exponential backoff",
  "confidence": 9,
  "files": ["PushService.java"],
  "notion_url": "https://www.notion.so/xxx"
}
```

`project-slug` 來自 Git Repo 識別碼（`/` 替換為 `-`）。每行一筆 JSON（JSONL 格式）。

#### 自動 vs 手動

AI 自動判斷是否有學習價值：
- **有明確洞察** → 自動寫入，在結案訊息中顯示「學習已捕捉：{insight}」
- **不確定** → 詢問使用者：「這次 bug 有什麼值得記下來的嗎？」
- **太泛/太明顯** → 不記錄（如「要注意 null check」太泛，不記）

#### 學習目錄建立

Resolver 本身不建立目錄；consumer 在 append 前只建立 canonical file 的 parent directory：

```bash
mkdir -p "$(dirname "${LEARNING_FILE}")"
```

然後把上方學習物件序列化成單行 JSONL append 到 `${LEARNING_FILE}`。
不得為了相容舊環境改寫回 `~/.claude`；legacy path 只供 `--mode read` fallback。

### 10. 標記結案狀態

前置條件：本輪 6.5 已取得使用者明確 acceptance，且 `state.json.gates.uat` 為 `approved` / `waived`。

> `TRANSITION_GATES["close"] = ["uat"]` 已啟用。即使 Skill 流程被誤改，runtime 仍會在 `uat` 未 approved/waived 時拒絕 `close=done`。

把 `.spec/{slug}/state.json` 的 close 步驟標為完成（見 `../../references/state-discipline.md`）：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" validate --slug {slug} --require-gate uat
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" set \
  --slug {slug} --step close --status done
```

標記後 `/plan-next` 與 SessionStart 開場提醒就不會再把它列為未結案。

🔴 **不要刪除 `state.json`**。舊版的 `handoff.md` 是純過程性檔案、結案即刪；`state.json`
是任務的結案紀錄，要**保留並入版控** —— `/plan-deploy-confirm` 事後要靠它查
`steps.close.status` 與 `deploy` 的執行進度，刪掉就查不到「這個任務的 SQL 到底跑了沒」。

與下方回傳結果的 Git 分支清理提示同屬結案收尾動作。

### 11. 回傳結果

向使用者回傳：
- 更新後的 Notion 頁面連結
- 變更摘要（修改了幾個檔案、根因分類、目前狀態）
- 知識庫條目連結（若有同步）
- Merge 結果（若「Merge 引導」步驟執行了 merge）：「已合併 feature/xxx → {dev_branch}」
- 提示後續操作：
  ```
  Bug 已結案！後續事項：
  {若有 merge} • git push origin {dev_branch}  — 推送合併結果
  • 驗證完成後請在 Notion 頁面勾選驗證項目
  • 若上線後問題復發，可使用 /bug-update reopen 重新開啟
  {若 feature branch 不再需要} • git branch -d feature/xxx  — 清理分支
  ```

---

## 何時不用

close 組 —— 本 skill 只結 bug 型任務；feature/.spec 任務結案用 /plan-close。

- feature/.spec 任務結案 → 用 `/plan-close`
- 尚未修完、只想中途補調查資訊 → 用 `/bug-update`
- Jira 單結案（非 Notion bug 流程）→ 用 jira MCP（`mcp-atlassian`）或 `jira-from-pm`
- 未建立 Notion bug 條目就想結案 → 先執行 `/bug-start`

---

## Gotchas

- **update_content 找不到區塊標題**：如果使用者手動修改過 Notion 頁面（例如把「🧠 根因分析」改成「根因分析」），`update_content` 的搜尋模式會匹配失敗。遇到這種情況，改用 `replace_content` 重寫整個頁面內容（先讀取現有內容合併）。
- **diff 包含二進位檔案**：`git diff` 遇到圖片、Excel 等二進位檔案會顯示 `Binary files differ`，不要把這些納入「修改後程式碼」區塊。只擷取文字類檔案的 diff。
- **知識庫 Tags 推測容易偏離**：自動推測 Tags 時，Claude 傾向選太多標籤。限制最多 3 個，優先選與 bug 直接相關的模組標籤（如「推播」、「排程」），避免選泛用標籤（如「API」、「效能」除非確實是那類問題）。
- **commit 範圍判斷**：使用者可能在修 bug 過程中穿插了不相關的 commit（如 merge commit）。若 `git log --oneline -10` 中混有非修復用途的 commit，應先確認正確範圍再擷取 diff，不要盲目用 `HEAD~1..HEAD`。
- **難易度判斷閾值偏保守**：「≤3 檔案且 ≤50 行 → 普通」的規則在重構型修復（改很多檔但每個只改一行）時會誤判為困難。若 diff 中大部分是 import 變更或 rename，應降級為「普通」。
- **Merge 引導是建議不是強制**：「Merge 引導」步驟可以跳過。有些場景使用者會在其他工具（如 GitLab MR）做 merge，不需要在 CLI 操作。
- **dev_branch 跨 plugin 讀取**：Merge 引導需要讀取 feature-workflow 的設定檔取得 `dev_branch`，但 bug-close 是 bug-workflow 的 skill。讀取失敗時顯示簡化提示，不阻擋流程。
- **Merge 衝突不自動解決**：衝突屬於需要人類判斷的操作，遇到衝突時顯示衝突檔案列表、暫停結案流程，等使用者解決後重新執行 `/bug-close`。
- **不自動 push**：merge 完成後不自動執行 `git push`，因為 push 會影響遠端共享狀態，需使用者明確操作。

參考 `examples/good-closure-report.md` 了解理想的結案報告結構和品質。

---

## 邊界情況

- **設定檔不存在**：提示使用者先執行 `/bug-setup` 完成初始設定
- **無 commit 可擷取**：提示使用者先 commit 修復程式碼
- **Notion 頁面內容與模板不符**：處理方式見 Gotchas 的「update_content 找不到區塊標題」
- **使用者想手動補充調查過程**：提示可直接在 Notion 頁面編輯「調查過程」區塊
- **diff 過大（> 500 行）**：僅摘要檔案清單和關鍵變更，不貼完整 diff
- **merge 衝突**：處理方式見 Gotchas 的「Merge 衝突不自動解決」
- **feature-workflow 未安裝或未設定**：原因與處理方式見 Gotchas 的「dev_branch 跨 plugin 讀取」
- **DEV 分支在本地不存在**：嘗試 `git checkout {dev_branch}`（git 會自動從 remote tracking 建立本地分支），若失敗則 `git fetch && git checkout {dev_branch}`
- **Feature branch 是否應刪除**：不自動刪除，僅在結案提示中建議。若 Feature 仍在開發中，刪除分支會造成問題
