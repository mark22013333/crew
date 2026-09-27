---
name: bug-fix
description: CREW bug 修復紀律 —— 根因確認才能改（鐵律）、產出修復建議與迴歸測試、瀏覽器驗證，隸屬 CREW bug 流程。當使用者提到 /bug-fix、「進行 CREW bug 修復」、「開始修復這個 bug」時觸發此 Skill。
---

# bug-fix — 修復紀律

修復 Bug 前確認根因已記錄，修復後產出迴歸測試並驗證，確保修復品質。

---

## 鐵律

> **根因分析必須有內容，才能開始修復。**
> 根因分析空白 = 還沒調查完 = 不知道要修什麼。

---

## 紀律護欄

> 紀律護欄：`../../references/discipline-preamble.md`（通用紀律）＋ `../../references/anti-rationalizations.md`「bug-fix 專用」＋ `../../references/boundaries.md`「bug-fix」段＋ `../../references/state-discipline.md`「bug-fix」段（斷點保險，進度即寫）；有「可以跳過」「應該夠了」的衝動時，停下查表確認是否為已知偏離模式。

---

## 前置條件

- 已使用 `/bug-start` 建立 Bug 條目（Notion 有「進行中」的 🐞 錯誤）
- 修復程式碼已 commit 或即將 commit

> **前置檢查**：參照 plugin 根目錄 `references/prerequisites.md`（相對 SKILL.md 為 `../../references/`）執行完整前置檢查（專案指令 + 設定檔 + 專案註冊）。

---

## 使用方式

```
/bug-fix                  # 標準修復流程
/bug-fix --skip-test      # 跳過迴歸測試（僅限無法測試的場景）
/bug-fix --verify-only    # 只驗證（已修復，只要驗證 + 產出測試）
```

---

## 流程

### 1. 定位目標 Bug

與 `/bug-update` 相同邏輯：參照 plugin 根目錄 `references/locate-bug.md`（相對 SKILL.md 為 `../../references/`）。

### 2. 分支檢查

確保修復在正確的分支上進行（依 Git-flow 規定：修改應在 feature branch 提交，再 merge 回 DEV）。

1. 從 Bug Notion 頁面讀取「修復分支」欄位
2. 取得當前分支：`git branch --show-current`
3. 比對：

**修復分支有值 且 ≠ 當前分支**：

```
⚠️ 分支不一致

當前分支：{專案}_DEV
修復分支：feature/{任務簡述}

依 Git-flow 規定，修改應在 feature branch 提交，再 merge 回 DEV。

要切換嗎？
  1. 是，切換到 feature/{任務簡述}
  2. 否，繼續在當前分支修復
```

- 選 1 → 執行 `git checkout <修復分支>`，繼續流程
- 選 2 → 繼續，不改變分支（分支不一致僅為引導，不阻擋流程）

**修復分支無值 或 = 當前分支**：跳過，繼續原流程。

### 3. 鐵律檢查

讀取 Notion 頁面「根因分析」區塊：

- **有內容** → 繼續
- **空白** → 🔴 BLOCK

```
⚠️ 根因分析尚未填寫。

修復前必須確認根因，否則無法確定修的是對的地方。
  • /bug-investigate — AI 協助調查根因
  • 手動填寫 Notion 頁面的「根因分析」區塊後再回來

鐵律：沒有根因確認，不能開始修復。
```

### 4. 修復建議與實作（唯讀 FAST → 實作者 DEEP）

> **模型分工（硬性規則）**——完整政策見 plugin 根目錄 `references/model-policy.md`（相對 SKILL.md 為 `../../references/`）：
>
> | 階段 | 工作 | routing / model |
> |------|------|-----------------|
> | 4a 定位（唯讀） | 讀取已確認根因、定位相關檔案、搜尋相似修正模式、尋找既有測試範本 | `task: repository_search` + `profile: FAST` |
> | 4b 實作 | 決定修正策略、修改正式程式碼、處理跨模組影響、建立必要的迴歸測試 | `profile: DEEP`；Claude adapter 目前 `model: opus` |
> | 5 驗證執行 | 編譯／測試指令與 pass/fail 判定 | `profile: NONE`（deterministic tooling） |
> | 5 驗證整理（唯讀） | 大量編譯／測試輸出摘要、整理結果、更新 `.spec/` 或 Notion 紀錄 | `task: test_output_summary` + `profile: FAST` |
>
> - 4a 依 `../../references/host-capabilities.md` 使用 `delegate_readonly`，routing=`task: repository_search`、`profile: FAST`、`risk: low`、`complexity: low`；執行前由 `crew-model-route.py` 取得 Host mapping。
> - 4b **正式修改 Agent 必須維持 DEEP**；Claude adapter 目前實際傳入 `model: opus`。
> - 4a 與 4b **必須是兩個工作單元**，不是同一個 agent「先探索再實作」。
> - 4b 的實作者只吃 4a 的交接（相關檔案、呼叫關係、風格／測試範本、已確認限制、測試方式），🔴 不重新全域掃描 repository。
> - 🔴 沒有根因確認（步驟 3 BLOCK）不得進入 4b。🔴 最小 diff：只動與根因直接相關的程式碼。

