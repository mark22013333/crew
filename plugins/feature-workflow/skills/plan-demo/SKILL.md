---
name: plan-demo
description: 純本地產出範例 .spec/ 任務，不依賴 Notion / 多角色委派 / DB MCP，讓評估者快速看到 CREW 完整流程效果。當使用者提到 /plan-demo、「評估 CREW 流程」、「CREW 試跑範例」時觸發此 Skill。
---

# plan-demo — 純本地評估模式

給未設定 Notion 但想評估 CREW 的人一個 5 分鐘看到完整流程的入口。
產出真實的 `.spec/demo-{task}/` 目錄，結構與真實任務**完全同構**：`plan.md` ＋ `state.json` ＋ `deploy.sql`，
但**不寫 Notion、不啟多角色委派、不連 DB MCP**。

> **這個 demo 想讓你看到的重點**：一個 CREW 任務只有一份給人讀的文件（`plan.md`），
> 它只寫**程式碼裡看不到的東西**（需求、決策與理由、被否決方案、驗收條件、取捨）；
> 「是什麼」（欄位、方法簽章、DDL、類別清單）一律用 `@code:` / `@sql:` 錨點指過去，**不抄寫**。
> 抄寫正是 Token 昂貴與文件漂移的共同根因。

---

## 紀律護欄

> 紀律護欄：`../../references/discipline-preamble.md`（通用紀律）＋ `../../references/anti-rationalizations.md`「plan-demo 專用」＋ `../../references/boundaries.md`「plan-demo」段。

---

## 使用方式

```
/plan-demo                       # 用內建預設範例「使用者管理 API」
/plan-demo <自訂題目>            # 簡短描述自訂任務（仍跑本地產出，不寫 Notion）
/plan-demo --keep                # 保留產出（純 UX 信號，效果與預設相同：預設本就不自動清理）
/plan-demo --cleanup             # 立即清除既有 demo 產物（.spec/demo-*/）
```

---

## 前置條件

**最低需求**：當前目錄有寫入權限即可。**不需要**：
- ❌ Notion MCP 安裝
- ❌ Notion 授權
- ❌ 平行委派能力（本 demo 不需要）
- ❌ DB MCP 安裝
- ❌ CLAUDE.md 或 /project-add 註冊
- ❌ `/bug-setup` 或 `/plan-setup`

若 CLAUDE.md 存在，demo 會用其中的技術棧資訊讓範例更貼合；若無，使用 `spring-boot-jpa` 預設範例。

---

## 流程

### 1. 確認題目

未指定 → 用內建範例：

```
題目：使用者管理 API
描述：提供使用者新增、查詢、更新、刪除（CRUD），含分頁與基本驗證
技術棧：Spring Boot + JPA（若 CLAUDE.md 偵測到其他棧則替換）
```

使用者指定 → 用該描述。

### 2. 產出 `.spec/demo-{slug}/` 目錄

`{slug}` 從題目自動產生（如「使用者管理 API」→ `user-management-api`）。
為避免污染真實 .spec，**前綴 `demo-`**：`.spec/demo-user-management-api/`。

產出**三個**產物（全本地寫入，不啟 Agent），與真實任務一模一樣：

| 產物 | 角色 | 建立方式 |
|------|------|---------|
| `plan.md` | 給人與 LLM 讀的**唯一文件**（六章節，≤100 行） | Write 骨架一次（與 `/plan-start` 完全相同），再用 Edit 對錨點插入範例條目 |
| `state.json` | 機器可讀的流程狀態，**唯一權威** | 呼叫 `crew-state.py`，🔴 絕不手寫 JSON |
| `deploy.sql` | **唯一 SQL 事實來源** | Write（含檔尾 Rollback 註解段） |

🔴 **不產生**其他任何文件檔。demo 若多產一個檔，評估者看到的就不是 CREW 現在的樣子。

#### 2a. plan.md（唯一文件，六章節）

骨架**必須與 `/plan-start` 建的完全一致** —— 六行 `<!-- crew:xxx -->` 錨點註解連空白數量都不可更動
（`references/plan-common.md`「plan.md 章節契約」是唯一權威，相對 SKILL.md 為 `../../references/`）。
demo 直接把範例條目填好，讓評估者看到「填滿之後長什麼樣」：

