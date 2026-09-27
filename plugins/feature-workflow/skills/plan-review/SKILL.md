---
name: plan-review
description: 以 3 個 reviewer 角色審查 .spec 任務的程式碼（邏輯/品質/效能），Host 支援時可平行、否則序列。當使用者提到 /plan-review、「CREW 程式碼審查」、「plan-review 審查」時觸發此 Skill。
argument-hint: "[--quick]"
---

# plan-review — 多角色程式碼審查

依 `../../references/host-capabilities.md` 以 3 位 Reviewer 的 role contract 審查程式碼；有 `parallel_delegate` 時可平行，否則序列。第一輪完成後由 Leader 整理發現，再進行交叉審查與彙整。

> **報告不落檔**：完整報告在**對話輸出**（要當下看、當下修的東西，存成檔案只會變成沒人再讀的漂移來源）。
> 落檔的只有兩樣：`plan.md`「檢查報告摘要」節的**一行**摘要，與 `state.json` 的 `results.review`。

---

## 前置條件

### Host capability

載入 `../../references/host-capabilities.md`。完整審查優先使用 `parallel_delegate`，但平行能力只是最佳化：

- 有 `parallel_delegate` → 3 個 reviewer 可平行。
- 只有一般 delegate → 3 個 reviewer 依序執行。
- 無 subagent → 主 Agent inline 執行 3 個唯讀 role。

不得因某家 Host 的 Team 功能或環境變數未啟用而阻擋審查。

### 程式碼

建議已執行 `/plan-build` 產生程式碼，或已有開發中的程式碼。

> 💡 plan-review 從 .spec/ 和程式碼檔案讀取所有輸入，不依賴對話歷史。
>    若剛執行完 /plan-build，建議先 /clear 再執行，確保有足夠 context 空間。

> **前置檢查**：參照 plugin 根目錄 `references/prerequisites.md`（相對 SKILL.md 為 `../../references/`）檢查專案指令是否存在。

---

## 紀律護欄

> 紀律護欄：`../../references/discipline-preamble.md`（通用紀律）＋ `../../references/anti-rationalizations.md`「plan-review 專用」＋ `../../references/boundaries.md`「plan-review」段；斷點保險改為**進度即寫 `state.json`**（`crew-state.py unit`／`result`）；有「可以跳過」「應該夠了」的衝動時，停下查表確認是否為已知偏離模式。

---

## 使用方式

```
/plan-review               # 完整 3 人審查
/plan-review --quick       # 快速審查（僅 logic-reviewer，用 Subagent）
```

---

## 流程

### 1. 定位活躍任務

參照 plugin 根目錄 `references/plan-common.md`（相對 SKILL.md 為 `../../references/`）的「定位活躍任務」（`crew-state.py list`），流程位置一律以 `state.json` 為準。

### 2. 收集審查範圍（git 是唯一事實來源）

`{prod_branch}` 從專案設定讀取；未設定時，先取 `origin/HEAD` 指向的分支，若無則依序嘗試 `production` → `master` → `main`：

```bash
git diff $(git merge-base HEAD {prod_branch})..HEAD --name-only   # 已 commit 的變更
git status --porcelain                                            # 尚未 commit 的變更
```

兩者合併去重即為審查範圍。🔴 不要去找檔案清單文件（已廢除）—— 清單檔會過期，git 不會。
兩邊都是空的 → 提示使用者指定檔案，或先 `/plan-build`。

### R0. 漂移 pre-check（省 token，不阻擋）

在 spawn Reviewer 之前先跑一次錨點檢查，把結果當 **Reviewer 1 的輸入**（它已經幫你標出「文件說的位置和程式碼對不上」的地方，Reviewer 不必自己重掃）：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check-spec-drift.py" \
  --spec .spec/{slug}/plan.md --format json
```

| exit | 處理 |
|------|------|
| 0 | 報告「錨點全部有效」，照常進行 |
| 1 / 2 | 把 JSON 內每筆的 `code`／`anchor`／`detail`／`fix` 摘要進 Reviewer 1 的 prompt，並在確認畫面顯示「⚠️ 錨點 N 筆需注意」；**不阻擋** |
| 3 | 環境問題 → 標「本次未檢查錨點」＋原因，🔴 不得說成漂移，也不得說成通過 |

🔴 本 skill **不修**錨點、**不寫** `verified_at_commit`；要修去 `/plan-drift`，硬關卡在 `/plan-close`。

### 3. 讀取審查基準

- `.spec/{slug}/plan.md` —— 目標與範圍、驗收條件 `AC-n`（功能正確性的判準）、決策紀錄 `D-n`（**為什麼這樣寫**，判斷「偏離」還是「刻意」的依據）、已知取捨與風險（已列為取捨的不要再當缺陷報）
- `.spec/{slug}/deploy.sql` —— 表結構、索引、約束的唯一事實來源（Reviewer 3 效能審查用）
- `state.json` 的 `results.verify` —— 上一輪運行時驗證結果（選讀，`crew-state.py list --slug {slug} --format json`）

### 4. 確認執行計畫

```
即將啟動 CREW 多角色程式碼審查：

