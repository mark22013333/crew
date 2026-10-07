---
name: plan-close
description: 結案前先跑文件漂移硬關卡（FAIL 擋、WARN 需明示放行），通過後蓋章 verified_at_commit、提交 Git、批次同步 plan.md 與 deploy.sql 到 Notion。當使用者提到 /plan-close、「feature 結案」、「同步 spec 到 Notion 並結案」時觸發此 Skill。
---

# plan-close — 統一結案（漂移硬關卡 ＋ 批次 Notion 同步）

結案 = **蓋章**。順序固定且不可調換：

```
漂移檢查（唯一硬關卡）→ 通過 → 寫 verified_at_commit → git add -f + commit → Notion 同步 → 知識庫 → 結案狀態
```

> **為什麼關卡在這裡**：`/plan-build` 時符號還在流動（誤殺率最高），此刻程式碼已穩定、誤殺最低；
> 而錯過這一刻，漂移的文件會被**原樣**推到 Notion 知識庫並長期腐爛 —— 把不可信的內容傳播出去比不同步更糟。

將 `.spec/{slug}/plan.md` 與 `deploy.sql` 一次性批次同步到 Notion，更新狀態，同步到知識庫，並提交到 Git。**整個流程約 3-7 次 Notion API 呼叫**（Bug 類型有 `related_feature` 時會多出關聯 Feature 頁面的 fetch + update，達到上限）。

> **v1 舊任務**：`.spec/{slug}/plan.md` 不存在 → 這是 v1 結構，依
> `../../references/legacy-v1.md` 的相容模式執行，並在開頭提示一次。
> 過渡期限定，到期本段連同該檔一併刪除。
---

## 設定目錄

依 plugin 根目錄 `references/config-resolver.md`（相對 SKILL.md 為 `../../references/`）的漸進式載入邏輯讀取設定。本 Skill 需要：
- **第 1 層**：`config.md`（Notion IDs — 功能設計庫 / 專案資料庫）
- **第 2 層**：`projects/{repo-id}.md`（專案對應、技術棧 ID）
- **第 3 層**：`stacks/{id}.md`（技術棧定義，用於設計庫同步）

Bug 類型還需讀取 bug-workflow 設定。不要自行判斷 Host 路徑，改用 portable config resolver：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
BUG_CONFIG_FILE="$(python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key bug/config \
  --mode read \
  --format path)"
