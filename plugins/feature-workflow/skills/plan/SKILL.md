---
name: plan
description: CREW 規劃 —— spec / db / arch 三個 pass 把決策與驗收條件寫進 .spec/{slug}/plan.md，DB 設計另產 deploy.sql（零 Notion 呼叫）。當使用者提到 /plan、「CREW 完整規劃」、「一次跑完 spec/db/arch」時觸發此 Skill。
argument-hint: "[spec|db|arch]"
---

# plan — 規劃三 pass（零 Notion 呼叫）

一個 CREW 任務的規劃只有**一份文件**：`.spec/{slug}/plan.md`。本 skill 以三個 pass 依序把內容填進它的章節，DB pass 另外產出 `deploy.sql`（唯一 SQL 事實來源）。

> **產出只有這些**：`plan.md` 的章節條目、`deploy.sql`、`state.json` 的階段更新。
> 🔴 不產生任何其他文件檔（規格書、DB 設計書、架構書、清單、日誌一律不落檔）。

> **v1 舊任務**：`.spec/{slug}/plan.md` 不存在 → 這是 v1 結構，依
> `../../references/legacy-v1.md` 的相容模式執行，並在開頭提示一次。
> 過渡期限定，到期本段連同該檔一併刪除。
---

## 使用方式

```
/plan            # 全跑：spec → db → arch
/plan spec       # 只跑規格 pass
/plan db         # 只跑 DB pass
/plan arch       # 只跑架構 pass
```

適用類型 **Feature**。活躍任務 `type=bug` → 提示改走 `/bug-investigate` → `/bug-fix`，本 skill 不執行。

---

## 鐵律：plan.md 寫入紀律

章節契約、owner 表、各節上限、錨點語法一律以 plugin 根目錄 `references/plan-common.md`（相對 SKILL.md 為 `../../references/`）「plan.md 章節契約」為準。本 skill 執行時必須守住：

1. **只用 Edit，不用 Write** —— plan.md 的骨架由 `/plan-start` 建立。本 skill 🔴 **嚴禁**整檔改寫、🔴 **嚴禁**把整個章節當 `old_string` 取代。
2. **插入點固定是該節錨點註解那一整行**：`old_string` = 錨點行原文，`new_string` = 錨點行原文 ＋ 換行 ＋ 新條目。
3. **subagent 不碰 plan.md** —— 三個 pass 的 subagent 只回傳「章節條目文字」，由本 skill（Leader）逐條 Edit 插入。唯一例外是 DB pass 的 `deploy.sql`（整檔由 DB pass 擁有，可 Write）。
4. **共享節 append-only** —— 決策紀錄／已知取捨與風險／指路只准新增條目；改變主意寫 `- D-7 [arch] 取代 D-3：…（原因：…）`，🔴 不刪舊條目。
5. **每條決策自帶 `[階段]` tag**：spec pass 寫 `[spec]`、db pass 寫 `[db]`、arch pass 寫 `[arch]`。
6. **不抄程式碼裡有的東西** —— API 表、欄位清單、方法簽章、類別清單、DDL 一律用錨點（`@code:` / `@sql:`）指過去。

---

## 流程

### 0. 定位活躍任務 + 讀取專案上下文

參照 plugin 根目錄 `references/plan-common.md`（相對 SKILL.md 為 `../../references/`）的「定位活躍任務」與「讀取專案上下文」。

單跑模式（`/plan db`）不檢查前一個 pass 是否完成，但要在回報中標註「前置 pass 未完成，本次僅依現有內容設計」。

---

### Pass 1 — spec（目標、驗收條件、範圍決策）

> 只在 `/plan` 或 `/plan spec` 時執行。

#### 1-1. 派工

依 `../../references/host-capabilities.md` 呼叫 **`delegate_readonly`**（role=`feature-spec-analyst`、`model: sonnet`）。

> **模型與邊界（硬性規則）**——完整政策見 plugin 根目錄 `references/model-policy.md`（相對 SKILL.md 為 `../../references/`）：
> - Capability request 必須實際帶 `model: sonnet`；只在 prompt 裡描述模型名稱不算。Host 若無法精準指定 worker model，依 `host-capabilities.md` 降級並回報。
> - 本 pass 只做需求分析、程式碼探索與規格判斷；🔴 禁止修改正式程式碼。
> - 🔴 禁止自動啟動 `/plan-build`（或任何實作階段 skill）、禁止啟動實作委派、禁止要求 Host-specific Dynamic Workflow。
> - 🔴 不得因需求文件多或內容長就自行升級 Opus；範圍過大就分節產出。
> - 規格確認迴圈（1-3）照原樣執行，不可略過。

