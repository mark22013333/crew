---
name: bug-investigate
description: 假說驅動的 CREW Bug 根因調查 —— 自動收集證據、模式比對、假說驗證，全程同步 Notion 任務追蹤。當使用者提到 /bug-investigate、「調查 bug 根因」、「CREW bug 根因分析」時觸發此 Skill。
---

# bug-investigate — 假說驅動根因調查

AI 主動調查 Bug 根因：收集證據、比對已知模式、建立假說、驗證假說，全程自動更新 Notion「任務追蹤工具」的 Bug 頁面。

---

## 鐵律

> **沒有根因確認，不能開始修復。**
> 假設不等於根因。「我覺得是 XXX」不夠，需要證據支持。

---

## 紀律護欄

> 紀律護欄：`../../references/discipline-preamble.md`（通用紀律）＋ `../../references/anti-rationalizations.md`「bug-investigate 專用」＋ `../../references/boundaries.md`「bug-investigate」段＋ `../../references/state-discipline.md`「bug-investigate」段（斷點保險，進度即寫）；有「可以跳過」「應該夠了」的衝動時，停下查表確認是否為已知偏離模式。

---

## 前置條件

- 已使用 `/bug-start` 建立 Bug 條目（Notion 有「進行中」的 🐞 錯誤）
- 或使用者直接描述新的 bug 症狀（此時先執行 `/bug-start`；它會自動跑 Bug Intake Refiner + Human confirmation，再進入調查）

> **前置檢查**：參照 plugin 根目錄 `references/prerequisites.md`（相對 SKILL.md 為 `../../references/`）執行完整前置檢查（專案指令 + 設定檔 + 專案註冊）。

---

## 使用方式

```
/bug-investigate                        # 調查當前進行中的 bug
/bug-investigate NullPointerException   # 帶症狀描述開始調查
/bug-investigate --resume               # 繼續上次的調查（讀取 Notion 已有內容）
```

---

## 流程

### 1. 定位目標 Bug

與 `/bug-update` 相同邏輯：參照 plugin 根目錄 `references/locate-bug.md`（相對 SKILL.md 為 `../../references/`）。

若使用 `--resume`：讀取已有的「調查過程」區塊，從中斷點繼續；**既有 Bug 不重新跑 intake refinement**。

#### 1.1 綁定 Bug Runtime State（必須）

定位 Notion Bug 後，取得該頁面的 page ID，然後用 `crew-state.py list --all --format json` 找出
`state.notion.page_id == 目前 Bug page id` 的 `{slug}`。若本輪是由 `/bug-start` 剛建立，直接沿用它回傳的 slug。

- 找到多筆 → **BLOCK**，不得猜測，列出 slug 讓使用者決定。
- 找不到 → **BLOCK**，提示先用 `/bug-start` 建立／補齊最小 runtime state；不得自行 `init --force` 建第二份任務。
- 找到後先確認 `type=bug`，且 `next` 不得回任何 `/plan-*` 指令。

解析 plugin root：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
```

正常開始（非 `--resume`）時，先寫入調查階段與第一個可恢復工作單元：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" set --slug {slug} \
  --step investigate --status in_progress

python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" unit --slug {slug} \
  --skill bug-investigate --done 0 --total 1 --label "假說" \
  --remaining "建立並驗證第一個可驗證根因假說"
```

使用 `--resume` 時**不要重設 done/total**；先讀：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" next --slug {slug} --format json
```

若 `next.command` 是 `/bug-investigate --resume`，依 `work_unit.remaining / evidence / ambiguities` 與 Notion 調查紀錄接續；不得從 Phase 1 全部重做。

> 🔴 在 `investigate=done` 前，`work_unit` 必須保留可恢復斷點。正常收工才 `unit --clear`。

### 2. Phase 1：證據收集（自動，唯讀，profile: FAST）

AI 根據 bug 描述自動收集初始證據，不需使用者介入。

> **模型與邊界（硬性規則）**——完整政策見 plugin 根目錄 `references/model-policy.md`（相對 SKILL.md 為 `../../references/`）：
> - 2.1–2.5 的證據收集依 `../../references/host-capabilities.md` 使用 **`delegate_readonly`**，routing=`task: evidence_collection`、`profile: FAST`、`risk: low`、`complexity: low`；執行前用 `crew-model-route.py` 取得 Host mapping。Host 無 subagent 時可 inline 執行，但仍是唯讀。
> - 互不依賴的收集項（log／Git 歷史／環境狀態／知識庫與學習搜尋）可在同一則訊息並行派出，回報只給結論與 `檔案:行號`，不貼大段原文。
> - 🔴 `/bug-investigate` **全程不修改正式程式碼**；只寫 Notion 調查紀錄、`.spec/` 與 `state.json`。
> - 🔴 沒有根因確認，不得進入修正（不自動觸發 `/bug-fix`）。
> - 🔴 Phase 1 只負責蒐證，不做深度根因推理；後續只有符合 4.4 升級條件時才可進 DEEP。
> - 🔴 不自動啟動 Dynamic Workflow、不依賴 `/effort ultracode`；沒有它本 skill 也要能跑完。

#### 2.1 錯誤 Log 搜集

根據專案類型決定搜集方式：

```bash
# 搜尋專案中的 log 檔案
find . -name "*.log" -mmin -60 -type f 2>/dev/null | head -5