```

- `[ -f "$BUG_CONFIG_FILE" ]` → 讀取 Bug 知識庫等 bug-workflow 設定。
- 檔案不存在 → 依既有邊界提示先執行 `/bug-setup`；不得自行回退到 Host-specific 實體路徑。
- `--mode read` 的 portable/legacy fallback 由 `config-contract.md` 統一負責。

---

## 前置條件

- 已使用 `/plan-start` 建立任務
- 已完成規劃和開發（`.spec/{slug}/plan.md` 各節有內容）
- 程式碼已 commit

> **前置檢查**：參照 plugin 根目錄 `references/prerequisites.md`（相對 SKILL.md 為 `../../references/`）執行完整前置檢查（專案指令 + 設定目錄 + 專案註冊）。

---

## 紀律護欄

> 紀律護欄：`../../references/discipline-preamble.md`（通用紀律）＋ `../../references/anti-rationalizations.md`「plan-close 專用」＋ `../../references/boundaries.md`「plan-close」段。
> 🔴 本 skill 最容易出現的合理化是「漂移只有一兩筆，先同步再說」—— 那正是文件變不可信的機制，不可放行（規則見『漂移硬關卡』一節）。

---

## 流程

### 1. 定位活躍任務

參照 plugin 根目錄 `references/plan-common.md`（相對 SKILL.md 為 `../../references/`）的「定位活躍任務」（`crew-state.py list`）。

- `type`（feature/bug）與 `name` 從 `.spec/{slug}/plan.md` frontmatter 讀取
- `notion.page_id` / `notion.url` 從 `state.json` 讀取（`crew-state.py list --slug {slug} --format json`）

### 2. 清點要同步的產物

`.spec/{slug}/` 只有三種產物，逐一確認（✅/❌）：

| 產物 | 用途 | 缺少時 |
|------|------|--------|
| `plan.md` | Notion「📝 規劃文件」區塊的來源（含檢查報告摘要） | 🔴 BLOCK — 沒有它就不是 v2 任務，見『邊界情況』 |
| `deploy.sql` | Notion「🗄️ 部署 SQL」＋初始化「🚀 部署狀態」（見 5-2a） | DB_REQUIRED=false 時正常，跳過該區塊 |
| `state.json` | Notion Properties 與結案狀態的來源 | 跑 `crew-state.py rebuild --slug {slug}` 修復 |

> `.cache/`、`screenshots/`、`evidence/` 都在 `.gitignore` 內：**不進版控、不同步 Notion**。
> review／security／verify 的報告依設計不落檔 —— 要同步的是 plan.md「檢查報告摘要」節那幾行，以及 `state.json` 的 `results.*`。

### 3. 從 Git 擷取變更摘要

從專案設定檔讀取 `prod_branch`（PROD 分支），用作 merge-base 計算 diff：

```bash
# {prod_branch} 從 projects/{repo-id}.md 的 prod_branch 欄位讀取
git branch --show-current
git log --oneline $(git merge-base HEAD {prod_branch})..HEAD
git diff $(git merge-base HEAD {prod_branch})..HEAD --stat
git diff $(git merge-base HEAD {prod_branch})..HEAD
```

> 若 `prod_branch` 未設定（舊專案），回退邏輯：先取 `origin/HEAD` 指向的分支，若無則依序嘗試 `production` → `master` → `main`。

根據 `project_instructions` 的架構描述，產出分層變更摘要。

### 4. 智慧判斷目標狀態

狀態推斷邏輯：
- 使用者輸入含「完成」、「done」、「上線」、「結案」→ `已完成`
- 含「測試」、「QA」→ `測試中`
- 無法判斷 → 詢問，預設 `測試中`

### 4.2 快速結案（security／verify／review 未完成時，僅 Feature）

本節只適用 v2 `state.json` 的 **feature** 任務；bug 任務沒有這三步，不適用。CREW Cockpit 總覽的「填入 /plan-close {slug}」按鈕只會把 `/plan-close {slug}` 填進輸入框，**不會改任何狀態**——跳過與否一律在本節由人類決定。

讀 `crew-state.py list --slug {slug} --format json` 的 `steps.security`／`steps.verify`／`steps.review`：

- 三步都已是 `done`／`skipped` → 本節不適用，直接進『Human UAT Gate』一節。
- **前置條件**：`steps.build` 不是 `done`／`skipped`，或 `gates.requirement`、`gates.architecture` 任一未通過（不是 `approved`／`waived`）→ **不提出快速結案**。快速結案只跳過「實作完成後」的檢查，不能拿來略過規劃與實作本身；照 `crew-state.py next --slug {slug}` 引導使用者先完成前面階段，停止本次 plan-close。runtime 也會以同一條件拒絕 `set --status skipped`。
- 有任一步為 `failed`、`results.verify.status=FAIL`，或 `results.review.critical > 0` → **不提供快速結案**（那是已知問題，不是「太簡單」）。照 `crew-state.py next` 的建議引導使用者處理，停止本次 plan-close。
- 有任一步為 `pending`／`in_progress` → 列出這些步驟，**明確詢問人類**：

```text
⚠️ 這個 Feature 還有檢查沒跑：{security（pending）、verify（in_progress）…}

要以「快速結案」跳過它們嗎？跳過的代價：
  • security 跳過 → 沒有安全掃描證據（OWASP、注入、權限、敏感資料都沒人看過）
  • verify 跳過   → 沒有 AC 驗收證據（驗收條件是否達成只能靠你的 UAT 判斷）
  • review 跳過   → 沒有程式碼審查證據（邏輯／品質／效能沒有第二雙眼睛）
跳過不會略過 Human UAT 與漂移硬關卡，它們照常執行。

  • 「同意快速結案」（可附理由）→ 把上列步驟全部標成 skipped（記錄理由與決策者），繼續結案
  • 只同意跳過其中幾步（例：「只跳過 security」）→ 只標那幾步，其餘照原流程
  • 其他回覆 → 停止本次 plan-close，改跑 {/plan-security、/plan-verify、/plan-review 中未完成者}
```

只有使用者在**本輪**明確同意，才可以對**使用者同意的那幾步**逐步執行（只對未完成的步驟執行）：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" set --slug {slug} \
  --step {security|verify|review} --status skipped --by human \
  --reason "quick close approved by user: {使用者原話}"
```

- **部分跳過**：使用者可以只同意其中部分步驟。逐步列出、逐步確認；回覆未明確涵蓋的步驟一律視為**不同意**，照原流程停止本次 plan-close 並引導該步驟的指令（例：同意跳過 security、未表態 verify → 只標 security，引導 `/plan-verify`）。
- **`--reason` 只能記錄使用者實際說的話**：使用者有說理由 → 照抄原話；只回「同意」而沒說理由 → 寫 `quick close approved by user: 使用者同意快速結案（未另述理由）`。**禁止 Agent 自行編造或補寫理由**（例如替使用者寫「文案微調、風險低」）。

