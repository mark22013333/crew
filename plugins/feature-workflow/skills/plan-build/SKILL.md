---
name: plan-build
description: 從 .spec/ 讀取設計文件，以 Agent Teams leader-delegate 模式（4 人團隊）產生程式碼。Leader 只協調不寫 code。當使用者提到「plan-build」、「build」、「產生程式碼」時觸發此 Skill。
---

# plan-build — Agent Teams 程式碼產生

從 `.spec/{slug}/` 讀取設計文件（spec.md、db.md、arch.md），以 **Agent Teams** leader-delegate 模式產生程式碼。Leader 只負責協調，不直接寫程式碼。

---

## 前置條件

### 環境變數

必須啟用 Agent Teams 實驗功能（擇一設定）：

**方式 A**：加入 shell profile（`~/.zshrc` 或 `~/.bashrc`）
```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

**方式 B**：加入 settings.json 的 `env` 區塊
```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

### 設計文件

建議至少完成 `/plan arch`（arch.md 存在），否則提示先執行 `/plan`。

> **前置檢查**：參照 bug-workflow plugin 的 `references/prerequisites.md` 檢查 CLAUDE.md 是否存在。

---

## 使用方式

```
/plan-build                # 完整產生（後端 + 前端 + API + 測試）
/plan-build --dry-run      # 預覽不建立檔案
/plan-build --backend-only # 只產後端
```

---

## 流程

### 1. 定位活躍任務

與 `/plan` 相同邏輯：從 Git branch 或 `_index.md` 匹配活躍任務。

讀取 `.spec/{slug}/README.md` 取得元資訊。

### 2. 讀取設計文件

讀取以下 `.spec/{slug}/` 下的檔案：

| 檔案 | 用途 | 必要性 |
|------|------|--------|
| `spec.md` | 技術規格（API 設計、業務邏輯） | 建議 |
| `db.md` | DB 設計（表結構） | 建議 |
| `db.sql` | SQL 檔案 | 選讀 |
| `arch.md` | 架構設計（類別清單、介面定義） | **強烈建議** |

若 arch.md 不存在，警告使用者並詢問是否繼續。

### 3. 判斷團隊組成

從 `spec.md` 的「判斷」區塊讀取：
- `FRONTEND_REQUIRED`: true/false
- `FRONTEND_TECH`: JSP/Vue/React/無

根據判斷結果決定團隊規模：

| 情境 | 團隊組成 |
|------|---------|
| `--backend-only` 或無前端 | 後端工程師（Subagent 模式） |
| 有前端需求 | 4 人 Agent Teams（後端 + 前端 + API + 測試） |

### 4. 確認執行計畫

```
即將啟動 Agent Teams 產生程式碼：

📄 設計來源：.spec/{slug}/
📊 Teammate 配置：
  • backend-engineer  — 後端核心（POJO/Mapper/Service）
  • api-engineer      — API 層（Controller/DTO/驗證）
  • frontend-engineer — 前端頁面（{FRONTEND_TECH}）
  • test-engineer     — 測試程式碼（單元測試/整合測試）

{--dry-run: 預覽模式，不建立檔案}

確認開始？[Y/n]
```

### 5. 讀取專案上下文（給 Teammates 的共用上下文）

收集一次，嵌入到 Team 建立指令中：

- 專案 CLAUDE.md 內容
- 技術棧 ID 和定義（從設定檔）
- 1-2 個現有程式碼範本（POJO、Mapper、Service、Controller 各一個）的檔案路徑

### 6. 啟動 Agent Teams

#### 僅後端（Subagent）

若 `FRONTEND_REQUIRED = false` 或 `--backend-only`，使用 **Agent tool** 啟動 subagent：

```
你是後端程式碼產生器。

## 設計文件
{arch.md 內容}

## DB 設計
{db.md 內容}

## 專案上下文
{CLAUDE.md 內容}

## 技術棧
{技術棧 ID 和定義}

## 現有程式碼範本
請讀取以下檔案作為風格參考：
{範本檔案路徑清單}

## 任務
按架構設計的類別清單，依序產生所有後端程式碼骨架：
1. POJO/Entity（含 Lombok、表註解）
2. Mapper/DAO（tk.mybatis 或 JPA Repository）
3. Mapper XML（若使用 MyBatis）
4. Service Interface
5. Service Impl（方法含 TODO 標記待實作邏輯）
6. Controller（含 @RequestMapping、參數驗證）

風格必須與專案完全一致（package、import 順序、註解、縮排）。
{dry_run_instruction}

使用繁體中文撰寫註解。
```

#### 完整 4 人團隊（Agent Teams）

使用自然語言要求 Claude 建立 Agent Team：