AI 根據 Notion 頁面的根因分析，產出修復建議：

```
根據根因分析，建議修復方向：

📍 問題檔案：PushService.java:235
🔧 修復建議：
  1. 在 getAccessToken() 的 retry 邏輯中加入 503 狀態碼的處理
  2. retry 次數從 1 次增加到 3 次，含 exponential backoff
  3. 加入 accessToken null check（防禦性程式設計）

⚠️ 最小 diff 原則：只修改與根因直接相關的程式碼
```

使用者確認方向後自行修復，或請 AI 修復 —— 由 AI 修復時，依 `../../references/host-capabilities.md` 使用 **`delegate_write`**，role=`bug-fix-implementer`、`profile: DEEP`（Claude adapter 目前 `model: opus`），輸入 4a 的交接內容與最小 diff scope。Host 無獨立 worker 時可由主 Agent inline 實作，但不得放寬可寫範圍與驗證要求。

### 5. 修復後驗證

使用者修復並 commit 後，執行驗證：

#### 5.1 編譯檢查

```bash
# 自動偵測 build 指令
[ -f pom.xml ] && mvn compile -q 2>&1 | tail -5
[ -f build.gradle ] && gradle compileJava 2>&1 | tail -5
```

- 通過 → ✅
- 失敗 → 顯示錯誤，要求修正

#### 5.2 迴歸測試產出

若需要 AI **新增或修改迴歸測試程式碼**，這屬可寫工作，必須沿用 4b 的 `delegate_write` + `profile: DEEP`（Claude adapter 目前 `model: opus`）；不得交給 FAST 驗證整理角色。AI 根據根因分析和修復 diff 產出 1 個迴歸測試：

```
迴歸測試需滿足：
  1. 重現 bug 的前置條件（模擬觸發 bug 的狀態）
  2. 執行觸發 bug 的操作
  3. 斷言正確行為（不是「不拋異常」，是「回傳正確結果」）
  4. 包含 attribution 註解：
     // Regression: {Bug 標題}
     // Root cause: {根因摘要}
     // Date: {YYYY-MM-DD}
```

讀取專案現有測試風格（命名、框架、assertion style），產出風格一致的測試。

```bash
# 執行迴歸測試
mvn test -pl {module} -Dtest={TestClass} 2>&1 | tail -20
```

- 通過 → ✅ commit 測試：`git add {test-file} && git commit -m "test: 迴歸測試 — {bug 摘要}"`
- 失敗 → 修正一次，仍失敗 → 標記為 WARN，不阻擋

#### 5.3 UI 驗證（若為前端相關 bug 且 gstack 可用）

```bash
B="$HOME/.claude/skills/gstack/browse/dist/browse"
if [ -x "$B" ]; then
  echo "GSTACK_AVAILABLE=true"
fi
```

若 gstack 可用且 bug 涉及 UI：

```bash
$B goto <affected-url>
$B snapshot -i
# 操作重現步驟
$B click @eN
$B snapshot -D
$B screenshot .spec/{slug}/screenshots/bugfix-{N}-after.png
$B console --errors
```

#### 5.4 API 驗證（若為 API 相關 bug）

```bash
curl -s "http://localhost:8080/api/xxx" -H "Cookie: <cookie>" | head -50
```

檢查 HTTP 狀態碼 + 回應 body。

### 6. 驗證結果寫入 Notion

更新 Notion 頁面「驗證」區塊：

**重要**：使用 `update_content` 前，必須先 `notion-fetch` 取得現有內容，將新內容附加到現有內容後面再寫回，避免覆蓋。

```markdown
## 🧪 驗證

- [x] 本地測試通過（{日期}）
  - 編譯：✅ 通過
  - 迴歸測試：✅ {TestClass} 通過（commit: {hash}）
  - UI 驗證：✅ 截圖確認（{截圖路徑}）
- [ ] UAT 驗證通過
- [ ] 正式環境確認
- [ ] 通報者確認問題已解決
```

### 7. 回傳結果