使用者未明確同意、沉默、或只說「繼續」而沒有回應跳過的問題 → 視為不同意，停止本次 plan-close，引導該跑的指令。

> 🔴 「這個功能夠簡單」的判定權在人，**不在 Agent**。Agent 不得主動建議快速結案、不得替使用者決定、不得在使用者沒回應時預設跳過。
> 🔴 runtime 守門：feature 的 security／verify／review 標 `skipped` 必須帶 `--reason` 與 `--by`，且 `build` 須為 done-like、requirement／architecture 閘須已通過，否則 `crew-state.py` 直接拒絕。
> ⚠️ 「不得覆蓋已 `done`／`failed` 的步驟或 verify FAIL／review 🔴 的結果」只是**防呆，非安全防線**：先把步驟改回 `pending`、或改寫 `results` 就能繞過；`--by` 也只檢查有值、不驗證是不是人。真正的把關是本節的人類明確同意，以及其後照常執行的 Human UAT 與漂移硬關卡。
> 跳過紀錄寫在 `steps.{step}.reason`／`steps.{step}.by` 與 `history`；最終回報要列出「快速結案跳過：{步驟}（理由）」。

### 4.5 Human UAT Gate（Runtime hard block）

本節只適用 v2 `state.json` 任務；v1 任務依 `../../references/legacy-v1.md` 相容模式執行，不呼叫 `crew-state.py`。

完整契約見 `../../references/uat-gate.md`。為了避免沿用前一次結案嘗試的 stale approval，**每次進入本節先重設本輪 UAT**：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" gate --slug {slug} \
  --name uat --status pending --by crew \
  --reason "plan-close requires fresh human acceptance for current delivery"
```

接著顯示 `results.verify`、`results.review`、主要交付結果與已知風險，向使用者明確詢問：

```text
機器驗證與程式碼審查已完成，現在進入 Human UAT。
（快速結案時改說：{步驟} 已依你的決定跳過、沒有對應檢查證據，現在進入 Human UAT。）

你是否接受目前交付結果並允許此 Feature 結案？
  • 「接受／OK／確認／可以」→ 記錄 uat=approved，繼續結案
  • 告訴我要調整的地方 → 記錄 uat=rejected，停止本次 plan-close
```

只有使用者在**本輪**明確表示接受，才可以執行：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" gate --slug {slug} \
  --name uat --status approved --by human \
  --reason "user explicitly accepted current feature delivery"
```

若使用者不接受或提出修改：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" gate --slug {slug} \
  --name uat --status rejected --by human \
  --reason "user requested additional feature changes"
```

然後**立即停止本次結案**，不得執行漂移蓋章、Notion 結案同步或 `close=done`。

若使用者明確要求 waive UAT，可寫 `status=waived`，但必須提供具體 reason；Agent 不得主動建議 waiver。

> 🔴 `results.verify.status=PASS`、`steps.review=done`、`/plan-verify --manual` 都只是證據，不是 Human UAT。
> 🔴 快速結案把 review 標成 `skipped` 後，uat gate 才能被設定（review 屬 done-like），但仍是 `pending`；**必須照本節取得人類 UAT 核准**，skipped 不會自動放行 close。
> 🔴 `TRANSITION_GATES["close"] = ["uat"]` 已啟用；即使 Skill 流程被誤改，runtime 仍會在 UAT 未通過時拒絕 `close=done`。

UAT 通過後先做 exit check：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" validate --slug {slug} --require-gate uat
```

### 5. 漂移硬關卡（文件硬關卡，🔴 不可跳過）

**必須在 `git add -f` 與任何 Notion 呼叫之前執行。** Human UAT 與文件漂移現在都是正式硬關卡：UAT 管「人是否接受」，漂移管「文件是否可信」。

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/check-spec-drift.py" \
  --spec .spec/{slug}/plan.md --format json