# 若有 Docker 容器
docker ps --format '{{.Names}}' 2>/dev/null | head -5
```

找到 log 來源後：

- **log 檔案在磁碟** → 使用 Read tool 讀取（精確除錯需保留原始 timestamp／request ID 順序，勿用會截斷或壓縮輸出的方式）
- **需要 shell 指令** → 用 Bash tool 執行（如 `grep`、`docker logs`、`tail`）；輸出量大時導到檔案再用 Read tool 讀

搜集策略：
- grep ERROR / Exception / FATAL（最近 30 分鐘）
- 擷取完整 stacktrace（從 Exception 行到下一個非 `at` 行）
- 記錄時間戳和頻率

#### 2.2 Git 歷史分析

```bash
# 最近 10 筆 commit
git log --oneline -10

# 最近修改的檔案
git log --since="3 days ago" --name-only --format="" | sort | uniq -c | sort -rn | head -10

# 若 stacktrace 提到特定檔案，查該檔案的最近變更
git log --oneline -5 -- <affected-file>
git diff HEAD~5..HEAD -- <affected-file>
```

#### 2.3–2.5 環境狀態／知識庫搜尋／學習搜尋

與 `/bug-start` 共用收集指令，參照 plugin 根目錄 `references/evidence-collection.md`（相對 SKILL.md 為 `../../references/`）「共用收集項目」段。

本 skill 專屬差異：2.4 知識庫搜尋的關鍵字來源為「bug 描述和 stacktrace 擷取核心詞」（比 bug-start 的標題關鍵字更廣）；2.5 學習搜尋取 `tail -5`（bug-start 取 `tail -3`），且若有匹配的歷史學習 → 除了最後寫入 Notion 之外，AI 應立即顯示：「歷史學習：{insight}（{date}，confidence {N}/10）」，讓使用者在調查當下就看到，不必等到 Notion 寫入才知道。

#### 2.6 寫入 Notion

將收集到的證據寫入 Notion 頁面「調查過程」區塊。

**重要**：使用 `update_content` 前，必須先 `notion-fetch` 取得現有內容，將新內容附加到現有內容後面再寫回，避免覆蓋。

寫入格式：標題為「### [HH:mm] 自動收集的證據」，先列本 skill 專屬的「錯誤 Log」「最近變更」，再接 `references/evidence-collection.md`「共用 Notion 寫入格式」段的三段共用區塊（環境狀態／歷史參考／歷史學習）：

```markdown
### [HH:mm] 自動收集的證據

**錯誤 Log**：
```
{擷取的 ERROR/Exception，含 stacktrace}
```

**最近變更**（3 天內）：
- {commit hash} {message}（{affected files}）

（接續共用區塊：環境狀態／歷史參考／歷史學習，見 references/evidence-collection.md）
```

### 3. Phase 2：模式比對（profile: STANDARD）

AI 根據收集到的證據，比對已知 bug 模式表（plugin 根目錄 `references/bug-patterns.md`，相對 SKILL.md 為 `../../references/`）。

> 模式比對、跨檔語意閱讀與一般假說推理屬正常工程 debugging：routing=`task: debugging`、`profile: STANDARD`、`risk: medium`、`complexity: medium`。
> 執行前用 `crew-model-route.py` 取得 Host mapping；需要委派時依 `../../references/host-capabilities.md` 使用 **`delegate_readonly`**，role=`bug-investigator`，並把上述 routing 結構化傳入。Host 無 subagent 時可 inline 執行，但仍遵守 STANDARD profile 與唯讀邊界。

讀取 plugin 根目錄 `references/bug-patterns.md`（相對 SKILL.md 為 `../../references/`）的 7 種模式定義，將證據中的症狀逐一比對：

```
依據證據比對結果：

  症狀：NullPointerException at PushService.java:235
  模式比對：NPE / NullPointer（confidence: 高）
  調查方向：追蹤 null 來源 — 參數傳入？DB 查詢回傳？API 回應？

  相關歷史：知識庫中有 2 筆同檔案的 NPE 記錄