**輸入**：`.spec/{slug}/plan.md` 現有內容 ＋ 步驟 0 載入的專案上下文 ＋ 使用者在指令中補充的需求。

**要求 subagent 回傳（不得寫檔）**：

```text
[goal]  ≤12 行：為何做、In Scope、Out of Scope
[ac]    ≤15 行：- [ ] AC-1 {可機器驗證的一句話}
[dec]   範圍判斷條目（固定第一條）：
        - D-1 [spec] 範圍判斷：TASK_TYPE={feature|adjustment|bugfix|refactor|performance}、
          CHANGE_SCOPE={full|backend-only|frontend-only|api-only|db-only}、
          FRONTEND_REQUIRED={true|false}（FRONTEND_TECH={JSP|Vue|React|無}）、
          DB_REQUIRED={true|false}（DB_TABLES=…）、NEW_API={true|false}、
          EXISTING_API_CHANGE={true|false}｜理由：…
        其餘 [spec] 決策每條一行：決策｜理由｜被否決方案＋否決理由
[risk]  ≤8 行：明知的技術債、邊界外情境
[map]   已探索到的關鍵既有程式碼錨點：`@code:<relpath>#<symbol>` (L{行號})
```

🔴 回傳中不得出現 API 端點表、欄位清單、方法簽章 —— 那些是程式碼的事實，用 `[map]` 錨點指過去。

#### 1-2. 寫入 plan.md

依「鐵律」逐節 Edit 插入：`crew:goal`、`crew:ac`（owner=spec，首次插入；修訂時只 Edit 要改的那幾行）、`crew:dec`、`crew:risk`、`crew:map`（append-only）。

#### 1-3. 規格確認迴圈（必須執行）

> ⚠️ **硬性規則**：spec pass 寫入後，🔴 禁止自動進入 db／arch pass，🔴 禁止直接開始寫程式碼。必須進入以下迴圈，直到使用者明確表示沒問題。

摘要「目標與範圍」「驗收條件」「D-1 範圍判斷」給使用者，然後：

```
規格已寫入 .spec/{slug}/plan.md（目標與範圍／驗收條件／決策紀錄）

請確認是否需要調整？
  • 直接告訴我要修改的部分，我會用 Edit 更新對應條目
  • 若確認沒問題，我會繼續下一個 pass
```

使用者提出修改 → **先讓既有 requirement approval 失效**（若原本已 approved/waived），再只 Edit 受影響的那幾行（不重寫整節）→ 摘要本次修改 → 再問一次：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" gate --slug {slug} \
  --name requirement --status pending --by crew \
  --reason "spec revised; human re-approval required"
```

使用者回「沒問題／OK／確認／可以了」才算通過。

> 🔴 **Approval Gate 硬規則**：
> - 只有使用者在**本次確認迴圈中明確表示核准**，才可以把 requirement gate 設為 approved。
> - 沉默、Enter、沒有提出修改、前一輪曾經核准，都**不等於本次核准**。
> - Agent 不得自行 approve，不得因為「規格看起來合理」代替使用者決策。
> - spec 任何實質修訂都要重新核准；不得沿用舊 approval。

#### 1-4. 收尾

只有在 1-3 已取得使用者明確核准後，依序執行：

```bash
# 先完成 spec；runtime 規定 source step 完成後才能批准 requirement gate
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" set --slug {slug} --step spec --status done --phase spec

# 這一行代表「人類剛剛明確核准」，Agent 不得自行觸發
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" gate --slug {slug} \
  --name requirement --status approved --by human \
  --reason "user explicitly approved current spec"

# exit gate：requirement 未 approved/waived 就視為 spec pass 尚未安全收尾
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" validate --slug {slug} \
  --expect-phase spec --require-gate requirement
```

---

### Pass 2 — db（表結構決策 + deploy.sql）

> 只在 `/plan` 或 `/plan db` 時執行。

#### 2-1. DB_REQUIRED 判斷