echo "exit=$?"
```

依 **exit code** 分流（🔴 不可自行改判，也不可只憑 JSON 是否為空就當通過）：

| exit | 意義 | 處置 |
|------|------|------|
| `0` | 無 FAIL、無 WARN | ✅ 通過 → 進『蓋章』一節 |
| `1` | 有 FAIL（D1 錨點檔案不存在／D2 符號不在檔內），或 WARN 被 `drift_policy: strict` 升級 | 🔴 **阻擋結案**，照下方「FAIL 的回報格式」列出並引導 `/plan-drift` |
| `2` | 只有 WARN（D4 hash、D5 表無引用、D6 文件落後程式碼、D7 缺蓋章／零錨點） | ⚠️ **需使用者逐筆明示放行**（見下方） |
| `3` | **環境問題**（非 git 工作區、`verified_at_commit` 不在歷史、檔案讀不到） | 🔴 阻擋蓋章，回報「**無法檢查**」＋原因＋script 的「修法：」原文 |

#### FAIL 的回報格式（exit 1）

```
🔴 結案已擋下：文件與程式碼不一致（{N} 筆 FAIL）

  • [D2] plan.md:23 `@code:src/.../LoginAttemptService.java#recordFailure`
    檔內找不到 recordFailure
    修法：{原文照登 script 的「修法：」那一行}
  • [D1] plan.md:31 `@code:src/.../OldService.java`（git 偵測到改名，可自動修）

  下一步：
    /plan-drift --fix     # 機械型（改名、行號）自動修
    /plan-drift           # 語意型逐條確認（符號消失常代表決策變了）
  修完重跑 /plan-close。
```

- exit 1 但 JSON 內 `level` 全無 FAIL → 是 WARN 被 `drift_policy: strict` 升級，照 WARN 流程逐筆放行即可，**不要去找不存在的 FAIL**。
- 🔴 **不得**在本 skill 自行改錨點、自行跑 `--fix`、或建議使用者改 `drift_policy: off` 來繞過。修復迴路是 `/plan-drift` 的職責（它有使用者逐條確認機制）。

#### WARN 的放行流程（exit 2）

逐筆顯示，一次問一條，**使用者明示才放行**（不提供「全部放行」選項 —— 那等於沒問）：

```
⚠️ [D6] plan.md 的錨點檔案自 {verified_at_commit} 後有變更（3 個檔案），plan.md 未同步更新
   影響：文件可能落後程式碼；蓋章後這份文件會被同步到 Notion 知識庫
   修法：{原文照登 script 的「修法：」那一行}
   [1] 放行（我確認這些變更不影響決策紀錄）  [2] 中止，我先去 /plan-drift 處理
```

- 每筆都選 1 → 視為通過，繼續『蓋章』一節，並在最終回報列出「已放行的 WARN」清單
- 任一筆選 2 → 終止 plan-close（不寫蓋章、不 commit、不呼叫 Notion）

#### ENV 項目一律單獨回報

JSON 中 `level` 為 `ENV`（`code` = `E1`）的項目代表「這次沒檢查成」，可能與 FAIL 並存（此時 exit 為 1）。
**每次都要掃有無 ENV 項目**，不能只看 exit code。🔴 ENV 不得說成「有漂移」，也不得說成「檢查通過」。

#### `drift_policy: off` 的任務

script 會明示「已跳過未檢查」。此時**不蓋章**（沒檢查就沒有承諾），照常結案，並在回報中寫「本任務 `drift_policy: off`，未做漂移檢查」，🔴 不得寫成「全部通過」。

### 5.5 蓋章 `verified_at_commit`（只有通過才做）

前置條件：『漂移硬關卡』一節得到 exit 0，或 exit 2 且**每筆** WARN 都經使用者明示放行。
exit 1、exit 3、有 ENV 項目、`drift_policy: off` → **不蓋章**。

```bash
git rev-parse --short HEAD
date +%F
```

用 **Edit** 更新 `.spec/{slug}/plan.md` frontmatter 的**兩行**（🔴 只改這兩行，不動其他 frontmatter 欄位、不整檔改寫）：

```yaml
verified_at_commit: 3f2a91c
verified_at: 2026-07-28
```

值一律用上面兩個指令的**實際輸出**，不憑印象填。

> **單一寫入點**：`verified_at_commit` 全流程只有 `/plan-drift` 與本 skill 能寫。
> `/plan-build`、`/plan`、`/plan-review`、`/plan-security`、`/plan-verify` 一律禁止 —— 剛改完程式碼自己蓋章等於作廢。

### 5.6 部署步驟數登記（deploy.sql 存在時）

`deploy-checklist.md` 已廢除（它是 `deploy.sql` 的 derived view，會自己過期）。部署進度改記在 `state.json`：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" set --slug {slug} \
  --deploy-total {deploy.sql 的 -- Step N 數量} --deploy-confirmed 0
```

`deploy.sql` 無 `-- Step N` 註解無法分段 → `--deploy-total 1`（整份視為一步），並在回報中提醒。
實際執行結果由 `/plan-deploy-confirm` 回報時更新 `--deploy-confirmed`。