```

寫入 Notion「調查過程 > 初步判斷」：

```markdown
### [HH:mm] 模式比對

**匹配模式**：NPE / NullPointer
**調查方向**：追蹤 null 來源
  - PushService.java:235 的 `accessToken` 可能為 null
  - 需確認 token 取得邏輯和過期處理
**歷史參考**：同檔案有 2 筆 NPE 歷史（2026-02-15、2026-01-20）
```

### 4. Phase 3：假說建立與驗證

#### 4.1 建立假說

AI 根據證據和模式比對，提出具體、可驗證的假說：

```
根因假說 #1：
  「PushService.getAccessToken() 在 token 過期後回傳 null，
   而 PushService.sendPush() 未檢查 null 就呼叫 token.getValue()」

驗證方式：
  1. 讀取 PushService.java 的 getAccessToken() 方法
  2. 確認 token 過期邏輯
  3. 檢查 sendPush() 是否有 null check
```

#### 4.2 執行驗證

AI 根據驗證方式執行具體操作：

```bash
# 讀取相關程式碼
grep -n "getAccessToken\|sendPush\|accessToken" src/main/java/.../PushService.java
```

使用 Read tool 讀取關鍵方法的完整實作。

若需要 DB 查詢驗證（且 DB MCP 可用）：

```
使用 execute_sql 查詢相關資料狀態
```

若需要 API 測試驗證：

```bash
curl -s "http://localhost:8080/api/xxx" -H "Authorization: Bearer <token>"
```

#### 4.3 判定結果

- **假說確認** → 進入 Phase 4
- **假說否定** → 記錄為什麼不對，修正假說

寫入 Notion：

```markdown
### [HH:mm] 假說 #1 驗證

**假說**：token 過期後 getAccessToken() 回傳 null
**驗證結果**：❌ 否定
**原因**：getAccessToken() 有 null check，過期時會自動 refresh
**新線索**：refresh 呼叫的 API endpoint 回傳 HTTP 401 時沒有 retry 邏輯
```

同一個假說的結果一落地，就**立即**更新 runtime 工作單元，不等整批調查結束。

若假說 #N 被否定，並已建立下一個假說 #N+1：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" unit --slug {slug} \
  --skill bug-investigate --done {N} --total {N+1} --label "假說" \
  --evidence "假說 #{N} 已否定：{一行證據}" \
  --remaining "假說 #{N+1}：{下一個可驗證假說}"
```

這樣若此刻中斷，`crew-state.py next` 必須回 `/bug-investigate --resume`。

若某假說看似確認、但第 7 節仍有可能推翻根因的釐清問題，**先不要把該假說單元標成完成**；
把問題寫入 `--ambiguity` / `--remaining`，等釐清後再完成該單元。

#### 4.4 3-Strike 升級規則

若連續 3 次假說都被否定：

```
⚠️  已嘗試 3 次假說，全部被否定。

已排除的方向：
  1. Token 過期 — getAccessToken() 有自動 refresh
  2. API 回傳 401 — retry 邏輯存在但只 retry 1 次
  3. 網路超時 — timeout 設定正常（30s）

建議：
  • 需要更多資訊（log 時間範圍擴大？不同環境？）
  • 可能需要在測試環境重現
  • 或請熟悉此模組的同事協助

要繼續標準調查、升級深度根因推理，還是暫停？
```

- 使用者選擇**繼續** → 重置計數器，維持 `profile: STANDARD` + `task: debugging` 繼續調查。
- 使用者選擇**暫停** → 記錄當前進度到 Notion，並把下一個待查方向留在 `work_unit.remaining`；**不要**把 investigate 標成 done、不要 clear work_unit。此時 `next` 應維持 `/bug-investigate --resume`。
- 使用者選擇**升級** → 依下方「升級 DEEP 深度推理」執行。

#### 4.5 升級 DEEP 深度推理（條件式）