📁 審查範圍：N 個檔案（git diff + git status）
🔍 錨點 pre-check：{全部有效 / ⚠️ N 筆需注意 / 本次未檢查（原因）}
📊 Reviewer 配置：
  • Reviewer 1 — 邏輯正確性（model: sonnet）
  • Reviewer 2 — 程式碼品質（model: sonnet）
  • Reviewer 3 — 效能審查（model: opus）

確認開始？[Y/n]
```

#### 模型配置規則（硬性）

完整政策見 plugin 根目錄 `references/model-policy.md`（相對 SKILL.md 為 `../../references/`）。

- 三位 Reviewer 都用 `delegate_readonly`／`parallel_delegate`；每個 role 的 capability request 各自帶結構化 `model`（`sonnet` / `sonnet` / `opus`），Host 做不到精準 worker model 時依 capability contract 回報降級。
- 一般邏輯檢查、規格符合度、程式碼風格與品質 → `sonnet`；效能敏感（含交易、並行、大量資料）→ `opus`。
- **小變更例外**：變更範圍小、且不涉及安全、交易、並行或效能敏感區域時，三位可全部用 `sonnet`，或直接建議使用者改跑 `/plan-review --quick`。採用例外時要在上面的確認畫面標明實際模型與理由。
- 安全審查不在本 skill 範圍 → 由 `/plan-security`（`model: opus`）負責。

### 5. 啟動多角色審查

#### 完整審查（parallel_delegate 優先）

建立 3 個 `delegate_readonly` role；Host 支援時包成一次 `parallel_delegate`，否則依序執行（每個角色各自帶結構化 `model`）：
- **Reviewer 1：邏輯正確性**（`model: sonnet`）— 讀取 plan.md（`AC-n` ＋ `D-n`）、R0 的錨點 pre-check 結果與變更檔案，檢查 API 參數驗證、業務邏輯、查詢條件、例外處理、邊界條件、回傳格式，並逐條對照 `AC-n` 是否真的有對應實作
- **Reviewer 2：程式碼品質**（`model: sonnet`）— 比對專案既有檔案風格，檢查命名規範、package 結構、Lombok、註解、error handling、edge case
- **Reviewer 3：效能審查**（`model: opus`）— 讀取 `deploy.sql`（索引、約束）與變更檔案，檢查 N+1、分頁、索引、迴圈內 DB 呼叫、快取、連線池

三位 Reviewer 完成後互相分享發現、交叉審查，Lead 只負責協調（delegate mode，不自己寫 code）彙整產出 Review Report，全程繁體中文。

完整派工 prompt 模板（含各 Reviewer 逐項檢查清單與標記符號）：plugin 根目錄 `references/review-prompts.md`（相對 SKILL.md 為 `../../references/`），套用時將 `{slug}`、`{檔案清單}` 換成實際值。

#### 快速審查（--quick，Subagent）

使用 `delegate_readonly`（role=`logic-reviewer`、`model: sonnet`），只做邏輯正確性審查
（呼叫時必須實際傳入 `{"model": "sonnet"}`；`--quick` 針對小型變更，唯讀不改程式碼）：

```
你是資深程式碼審查員。

## 規劃文件（判準）
{plan.md 的 目標與範圍 / 驗收條件 AC-n / 決策紀錄 D-n / 已知取捨與風險}

## 錨點 pre-check 結果
{R0 的 JSON 摘要；無則寫「全部有效」或「本次未檢查（原因）」}

## 審查檔案
{檔案清單及內容}

## 專案上下文
{project_instructions 內容}

## 任務
對以上程式碼進行快速審查，聚焦於：
1. 邏輯正確性
2. 明顯的安全問題
3. 風格一致性（與專案現有程式碼比對）

標記嚴重程度：🔴 嚴重 / 🟡 建議 / 🟢 良好
輸出使用繁體中文。
```

### 6. 彙整審查報告（對話輸出，不落檔）

Leader 收集所有 Reviewer 的發現（含交叉分享結果），彙整成下列結構**直接輸出在對話**。
🔴 **不要**寫成 `.spec/` 下的檔案 —— 這份報告的價值是「現在拿去修」，存成檔案只會在下次改碼後變成錯的。

```markdown
# 程式碼審查報告

## 審查日期
{日期}

## 審查範圍
{N} 個檔案

## 統計
| 類別 | 🔴 嚴重 | 🟡 建議 | 🟢 良好 |
|------|---------|---------|---------|
| 邏輯正確性 | {N} | {N} | {N} |
| 程式碼品質 | — | {N} | {N} |
| 效能 | {N} | {N} | {N} |
| **合計** | **{N}** | **{N}** | **{N}** |

## 🔴 嚴重問題

### [{序號}] {問題標題}
- **檔案**：{路徑}:{行號}
- **Reviewer**：{logic/quality/performance}
- **問題**：{描述}
- **建議**：{修復建議}

## 🟡 改善建議

### [{序號}] {建議標題}
- **檔案**：{路徑}:{行號}
- **Reviewer**：{reviewer}
- **建議**：{描述}