```markdown
---
slug: demo-user-management-api
name: 使用者管理 API（DEMO）
type: feature
verified_at_commit:
verified_at:
drift_policy: normal
---

# 使用者管理 API（DEMO）

> ⚠️ `/plan-demo` 產生的示範任務，未同步 Notion。真實使用請先 `/crew-init` 完成首次設定，再用 `/plan-start <任務>` 開新任務。

## 目標與範圍        <!-- crew:goal owner=spec -->

為何做：使用者資料散在三支後台 JSP，各自一套查詢寫法，前端無法重用。
- In Scope：使用者 CRUD、分頁列表、email 唯一性、軟刪除
- Out of Scope：角色權限管理、SSO 整合、批次匯入

## 驗收條件          <!-- crew:ac   owner=spec -->

- [ ] AC-1 新增 email 已存在的使用者時回 409 Conflict
- [ ] AC-2 分頁參數越界（page < 0 或 size > 100）回 400，不回空清單
- [ ] AC-3 軟刪除後的使用者不出現在列表 API 結果
- [ ] AC-4 所有回應符合專案 ApiResult 格式（code／message／data）

## 決策紀錄          <!-- crew:dec  append-only -->

- D-4 [arch] 唯一性檢查放 Service 不靠 DB 例外攔截｜理由：要回可讀的 409 訊息｜否決：接 DataIntegrityViolationException（訊息綁 DB 方言）
- D-3 [db] email 唯一性用複合唯一索引 `(email, deleted_at)`｜理由：軟刪除後同一 email 要能重新註冊｜否決：單欄 UNIQUE（刪了仍占用）
- D-2 [db] 軟刪除用 `deleted_at` 時間戳不用 `is_deleted` 旗標｜理由：順便留下刪除時間供稽核｜否決：布林旗標（還要另存時間欄）
- D-1 [spec] 範圍判斷：TASK_TYPE=feature、CHANGE_SCOPE=backend-only、FRONTEND_REQUIRED=false、DB_REQUIRED=true（DB_TABLES=users）、NEW_API=true、EXISTING_API_CHANGE=false｜理由：純後端 CRUD，新增一張表

## 已知取捨與風險    <!-- crew:risk append-only -->

- 軟刪除資料不清理，`users` 表單向成長；量大後要另開歸檔工作（本次不做）
- 分頁走 offset，深分頁（page > 1000）會退化；目前後台情境踩不到

## 指路              <!-- crew:map  append-only -->

- 資料表：`@sql:deploy.sql#users`
- 回應格式慣例：`@code:src/main/java/com/example/common/ApiResult.java`
- 分頁寫法可抄的既有例子：`@code:src/main/java/com/example/order/OrderController.java#list` (L64)

## 檢查報告摘要      <!-- crew:rep  append-only -->

- [{today}] DEMO 說明｜真實流程中這節由 /plan-review、/plan-security、/plan-verify 各留一行結論（🔴n 🟡n），逐條發現不落檔
```

> 注意這份範例裡**沒有** API 端點表、沒有欄位清單、沒有類別清單、沒有 DDL —— 那些全在
> `deploy.sql` 與程式碼裡，plan.md 只用「指路」節的錨點指過去。這是 CREW 的設計靈魂，demo 不可破例。

#### 2b. deploy.sql（唯一 SQL 事實來源）

```sql
-- ================================================================
-- demo-user-management-api 部署 SQL
-- 依部署順序執行；檔尾 Rollback 段預設註解
-- ================================================================

-- Step 1：建立 users 表
CREATE TABLE users (
  id           BIGINT       NOT NULL AUTO_INCREMENT,
  email        VARCHAR(100) NOT NULL,
  display_name VARCHAR(50)  NOT NULL,
  created_at   DATETIME     NOT NULL,
  deleted_at   DATETIME     NULL,
  PRIMARY KEY (id)
);

-- Step 2：email 複合唯一索引（軟刪除後可重用 email，見 D-3）
CREATE UNIQUE INDEX uk_users_email_alive ON users (email, deleted_at);

-- Step 3：預設管理員帳號
INSERT INTO users (email, display_name, created_at)
VALUES ('admin@example.com', '系統管理員', NOW());

-- ================================================================
-- Rollback（逆序，確認要回退才解開註解）
-- ================================================================
-- DELETE FROM users WHERE email = 'admin@example.com';
-- DROP INDEX uk_users_email_alive ON users;
-- DROP TABLE users;
```

#### 2c. state.json（呼叫 crew-state.py 建立，不手寫）

流程狀態的單一寫者是 `crew-state.py`。demo 也走同一條路，評估者才看得到真實的階段機：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" init \
  --slug demo-user-management-api --name "使用者管理 API（DEMO）" --type feature
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" set \
  --slug demo-user-management-api --step spec --status done
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" set \
  --slug demo-user-management-api --step db --status done
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" set \
  --slug demo-user-management-api --step arch --status done --phase arch
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" set \
  --slug demo-user-management-api --deploy-total 3 --deploy-confirmed 0
```

跑完後 `crew-state.py next --slug demo-user-management-api` 會回 `/plan-build`，
評估者可以直接看到「流程位置是算出來的，不是猜檔案存不存在」。

### 3. 引導使用者體驗

產出後顯示：