完整政策見 plugin 根目錄 `references/model-policy.md`（相對 SKILL.md 為 `../../references/`）。
預設維持 `profile: STANDARD`；🔴 **不得因第一次假說被否定就升級**。只有符合下列任一條件才允許升級：

- 連續三個可驗證假說都被證據否定（即 4.4 的 3-Strike）
- 問題跨越三個以上模組
- 涉及複雜並行、交易一致性、記憶體或分散式狀態
- 多份證據互相矛盾
- 一般 STANDARD 調查無法收斂
- 使用者明確要求深度分析

升級前，STANDARD 調查角色必須先整理下列交接（寫入 Notion「調查過程」並附在派工 prompt 內）：

```markdown
## 深度調查交接

### 已確認事實
- ...

### 已排除假說
- ...

### 相關檔案與方法
- ...

### 關鍵證據
- ...

### 尚未解答的問題
- ...
```

派工前先用 Router 取得深度 mapping：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-model-route.py" route \
  --task deep_investigation --risk high --complexity high \
  --host portable --format json
```

派工規則：依 `../../references/host-capabilities.md` 使用 **`delegate_readonly`**，role=`deep-investigator`，
routing=`task: deep_investigation`、`profile: DEEP`、`risk: high`、`complexity: high`。
Host adapter 必須依 Router mapping 套用可用的模型／reasoning；做不到 per-worker routing 時回報 `routing_degraded=true`，不得假裝已套用。
DEEP 角色 **只針對「尚未解答的問題」推理**，🔴 不得重做全部證據收集，🔴 不得修改正式程式碼（本 skill 仍是唯讀調查）。

### 5. Phase 4：根因確認

假說確認後，將根因寫入 Notion「根因分析」區塊：

```markdown
## 🧠 根因分析

- **問題根因**：LINE API 的 access token refresh 端點偶爾回傳 HTTP 503，
  而 getAccessToken() 的 retry 邏輯只重試 1 次且未處理 503 狀態碼，
  導致第二次推播時 accessToken 為 null。
- **問題檔案**：PushService.java:235
- **問題程式碼**：
  ```java
  // retry 只處理 401，未處理 503
  if (response.getStatusCode() == 401) {
      return refreshToken();
  }
  return null; // ← 503 時走到這裡
  ```
```

同時更新 Notion 頁面屬性：
- 根因分類 → 自動推斷（此例：「第三方API」）

### 6. Phase 5：調查報告

產出結構化調查報告，寫入 Notion 頁面底部：

```markdown
---

## 📋 調查報告

| 項目 | 值 |
|------|-----|
| 調查日期 | {YYYY-MM-DD} |
| 調查時長 | {N} 分鐘 |
| 假說嘗試 | {N} 次（確認第 {N} 次） |
| 證據來源 | Log + Git + 知識庫 |

### 時間線
1. [HH:mm] 收集證據 — stacktrace + 最近 commit
2. [HH:mm] 模式比對 — NPE 模式，追蹤 null 來源
3. [HH:mm] 假說 #1 否定 — token refresh 正常
4. [HH:mm] 假說 #2 確認 — 503 未處理
5. [HH:mm] 根因確認
```

### 7. 釐清問題（條件觸發）

調查報告產出後，AI 自我檢查是否有**無法自行確認的關鍵問題**。只在以下情況觸發：

- 根因假說已確認，但涉及 AI 無法驗證的商業邏輯（如「這個行為是 bug 還是 spec？」）
- 調查中發現環境差異，需使用者確認（如「正式環境的 API endpoint 跟測試環境一樣嗎？」）
- 重現步驟不完整，影響根因判斷

**不觸發**的情況（直接跳到回傳結果）：
- 根因已明確確認且不涉及商業邏輯疑問
- 3-Strike 升級已由使用者回答過

#### 觸發時的格式

```
❓ 調查中有 {N} 個問題需要釐清：

1. {問題描述}
   背景：{為什麼需要釐清，對根因判斷的影響}

2. {問題描述}
   背景：{為什麼需要釐清}