### 5.7 提交 .spec/ 到 Git（在 Notion 同步之前）

蓋章後**先進版控再同步 Notion** —— 順序反了會出現「Notion 有、git 沒有」的狀態，且 commit 的內容不含蓋章。

`plan-start` 在 `.gitignore` 寫入的是整個 `.spec/`（排除目錄），此時用 `!.spec/{slug}/` 反向取消忽略**無效**（Git 不會遞迴進入已被排除的目錄），因此改用 `git add -f` 強制加入：

```bash
# -f 強制加入被 .gitignore 忽略的檔案；一旦加入即為 tracked，
# 之後的修改 Git 會正常追蹤，不需再次 -f。
git add -f .spec/{slug}/plan.md
git add -f .spec/{slug}/deploy.sql      # 存在時
git add -f .spec/{slug}/state.json
git commit -m "docs: 新增 {slug} 規劃文件（plan.md + deploy.sql）"
```

🔴 **逐檔指定，不要 `git add -f .spec/{slug}/`**：整個目錄會把 `.cache/`、`screenshots/`、`evidence/` 一起強制加入（`-f` 會蓋掉 gitignore），binary 與一次性暫存不該進版控。
commit 後跑 `git status --short .spec/{slug}/` 確認沒有意外被加入的檔案。

### 6. 一次性 Notion 批次更新（只在漂移關卡通過後執行）

**6-1. Fetch 現有頁面**（1 次 `notion-fetch`）

使用 `state.json` 的 `notion.page_id` fetch 頁面。

**6-2. 更新頁面內容**（1 次 `notion-update-page` content）

**同步映射表（v2，來源只有 `plan.md` ＋ `deploy.sql` ＋ git）**：

區塊標題以 plugin 根目錄 `references/notion-page-template.md`（相對 SKILL.md 為 `../../references/`）的模板為準。

| Notion 區塊 | 來源 | 條件 |
|-------------|------|------|
| 📋 需求描述 | 保留 intake prefix（`### 原始需求`＋`### 確認後任務描述`）＋更新 `plan.md`「目標與範圍」＋「驗收條件」（`AC-n` 原樣） | 必有 |
| 📐 技術規格 | `plan.md`「決策紀錄」＋「已知取捨與風險」＋「指路」（錨點原樣，不展開內容） | 必有 |
| 🗄️ 資料庫設計 → 遷移 SQL | `deploy.sql` 全文 | `deploy.sql` 存在 |
| 🚀 部署狀態 | 由 `deploy.sql` 的 `-- Step N` 初始化（見 6-2a），每筆預設「待執行」 | `deploy.sql` 存在 |
| 📁 程式碼清單 | `git diff --name-status` ＋『從 Git 擷取變更摘要』一節的分層變更摘要 | 必有 |
| 📝 開發日誌 | `plan.md`「檢查報告摘要」節的條目 ＋ 追加結案紀錄：<br>`### [{日期}] 開發完成`<br>`- **分支**：{branch}`<br>`- **Commit 數**：{N}`<br>`- **蓋章**：verified_at_commit {sha}`<br>`- **變更摘要**：{分層變更摘要}` | 必有 |

- **原樣搬運，不重寫**：章節內容照抄，不要「順手潤稿」或補充 —— 那會讓 Notion 與 plan.md 講不同的話。
- **📋 需求描述 intake prefix 永久保留**：`### 原始需求` 與 `### 確認後任務描述` 不由 plan.md 重建。只更新其後的 `### 目標與範圍` / `### 驗收條件`。
- 若 `.spec/{slug}/.cache/intake.md` 存在：
  - 先讀 cache 的 `notion_page_id`；非空時必須與 state 的 `notion.page_id` 一致，不一致就 **BLOCK**，不得猜 page。
  - 頁面缺 intake prefix → 用 cache 補回 original/refined。
  - Notion update 後重新 fetch；只有 intake prefix 完整、state page ID 與本輪 page 一致、cache page ID 為空或一致時才刪 cache。
- 若頁面缺 intake prefix且 cache 也不存在（legacy task）→ 保留既有需求內容，**不得猜原始 prompt**；必要時要求 Human 補充。
- **對應表兩處要一致**：`/plan-sync`（中途同步）用同一組區塊。改這張表時要同步確認 `plan-sync` 的版本，否則同一份 plan.md 會在中途同步與結案同步落到不同區塊。