```
Bug 修復驗證完成！

📍 修復檔案：{N} 個
🧪 迴歸測試：{TestClass}（✅ 通過）
📸 UI 驗證：{✅ / ⏭️ 跳過}
🔗 Notion：{頁面連結}

後續：
  • /bug-close — 結案並同步知識庫
  • 部署到 UAT 後在 Notion 勾選「UAT 驗證通過」
```

**分支引導**（若當前在 feature branch 且不是 DEV/PRD 分支）：

讀取 feature-workflow 的 `projects/{repo-id}.md` 取得 `dev_branch`。若取得成功，額外顯示：

```
🔀 分支引導：
  目前在 feature/{任務簡述}
  修復已 commit，後續請 merge 回 DEV：

  git checkout {dev_branch} && git merge feature/{任務簡述} --no-ff

  或使用 /bug-close 時自動引導 merge。
```

若 `dev_branch` 未設定，顯示通用提示：

```
🔀 分支引導：
  目前在 feature branch，記得修復完成後 merge 回開發分支。
```

---

## 何時不用

- 根因尚未確認 → 先 `/bug-investigate`（或個人 `investigate` / `superpowers:systematic-debugging`）
- 一般錯誤排查、非 CREW 任務 → 個人 `investigate` / `superpowers:systematic-debugging`
- 只想記錄修復結果並結案 → `/bug-close`
- typo 或瑣碎改動 → 直接改，無需本 skill

---

## Gotchas

- **根因分析空白的判斷**：Notion 頁面的「根因分析」區塊可能存在但內容只有模板佔位符（如「待填寫」、空白 bullet）。這種情況也算「空白」，應觸發 BLOCK。判斷標準是：去掉模板佔位符和空白行後，是否有實質內容。
- **迴歸測試風格匹配**：產出的測試檔案要與專案現有測試使用相同的框架（JUnit 5 / TestNG）、assertion library（AssertJ / Hamcrest）、命名風格（`should_xxx_when_yyy` / `testXxxWhenYyy`）。先搜尋 `src/test` 目錄中的現有測試作為範本。
- **--skip-test 的使用場景**：僅限以下情況：環境問題（如無法在本地跑測試）、設定類修復（如改 properties 檔）、純 SQL 修復（如改 DB 資料）。其他場景不應跳過。
- **gstack browse 可用性**：不是所有環境都有安裝 gstack。先偵測 `$HOME/.claude/skills/gstack/browse/dist/browse` 是否存在且可執行，再決定是否進行 UI 驗證。
- **dev_branch 取得路徑**：分支引導需要讀取 feature-workflow 的 `projects/{repo-id}.md`，但 bug-fix 是 bug-workflow 的 skill。需跨 plugin 讀取設定：先嘗試 `~/.claude-company/feature-workflow/projects/{repo-id}.md`，再嘗試 `~/.claude/feature-workflow/projects/{repo-id}.md`。讀取失敗時顯示通用提示。

---

## 邊界情況

- **設定檔不存在**：提示使用者先執行 `/bug-setup` 完成初始設定
- **根因分析空白**：BLOCK，引導使用者用 `/bug-investigate` 或手動填寫
- **無 commit 可檢查**：若使用者尚未 commit，提示先 commit 修復程式碼再執行 `/bug-fix`
- **編譯失敗**：顯示錯誤訊息，要求使用者修正後重新執行
- **迴歸測試無法產出**：某些修復（如純設定變更）難以寫自動化測試，標記為 WARN 並在 Notion 說明原因
- **gstack 不可用**：跳過 UI 驗證，在 Notion 標記「UI 驗證：⏭️ 跳過（gstack 不可用）」
- **API 驗證服務未啟動**：跳過 API 驗證，在 Notion 標記「API 驗證：⏭️ 跳過（服務未啟動）」
- **--verify-only 模式**：跳過『修復建議與實作』一節，直接從『修復後驗證』一節開始。編譯／測試執行本身是 `profile: NONE`；需要摘要大量輸出或整理紀錄時用 `task: test_output_summary` + `profile: FAST`。若驗證失敗且使用者同意修改程式碼，才進 `profile: DEEP` 的 `delegate_write` 實作者。
- **diff 過大（> 500 行）**：提示使用者確認是否所有變更都與 bug 修復相關，遵循最小 diff 原則；其他改善（如 code style、重構旁邊的邏輯）應在另一個 commit 完成，否則 revert 時會連帶
- **Bug 無「修復分支」欄位**：『分支檢查』一節跳過
- **feature-workflow 未安裝或未設定**：分支引導顯示通用提示，不阻擋流程