```

限制 1-3 個問題，只列真正影響後續修復方向的關鍵問題。

#### 使用者回答後

根據釐清結果，可能：
- **修正根因**：更新 Notion 頁面的根因分析
- **補充根因細節**：在原有根因上附加商業背景
- **根因不變**：釐清確認了原有判斷

然後進入回傳結果。

### 7.5 Runtime 收尾（只有根因正式確認後）

只有符合以下全部條件才可把 `investigate` 標成完成：

1. 根因已由證據確認，不是「最可能」或尚待驗證的假說
2. 根因分析已寫入 Notion
3. 調查報告已寫入 Notion
4. 第 7 節若有關鍵釐清問題，已得到答案且不再可能推翻根因

先把最後一個假說單元標成完成，再清除 work unit：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" unit --slug {slug} \
  --skill bug-investigate --done {N} --total {N} --label "假說" \
  --evidence "假說 #{N} 已確認根因：{一行證據}"

python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" unit --slug {slug} --clear
```

最後才寫 step：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" set --slug {slug} \
  --step investigate --status done

python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" validate --slug {slug} \
  --expect-phase investigate

python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" next --slug {slug} --format json
```

exit gate：

- `steps.investigate.status == done`
- `work_unit.skill == null`
- `next.command == "/bug-fix"`

任一不成立 → 不得在回傳結果中宣稱「根因調查完成」。

### 8. 回傳結果

```
Bug 調查完成！

📋 根因：LINE API refresh 回傳 503 未處理
📊 調查過程：2 次假說，第 2 次確認
🔗 Notion：{頁面連結}
```

根據調查結果動態建議後續指令：

**根因已確認 → 建議修復：**
```
建議後續：
  • /bug-fix — 修復並驗證（根因已確認，可以開始修復）
```

**根因已確認但需要更多資訊 → 建議補充：**
```
建議後續：
  • /bug-update <補充> — 先補充更多環境資訊
  • /bug-fix            — 或直接開始修復
```

**根因未確認（3-Strike 暫停後）→ 建議擴大調查：**

回傳前先確認 `crew-state.py next --slug {slug} --format json` 的 command 為
`/bug-investigate --resume`；若不是，先修正 work_unit 斷點。

```
建議後續：
  • /bug-investigate --resume — 繼續調查（有新線索時）
  • /bug-update <新線索>      — 補充新發現的資訊
```

---

## 何時不用

- 非 CREW、未建 Notion 任務的一般除錯 → 個人 `investigate` skill 或 `superpowers:systematic-debugging`
- 根因已確認、要開始修 → `/bug-fix`
- 只把新證據補進既有頁面 → `/bug-update`
- CREW 環境本身為何不能用 → `/crew-doctor`

---

## Gotchas

- **Log 讀取保留原始輸出**：精確除錯場景（追蹤 timestamp、request ID、事件順序）用 Read tool 讀 log 檔；需 shell 指令時輸出量大就先導到檔案再 Read，避免輸出被截斷或壓縮而遺失順序資訊。
- **notion-update-page 的 update_content 是覆蓋**：每次寫入調查過程時，必須先 `notion-fetch` 取得現有內容，附加新內容後再寫回。
- **假說驗證不要改 code**：investigate 階段只讀取和查詢，不修改程式碼。修改是 bug-fix 的職責。
- **知識庫搜尋可能回傳不相關結果**：Bug 知識庫的關鍵字搜尋粒度較粗，AI 需判斷歷史 bug 是否真的相關，不要盲目採用歷史根因。
- **3-Strike 不是硬限制**：使用者可選擇繼續。3-Strike 的目的是「停下來思考」而不是「強制停止」。
- **釐清問題不是每次都觸發**：只在根因涉及 AI 無法自行驗證的商業邏輯或環境差異時才列出釐清問題。技術根因明確時直接給結論和建議指令，不要為了觸發釐清步驟而硬湊問題。
- **釐清問題限制 1-3 個**：超過 3 個表示調查不充分，應繼續調查而非丟問題給使用者。

## 邊界情況

- **沒有 log 可收集**：跳過 log 收集，從 git 歷史和程式碼分析開始
- **Bug 知識庫未設定**：跳過知識庫搜尋，不阻擋流程
- **學習檔案不存在**：跳過學習搜尋，首次使用時自動建立
- **DB MCP 不可用**：跳過 DB 查詢驗證，提示使用者手動查詢
- **使用者中途提供新線索**：接受新資訊，調整假說方向
- **--resume 時 Notion 內容被手動修改**：以 Notion 現有內容為準，不覆蓋
- **釐清問題使用者不回答**：若使用者跳過釐清問題直接要求下一步，視為「不需要釐清」，直接進入回傳結果
- **釐清結果推翻根因**：若使用者回答後發現根因需要修正，更新 Notion 後重新產出建議指令