🔴 **不再同步**（來源檔案已廢除）：spec／db／arch 三份設計文件、上線前置作業 checklist、檔案清單文件、review／security／verify 全文報告。
需要細節的人看 `plan.md` 的錨點與 git 本身 —— 抄一份到 Notion 就是製造第二份會漂移的副本。
`state.json` 的 `results.review` / `results.security` / `results.verify` 只用來核對摘要行的數字是否一致，本身不同步。

> **只有蓋過章的內容才推上去**：本節必須在『漂移硬關卡』通過（exit 0 或 WARN 全放行）後才執行。
> 舊流程把本地文件**原樣**同步、不校對，等於把不可信的內容傳播到知識庫，這是本次重構要解掉的第三個症狀。

**6-2a. 建立「🚀 部署狀態」區塊**（僅 Feature 且 deploy.sql 存在）

`deploy.sql` 寫入「部署 SQL」子區塊後，一併建立「🚀 部署狀態」追蹤區塊，作為 `/plan-deploy-confirm` 回流機制的寫入標的。此處只**初始化**（每筆預設「待執行」），實際執行結果由 `/plan-deploy-confirm` 之後覆寫。

依 `-- Step N：{描述}` 註解切割 deploy.sql，每個 Step 產生一列，狀態一律填「⏳ 待執行」：

```markdown
## 🚀 部署狀態

### 最後執行：（尚未執行）

| Step | 描述 | 狀態 | 執行時間 | 備註 |
|------|------|------|---------|------|
| 1 | 建立 users 表 | ⏳ 待執行 | — | — |
| 2 | 建立 email 唯一索引 | ⏳ 待執行 | — | — |

### 執行紀錄

（尚無執行紀錄，執行後由 /plan-deploy-confirm 追加）

### 備註
（無）
```

> **契約**：區塊標題固定為「🚀 部署狀態」、狀態詞固定用「待執行」，與 `/plan-deploy-confirm` 讀寫的名稱一致。若 deploy.sql 無 `-- Step N` 註解無法分段，退回單一列（Step 1 = 整個 deploy.sql，狀態「待執行」）。
> 表格內容與 `state.json` 的 `deploy.steps_total`（見『部署步驟數登記』一節）必須一致。
>
> **語意一致性註記**：Notion「狀態」欄位值（本步驟『智慧判斷目標狀態』寫入的 `測試中`/`已完成`）與本地 `state.json` 的 `steps.close.status = done`（見『結案狀態』一節）是兩套獨立語意，不可混用。`/plan-deploy-confirm` 的 Notion 搜尋以「🚀 部署狀態含待執行」為主判準，不依賴 Notion 狀態欄位值。

**Bug 類型**：

Bug 頁面用的是 `/plan-start` 的 Bug 模板（🔴 問題描述 / 🔍 調查過程 / 🧠 根因分析 / ✅ 修復方案 / 🧪 驗證 / 📝 經驗教訓）。內容一律取自同一份 `plan.md`：

| Notion 區塊 | 來源 |
|-------------|------|
| 🧠 根因分析 | `plan.md`「決策紀錄」節中根因判定的條目（含被否決的假設與否決理由） |
| ✅ 修復方案 | `plan.md`「指路」節的修改落點錨點 ＋ git diff 分層摘要 |
| 🧪 驗證 | `plan.md`「檢查報告摘要」節的 verify／review／security 摘要行 |
| 📝 經驗教訓 | `plan.md`「已知取捨與風險」節 ＋ 決策紀錄中「為什麼一開始會錯」的條目 |

🔴 不再有 `investigation.md` / `root-cause.md` / `fix.md` / `log.md` 這些獨立檔案。

**6-3. 更新 Properties**（1 次 `notion-update-page` properties）

**Feature**：

| 欄位 | 值 |
|------|-----|
| 狀態 | 『智慧判斷目標狀態』判斷結果 |
| 開發階段 | `測試中` |
| 修復分支 | 當前 Git branch |

**Bug**：

| 欄位 | 值 |
|------|-----|
| 狀態 | 『智慧判斷目標狀態』判斷結果 |
| 根因分類 | 從 plan.md「決策紀錄」節的根因決策條目推斷（邏輯錯誤/資料異常/設定問題/第三方API/效能/權限/前端UI） |
| 修復分支 | 當前 Git branch（`state.json` 的 `git.branch`） |

### 7. 同步到知識庫

**Feature → 功能設計庫**（1 次 `notion-create-pages`）

同步邏輯：