```
建立一個 Agent Team 來開發 {功能名稱} 功能，生成 4 個 Teammate：

【成員 1：後端工程師】Backend Engineer
- 讀取專案 CLAUDE.md 了解架構慣例
- 讀取設計文件：
  * .spec/{slug}/arch.md（架構設計 — 類別清單、介面定義）
  * .spec/{slug}/db.md（DB 設計 — 表結構）
- 掃描專案現有程式碼學習風格（POJO、Mapper、Service 各一個範本）
- 任務：
  * 產生 POJO/Entity（含 Lombok、表註解）
  * 產生 Mapper/DAO（tk.mybatis 或 JPA Repository）
  * 產生 Mapper XML（若使用 MyBatis）
  * 產生 Service Interface + Service Impl
  * Service 方法含 TODO 標記待實作邏輯
- 風格必須與專案完全一致（package、import 順序、註解、縮排）
- 完成後通知 Lead，並向其他成員分享產出的類別清單和介面定義
- 使用 Opus 模型
- 使用繁體中文

【成員 2：API 工程師】API Engineer
- 讀取設計文件：
  * .spec/{slug}/spec.md（技術規格 — API 設計、參數驗證規則）
  * .spec/{slug}/arch.md（架構設計）
- 等待後端工程師完成 Service 層後開始
- 任務：
  * 產生 Controller（含 @RequestMapping、路由設定）
  * 產生 DTO（Request/Response 物件）
  * 實作 API 參數驗證邏輯
  * 實作例外處理（BizException、ApiResult）
  * 確保 API 回應格式與專案現有風格一致
- 完成後通知 Lead，並向前端工程師分享 API 端點清單（URL + Method + 請求/回應格式）
- 使用 Opus 模型
- 使用繁體中文

【成員 3：前端工程師】Frontend Engineer
- 前端技術棧：{FRONTEND_TECH}
- 讀取設計文件：
  * .spec/{slug}/spec.md（技術規格 — 畫面需求、操作流程）
- 掃描專案前端目錄，讀取 2-3 個現有頁面作為風格範本
- 可與後端工程師同時開始（前端不依賴後端實作）
- 任務：
  * 產生前端頁面（HTML/JSP/Vue）
  * 產生 API 呼叫邏輯（待 API 工程師確認端點後對齊）
  * 產生表單驗證、表格展示、分頁元件
- 風格必須與專案完全一致
- 完成後通知 Lead
- 使用繁體中文

【成員 4：測試工程師】Test Engineer
- 讀取專案的測試慣例（掃描 src/test/ 下現有測試檔案）
- 等待後端工程師完成後開始
- 任務：
  * 為 Service 層產生單元測試（JUnit + Mockito）
  * 為 Controller 層產生整合測試（MockMvc / SpringBootTest）
  * 測試案例涵蓋：正常流程、邊界條件、異常處理
  * 測試命名遵循專案慣例
- 完成後通知 Lead
- 使用繁體中文

【任務依賴關係】
- 成員 1（後端工程師）最先開始，是核心
- 成員 2（API 工程師）和 4（測試工程師）等成員 1 完成後再開始
- 成員 3（前端工程師）可以跟成員 1 同時開始（前端不依賴後端實作）
- 成員 2、3、4 之間可並行

重要：四位 Teammate 負責不同目錄，不會衝突。
完成後：互相確認 API 契約是否一致（端點 URL、參數、回應格式），
不一致的地方由 API 工程師為準，其他成員調整。
{dry_run_instruction}

請使用 delegate mode，Lead 只負責協調，不要自己寫 code。
每個 Teammate 完成後要通知 Lead。
所有輸出使用繁體中文。
```

> `{dry_run_instruction}`：若 `--dry-run`，加入「只展示檔案清單和關鍵程式碼片段，不實際建立檔案」。

### 7. 更新 .spec/ 檔案

程式碼產生完成後：

1. 產生 `.spec/{slug}/files.md`：

```markdown
# 程式碼清單

## 新增檔案

| 檔案路徑 | 層級 | 說明 |
|---------|------|------|
| {path} | {Controller/Service/DAO/...} | {說明} |

## 修改檔案

| 檔案路徑 | 修改說明 |
|---------|---------|
```

2. 更新 `README.md` 的 `status: 開發中`
3. 在 `log.md` 追加紀錄

### 8. 回傳結果

```
程式碼產生完成！

📁 產出清單：.spec/{slug}/files.md
📊 統計：N 個後端 + M 個前端 + K 個測試

已完成：
  ✅ backend-engineer  — N 個檔案（POJO/Mapper/Service）
  ✅ api-engineer      — N 個檔案（Controller/DTO）
  {✅ frontend-engineer — M 個檔案（JSP/JS/CSS）}
  ✅ test-engineer     — K 個檔案（測試）
  {✅ API 契約確認 — 一致}

後續可使用：
  • /plan-verify  — 驗收驗證
  • /plan-review  — Agent Teams 3 人審查
  • /plan-close   — 結案並同步 Notion
```

---

## 邊界情況

- **arch.md 不存在**：警告並詢問，允許從 spec.md 或 README.md 直接產生
- **Agent Teams 未啟用**：顯示設定指引
- **--dry-run 模式**：不建立任何檔案，只展示清單和關鍵片段
- **Teammate 失敗**：提供選項：重試 / 跳過 / 終止
- **API 契約不一致**：以 API 工程師為準，其他成員調整
- **每個工作階段只能一個 Team**：建立新 Team 前確認無殘留 Team
- **僅後端模式**：不建立 Agent Teams，使用 Subagent 完成