讀 plan.md 決策紀錄的 `D-1 [spec] 範圍判斷`。`DB_REQUIRED=false` → **跳過本 pass**，不產生 `deploy.sql`，並記錄跳過事實（不是假裝沒這個階段）：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" set --slug {slug} --step db --status skipped --reason "DB_REQUIRED=false"
```

#### 2-2. 派工

依 `../../references/host-capabilities.md` 呼叫 **`delegate_readonly`**（role=`feature-db-designer`、`model: opus`）。表結構、索引、約束與交易一致性屬複雜架構決策，🔴 不得因為「只產一個 SQL 檔」而主動降級模型目標。

**輸入**：plan.md 現有內容（目標／驗收條件／決策紀錄）＋ `project_instructions` 取得的 DB 類型 ＋ Host 可用的 DB 規則（Claude adapter 可額外讀取 `~/.claude/rules/database.md`）＋ 既有 Entity／Mapper 的命名慣例。

**要求 subagent 產出**：

1. **`.spec/{slug}/deploy.sql`（唯一 SQL 事實來源，可用 Write 整檔寫）** —— 依部署順序：`CREATE TABLE` → `CREATE INDEX` → `ALTER TABLE` → 範例／初始資料 `INSERT`，檔尾以註解分隔的 Rollback 段（逆序 `DROP`）。DDL 只存在這一個檔案，🔴 不得複製到 plan.md。
2. **回傳章節條目（不得寫 plan.md）**：

```text
[dec]   - D-n [db] {表／索引／型別／約束的取捨}｜理由：…｜否決：…（否決理由）
        表結構本身用錨點：見 `@sql:deploy.sql#{table_name}`
[risk]  資料量成長、鎖競爭、遷移風險等明知的取捨
[map]   - 資料表：`@sql:deploy.sql#{table_name}`（每張新表一行）
```

#### 2-3. 寫入與收尾

Leader 依「鐵律」把條目 Edit 插入 `crew:dec` / `crew:risk` / `crew:map`，並登記部署步驟數（取代舊的部署清單文件）：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" set --slug {slug} --deploy-total {deploy.sql 中的執行步驟數} --deploy-confirmed 0
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" set --slug {slug} --step db --status done --phase db
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" validate --slug {slug} --expect-phase db
```

---

### Pass 3 — arch（分層與設計模式決策）

> 只在 `/plan` 或 `/plan arch` 時執行。

#### 3-1. 派工

依 `../../references/host-capabilities.md` 呼叫 **`delegate_readonly`**（role=`feature-backend-designer`、`model: opus`）。分層決策與設計模式選擇屬複雜架構決策，🔴 不得主動降低模型目標。

**輸入**：plan.md 現有內容 ＋ `deploy.sql`（若有）＋ 專案 package 結構與 1-2 條既有呼叫鏈。

**要求 subagent 回傳（不得寫檔）**：

```text
[dec]   - D-n [arch] {分層歸屬／介面切割／設計模式／依賴方向的取捨}｜理由：…｜否決：…
        與既有慣例衝突時，寫明「為何這次不照舊」
[risk]  擴充性、效能、與既有模組耦合的已知取捨
[map]   要新增或改動的落點：`@code:<relpath>#<symbol>`（尚未存在的檔案用 T1 僅路徑）
```

🔴 回傳中不得出現 Mermaid 圖、完整類別清單、介面方法簽章 —— 那些在 `/plan-build` 產碼後就是程式碼事實，用 `[map]` 錨點指過去。

#### 3-2. 寫入

在對 plan.md 做任何**實質架構修訂之前**，先讓既有 architecture approval 失效：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" gate --slug {slug} \
  --name architecture --status pending --by crew \
  --reason "architecture revised; human re-approval required"
```

然後 Leader 逐條 Edit 插入 `crew:dec` / `crew:risk` / `crew:map`。

> 若本次只是重跑但沒有任何實質架構變更，不需要為了形式重設 gate；只要 plan.md 的架構內容有改，就必須 reset pending。

#### 3-3. 架構確認迴圈（必須執行）

摘要本次架構決策給使用者，至少包含：

- 分層／模組落點
- 主要依賴方向與介面切割
- 與既有慣例不同的地方及理由
- 已知取捨與風險

然後詢問：

```text
架構決策已寫入 .spec/{slug}/plan.md。

請確認是否需要調整？
  • 直接告訴我要修改的部分，我會只 Edit 對應條目
  • 若確認沒問題，我會核准 architecture gate，之後才能進 /plan-build
```

使用者提出修改 → 保持 `architecture=pending` → 只 Edit 受影響條目 → 摘要修改 → 再問一次。

使用者在**本輪**明確回「沒問題／OK／確認／可以了」才算通過。

> 🔴 **Architecture Approval Gate 硬規則**：
> - 只有使用者本輪明確核准，才可以把 architecture gate 設為 approved。
> - 沉默、Enter、沒有再提出修改、requirement 已核准，都**不等於架構核准**。
> - Agent 不得自行 approve，也不得用「符合既有架構」取代人的決策。
> - 架構任何實質修訂都必須回到 `pending` 並重新取得核准。