| 欄位 | 值 |
|------|-----|
| Name | 功能標題 |
| Tags | 自動推測（API/報表/標籤/推播/排程 等） |
| 設計類型 | 依 plan.md 走過的 pass 判斷（`state.json` 的 `steps.spec/db/arch` 哪些是 done） |
| 技術棧 | 設定檔中的技術棧 ID |
| 參考連結 | Notion 頁面 URL |
| 專案資料庫 | 同一專案 |

> 知識庫條目的內容以 `plan.md` 的決策紀錄為主體（那是唯一不會過期的資產）。🔴 不要把程式碼事實（欄位、簽章、DDL）抄進知識庫。

**Bug → Bug 知識庫**（1 次 `notion-create-pages`）

複用 `bug-close` 的同步邏輯：

| 欄位 | 值 |
|------|-----|
| Name | Bug 標題 |
| Tags | 自動推測 |
| 難易度 | 依修改檔案數和行數判斷 |
| 專案資料庫 | 同一專案 |
| 參考連結 | Notion 頁面 URL |

### 8. Feature-Bug 關聯（僅 Bug 且有來源 feature）

來源 feature 記在 Bug 的 `plan.md`「指路」節（由 `/plan-start --related` 寫入，格式 `- 來源 feature：{slug}（Notion：{URL}）`）：

1. 用 `crew-state.py list --all --format json` 取得該 feature 的 `notion.page_id`
2. `notion-fetch` 取得關聯 Feature 的 Notion 頁面（1 次）
3. 在「📝 開發日誌」區塊追加：

```
### [{日期}] 🔴 相關 Bug
- Bug: {Bug 名稱}（{Bug Notion URL}）
- 根因: {Bug plan.md「決策紀錄」節的根因條目摘要}
- 修復: {Bug plan.md「指路」節的修改落點摘要}
```

4. `notion-update-page` 更新 Feature 頁面（1 次）

### 9. 結案狀態（唯一權威 state.json）

Notion 同步完成後寫回狀態，**不手寫任何欄位**。`close=done` 受 runtime UAT hard gate 保護，若 gate 不是 `approved` / `waived`，這一步必須失敗：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" set --slug {slug} \
  --step close --status done --phase close \
  --last-commit "$(git rev-parse HEAD)" \
  --mirrored-status "{Notion 上的狀態字串，例：測試中}" --synced-now
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" validate --slug {slug} --expect-phase close
```

- `steps.close.status = done` 就是「已結案」的唯一判準；`/plan-status`、`/plan-next`、SessionStart 提醒都讀這裡。
- 舊流程的任務索引檔與 README frontmatter 的狀態欄位皆已廢除 —— 任務清單由 `crew-state.py list` 即時掃 `state.json` 生成，沒有快取可漂移。
- `--synced-now` 記錄 `notion.last_synced_at`；`--mirrored-status` 記錄 Notion 上呈現的狀態（供下次比對，衝突時本地贏）。
- **不刪除 `.spec/{slug}/` 目錄**，保留供未來 Bug 關聯匹配。

> `state.json` 已在『提交 .spec/ 到 Git』一節被 commit，此處的更新屬結案後的狀態變化，
> 使用者可自行決定要不要再補一個 commit（`/plan-status` 讀工作區檔案，不受影響）。

### 10. 回傳結果

```
結案完成！

{⏭️ 快速結案跳過：{security/verify/review 中被跳過者}（理由：{reason}，決策者：human）—— 無對應檢查證據}
🔍 漂移檢查：exit {0|2}（{錨點全部有效 / N 筆 WARN 經使用者放行 / drift_policy: off 未檢查}）
🔖 蓋章：verified_at_commit {sha}（{日期}）{未蓋章時改為「未蓋章（原因）」}
📁 已提交到 Git：plan.md{、deploy.sql}、state.json
📊 Notion 頁面：{URL}（已更新）
📚 知識庫：{知識庫條目 URL}（已同步）
{📎 Feature 關聯：已更新 {來源 feature slug} 的開發日誌}
{🗄️ 部署步驟：{N} 個 Step 待執行 → 之後用 /plan-deploy-confirm 回報}
✅ 狀態：steps.close = done

Notion API 呼叫統計：{N} 次（fetch: 1, update: 2, create: 1{, 關聯更新: 2}）

{已放行的 WARN（逐筆列出，含使用者放行理由）}

後續事項：
  📋 測試驗證：在 Notion 頁面勾選驗證項目
  🔀 Git 合併：{根據 project_instructions 的 Git Flow 產出合併建議}