## 🟢 良好實踐

{正面反饋清單}

## 交叉審查發現

{Reviewers 之間互相分享後發現的額外觀點}
```

### 7. 落檔的兩件事（摘要一行 + 狀態）

**7a. plan.md「檢查報告摘要」節 append 一行**

依 `references/plan-common.md`「寫入紀律」用 **Edit** 對 `<!-- crew:rep  append-only -->` 那一整行插入，格式固定：

```text
- [{YYYY-MM-DD}] review {PASS|WARN|FAIL}｜🔴{N} 🟡{N}｜{一句話結論}
```

🔴 只寫這一行：逐條發現不進 plan.md（該節上限 6 行），🔴 不得整節取代、不得動別節。
日期用 `date +%F` 的實際輸出。結論詞：無 🔴 → `PASS`；有 🟡 無 🔴 → `WARN`；有 🔴 → `FAIL`。

**7b. 寫回 state.json（唯一狀態權威）**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" result --slug {slug} \
  --kind review --status {PASS|WARN|FAIL} \
  --set critical={🔴 數} --set warning={🟡 數} --set files={審查檔案數} --set mode={full|quick}
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" set --slug {slug} \
  --step review --status done --phase review
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" validate --slug {slug} --expect-phase review
```

`validate` exit 1 → 依訊息修正後重跑；仍失敗 → `crew-state.py rebuild --slug {slug}`。

### 8. 回傳結果

```
程式碼審查完成！

📋 報告：見上方對話全文（依設計不落檔）
📊 統計：🔴 {N} 嚴重 / 🟡 {N} 建議 / 🟢 {N} 良好
📝 已寫入：plan.md 摘要一行 + state.json results.review
🔍 錨點 pre-check：{全部有效 / ⚠️ N 筆 / 本次未檢查（原因）}

{若有嚴重問題}
⚠️  發現 {N} 個嚴重問題，建議修復後再結案。

後續可使用：
  • 修正問題後再次 /plan-review
  • /plan-drift   — 修錨點失效（結案前一定要清乾淨）
  • /plan-close   — 結案並同步 Notion
```

---

## 何時不用

分工邊界：本 skill 專責 CREW `.spec` 任務的多角色交叉審查，其餘審查需求請改用下列指令。

- 一般 diff code review → 內建 `/code-review` 或 `codex`
- Java 最佳實務審查 → 個人 `java-code-review`
- 提交前驗證需求覆蓋 → `superpowers:requesting-code-review`
- 安全掃描 → `/plan-security`；架構設計建議 → 個人 `java-design-advisor`

---

## Gotchas

- **3 人並行的 token 消耗約為單次的 5-6 倍**：3 位 Reviewer 各自讀取完整程式碼 + 設計文件，再加上交叉審查。小變更（< 5 個檔案）建議用 `--quick` 模式（單一 Subagent），節省 80% token。
- **交叉審查傾向「無中生有」**：三位 Reviewer 獨立審查都沒嚴重問題時，交叉審查階段不太可能突然冒出真正嚴重的問題。Leader 彙整時應對交叉審查新增的「嚴重」問題持保留態度，優先信任獨立審查的結果。
- **merge-base 的主分支名稱**：`{prod_branch}` 從專案設定檔的 `prod_branch` 欄位讀取（由 `/project-add` 設定）。若未設定，回退邏輯：先取 `origin/HEAD` 指向的分支，若無則依序嘗試 `production` → `master` → `main`。
- **報告不落檔是刻意的**：使用者要的是「當下看得到」。存成 `.spec/review.md` 之後，程式碼一改它就變成錯的，還會被 `/plan-close` 原樣推到 Notion 汙染知識庫。要留痕就留 plan.md 那一行摘要與 `state.json`。
- **R0 只是輸入，不是關卡**：pre-check 有 FAIL 也照樣審查。真正的關卡在 `/plan-close`（D1／D2 擋結案），要修去 `/plan-drift`。
- **`git status` 別漏**：只跑 `git diff merge-base..HEAD` 會漏掉還沒 commit 的變更，剛跑完 `/plan-build` 的檔案通常都還沒 commit。

---

## 邊界情況

- **無程式碼可審查**：提示先執行 `/plan-build` 或 commit 程式碼
- **plan.md 只有骨架（尚未 `/plan`）**：仍可審查，但在報告開頭標「無驗收條件可對照，本次只做程式碼層面審查」
- **`check-spec-drift.py` 回 exit 3**：R0 標「本次未檢查」＋原文的「修法：」，不阻擋、不改判為漂移
- **Host 無 parallel capability**：自動序列執行 3 個 reviewer；若使用者明確要省成本才建議 `--quick`
- **交叉審查發現嚴重問題**：提供選項：修正後重新審查 / 忽略繼續 / 終止
- **Reviewer 失敗**：提供選項：重試 / 跳過該 Reviewer / 終止
- **--quick 模式**：只執行一個 `delegate_readonly` reviewer（role=`logic-reviewer`、`model: sonnet`）