#### 3-4. 收尾

只有 3-3 已取得使用者明確核准後，依序執行：

```bash
# 先完成 arch；runtime 規定 source step 完成後才能批准 architecture gate
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" set --slug {slug} --step arch --status done --phase arch

# 這一行代表「人類剛剛明確核准」，Agent 不得自行觸發
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" gate --slug {slug} \
  --name architecture --status approved --by human \
  --reason "user explicitly approved current architecture"

# exit gate：architecture 未 approved/waived 就不能安全進 build
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" validate --slug {slug} \
  --expect-phase arch --require-gate architecture
```

---

### 4. 退出驗證（強制，不可跳過）

| # | 檢查項目 | 驗證方式 | 失敗處理 |
|---|---------|---------|---------|
| E0 | 狀態已更新 | spec：`validate --expect-phase spec --require-gate requirement`；db：`validate --expect-phase db`；arch：`validate --expect-phase arch --require-gate architecture` | 依訊息修正後重跑；仍失敗 → `crew-state.py rebuild --slug {slug}` |
| E1 | 六個錨點註解仍各只出現一次 | `grep -c 'crew:goal\|crew:ac\|crew:dec\|crew:risk\|crew:map\|crew:rep' .spec/{slug}/plan.md` 為 6 | 表示有人整段取代了骨架 → 用 `git diff` 找回被吃掉的條目再補 |
| E2 | plan.md 未超篇幅 | `wc -l .spec/{slug}/plan.md` ≤ 100 | 壓縮既有條目或 supersede，🔴 不得另開檔案 |
| E3 | 沒有抄寫程式碼事實 | plan.md 內無 `CREATE TABLE`／方法簽章／API 端點表 | 刪掉抄寫段，改成 `@code:` / `@sql:` 錨點 |
| E4 | DB pass 的 SQL 只有一份 | `.spec/{slug}/` 下只有 `deploy.sql` 一個 `.sql` | 合併去重，保留 `deploy.sql` |

### 5. 回傳結果

```
規劃完成（{已執行的 pass}）！

📁 .spec/{slug}/plan.md（{N} 行）
🗄️ .spec/{slug}/deploy.sql（{M} 個部署步驟；DB_REQUIRED=false 時不顯示此行）
📊 階段：{spec|db|arch}

本次新增條目：
  • 驗收條件 {n} 條
  • 決策 D-{a}…D-{b}
  • 指路錨點 {k} 個

後續可使用：
  • /plan-build  — 多角色協作產生程式碼
  • /plan-review — 多角色程式碼審查
  • /plan-next   — 不確定下一步時問它
```

---

## 何時不用

- 只跑其中一個階段 → 本 skill 的 `/plan spec`、`/plan db`、`/plan arch`（不再有獨立指令）
- 規劃前發散討論 → 改用 `/plan-explore`
- 建任務入口（Notion + branch + plan.md 骨架）→ 改用 `/plan-start`
- Bug 的調查與修復 → `/bug-investigate` → `/bug-fix` → `/bug-close`
- 一般寫實作計畫文件（非 CREW 流程）→ 改用 superpowers:writing-plans

---

## Gotchas

- **「取代整段」是這份文件最大的風險**：三個 pass 共用決策紀錄／風險／指路三節。任何一個 pass 用整節取代，都會靜默吃掉別的 pass 寫的條目，而 lint 與測試都抓不到。收工前用 `git diff -U0 .spec/{slug}/plan.md | grep '^-'` 確認刪除行數為 0（修訂 goal／ac 除外）。
- **錨點註解不可美化**：`<!-- crew:dec  append-only -->` 的空白數量都是插入點比對的一部分，不要重新對齊或翻譯。
- **單跑不等於可以跳過確認**：`/plan spec` 必須完成 requirement confirmation；`/plan arch` 必須完成 architecture confirmation；`/plan db` 寫入後仍要摘要結果，但沒有獨立人類 approval gate。
- **DB_REQUIRED=false 要留痕**：跳過 db pass 時務必寫 `--status skipped --reason`，否則下游只會看到「沒有 deploy.sql」而必須用猜的。
- **委派的 model 目標**：prompt 中只寫模型名稱不算；capability request 必須帶結構化 `model`，Host 對映與降級規則見 `references/host-capabilities.md`，角色政策見 `references/model-policy.md`。
- **plan.md 不是需求垃圾桶**：使用者貼的長需求原文不要整段收進來 —— 萃取成目標／驗收條件／決策，原文留在 Notion 頁面。