```

---

## 何時不用

close 組 + sync 組 —— feature/.spec 任務結案用本 skill；bug 型結案用 /bug-close；未結案的中途同步用 /plan-sync。

- bug 型任務結案 → 改用 `/bug-close`
- 未結案的中途同步 → 改用 `/plan-sync`
- 更新單一 bug 頁 → 改用 `/bug-update`
- 部署 SQL 執行回報 → 改用 `/plan-deploy-confirm`
- 只想檢查／修錨點漂移，還不打算結案 → 改用 `/plan-drift`

---

## Gotchas

- **快速結案只跳檢查，不跳關卡**：security／verify／review 可由人類決定標 `skipped`，但 Human UAT 與漂移硬關卡照常執行；`skipped` 是 done-like，會讓 `/plan-next` 指向 `/plan-close`，不代表 UAT 已核准。
- **關卡順序不可調換**：漂移檢查 → 蓋章 → `git add -f` → Notion 同步。任何「先同步、之後再修文件」的變體都會把不可信內容推上知識庫，而那正是使用者最在意的症狀。
- **exit code 才是判準，不是 JSON 看起來乾不乾淨**：D3（行號位移）是 INFO，不影響 exit code；只看 JSON 有沒有項目會誤判。反過來，exit 1 但無 FAIL 代表 WARN 被 `drift_policy: strict` 升級。
- **exit 3 不是漂移**：環境問題代表「這次沒檢查成」。把它說成「有漂移」或「檢查通過」都是假資訊，一律原文照登 script 的「修法：」那行，並且**不蓋章**。
- **蓋章是承諾，不是儀式**：`verified_at_commit` 只有 `/plan-drift` 與本 skill 能寫，且必須在檢查真的通過之後。這個欄位一旦被隨手蓋，整套漂移偵測就失去意義（下次 D6 的比較基準也會錯）。
- **一次 update_content 的大小限制**：Notion API request body 約 2MB 上限。v2 只同步 plan.md（≤100 行）＋ deploy.sql，通常遠低於上限；`deploy.sql` 特別大時才需分批呼叫 `update_content`。
- **Bug 類型需讀取兩個設定來源**：知識庫 ID（Bug 知識庫）在 `bug/config` logical key 中；只讀 feature-workflow 設定會靜默跳過知識庫同步。Bug 類型結案時，feature 設定照既有流程載入，bug 設定一律經 `crew-config.py resolve --key bug/config --mode read`。
- **提交 .spec/ 用 `git add -f`，但要逐檔指定**：`plan-start` 在 `.gitignore` 忽略整個 `.spec/`，而 Git 無法用 `!.spec/{slug}/` 反向取消對「已排除目錄」的忽略（re-include 對已被排除目錄下的內容無效），故必須用 `-f`；力求不改動 `.gitignore`，避免規則順序踩坑。但 `-f` 對整個目錄會連 `.cache/`、`screenshots/`、`evidence/` 一起強制加入 —— 只逐檔加 `plan.md` / `deploy.sql` / `state.json`。強制加入後檔案即成 tracked，後續修改 Git 會正常追蹤。
- **Notion 呼叫次數統計**：基本情況 3-5 次，但 Bug 有來源 feature 時會多 2 次（fetch + update 關聯 Feature 頁面），實際可達 7 次。回傳結果的統計數字要如實反映。

---

## 邊界情況

- **`notion.page_id` 為空**：先用 `/plan-sync` 執行 intake cache/page recovery；不要在 `/plan-close` 直接建立第二個 page
- **plan.md 不存在（v1 舊任務，只有 README.md）**：本 skill 的 v2 流程不適用 —— 明說「該任務仍是 v1 格式」，不要當成通過、也不要跑漂移檢查（沒有錨點可檢查）
- **plan.md 存在但零錨點**：script 回 D7 WARN（過渡期），照 WARN 流程請使用者放行；放行後照常蓋章
- **`drift_policy: off`**：不檢查、不蓋章，照常結案，回報明寫「未檢查」
- **`check-spec-drift.py` 回 exit 3**：阻擋蓋章，回報「無法檢查」＋原因；使用者修好環境後重跑
- **diff 過大（> 500 行）**：僅摘要檔案清單和分層變更
- **知識庫 ID 為空**：跳過知識庫同步
- **來源 feature 的 Notion 頁面不存在**：跳過關聯更新，提示使用者
- **Notion API 失敗**：顯示已完成和失敗的步驟，建議用 `/plan-sync` 重試（此時 git commit 與蓋章已完成，不需重跑漂移檢查）；若 intake cache 尚未成功持久化，必須保留 cache，不得提前刪除
- **project_instructions 無 Git Flow 描述**：使用通用提示