```
═══════════════════════════════════════════
🎯 CREW Demo 完成

📂 產出目錄：.spec/demo-user-management-api/
📄 plan.md      唯一文件（六章節：目標與範圍／驗收條件／決策紀錄／
                已知取捨與風險／指路／檢查報告摘要）
🗄️ deploy.sql   唯一 SQL 事實來源（3 個部署步驟 + Rollback 段）
📊 state.json   流程狀態唯一權威（階段：arch）

💡 接下來可以做什麼：

1. 看規劃長什麼樣（整個任務就這一份文件）：
   - cat .spec/demo-user-management-api/plan.md
   - cat .spec/demo-user-management-api/deploy.sql

2. 用 /plan-next 體驗智慧推薦（階段是算出來的，不是猜的）：
   /plan-next demo-user-management-api

3. 用 /plan-status --detail 看階段機與部署進度

4. 真正開始用 CREW：
   /crew-init                  完成首次設定（含 Notion）
   /plan-start <你的任務>      建立真實任務
   /crew-doctor                檢查環境

5. 清理 demo 產物：
   /plan-demo --cleanup
═══════════════════════════════════════════
```

### 4. 自動清理時機

`/plan-demo` 預設**不自動清理**（使用者要主動 `--cleanup`）。

demo 任務靠 **`demo-` slug 前綴**辨識，🔴 **不得**在 plan.md frontmatter 加 `demo: true` 之類的自訂欄位
（frontmatter 只准 `slug` / `name` / `type` / `verified_at_commit` / `verified_at` / `drift_policy` 六個欄位），
也不得手改 `state.json` 加欄位。目前 `/plan-status`、`crew-state.py list` 不特別處理此前綴，
demo 任務會與真實任務混在同一份清單顯示，不會標示「[DEMO]」也不會分組，用完建議 `--cleanup`。

`--keep` 旗標：明示「我之後會自己處理」，效果與預設相同（純 UX 信號）。

---

## 範例內容（內建）

完整範本 inline 於本 skill 的「產出 `.spec/demo-{slug}/` 目錄」一節（plan.md 全文 ＋ deploy.sql 全文
＋ `crew-state.py` 指令序列），不依賴外部 references 檔。

**舊版 demo 曾經產出、現在刻意不再產出的東西**（評估者若看過舊版會問，這裡先說明去向）：

| 舊產物 | 現在在哪 |
|--------|---------|
| 任務元資訊（type／建立日期／狀態） | `state.json`（`crew-state.py` 唯一寫者）＋ plan.md frontmatter 的 `slug`／`name`／`type` |
| 判斷區塊（TASK_TYPE／DB_REQUIRED…） | plan.md 決策紀錄的 `D-1 [spec] 範圍判斷` 條目 |
| API 端點表 | **不落檔**——端點是程式碼事實，用「指路」節的 `@code:` 錨點指過去 |
| 表 schema 與索引 | `deploy.sql`（唯一 SQL 事實來源）＋「指路」節 `@sql:deploy.sql#users` |
| 類別清單與介面定義 | **不落檔**——同上，產碼後即程式碼事實 |
| 會被產出的檔案清單 | **不落檔**——`git status` 與 `state.json` 的 `work_unit` 就是事實 |
| 驗證報告 | 摘要一行進 plan.md「檢查報告摘要」；完整報告是 `.cache/` 一次性暫存（gitignore） |
| 開發日誌 | `state.json` 的 `history` 事件流 |

---

## 何時不用

- 寫 demo 頁面給客戶看 → 直接開發，非本 skill
- 正式建立任務 → `/plan-start`
- 完整規劃 → `/plan`
- CREW 環境檢查 → `/crew-doctor`

---

## Gotchas

- **demo 任務會混進真實任務清單**：`crew-state.py list` 掃的是 `.spec/*/state.json`，demo 也有一份，因此 `/plan-status`、`/plan-next --all`、SessionStart 開場提醒都會看到它。目前不會標示「[DEMO]」也不會分組，用完建議 `--cleanup` 清除
- **骨架一個字都不能改**：demo 的 plan.md 六行錨點註解（含空白數量）必須與 `/plan-start` 建的完全相同。改掉一個字，評估者拿 demo 去跑 `/plan` 時 Edit 會找不到插入點
- **CLAUDE.md 技術棧偵測不到** → 用 `spring-boot-jpa` 預設範本；不阻擋
- **重複跑 /plan-demo** → 若 `.spec/demo-{slug}/` 已存在，提示「是否覆寫？」；確認覆寫才對 `crew-state.py init` 加 `--force`（不問就 `--force` 會蓋掉別人的狀態檔）
- **demo 不會建立 Git branch**：避免污染分支樹。真實 plan-start 會建分支

---

## 邊界情況

- **當前目錄無寫入權限** → 提示換目錄
- **使用者指定的題目過於複雜** → 仍按範本產出，但提醒「demo 模式不深入展開，建議 /plan-start 跑真實流程」
- **demo 已存在且使用者選不覆寫** → 跳過產出，僅顯示「查看現有 demo」指引
