# Feature Workflow Plugin

功能開發工作流 — 整合 Notion 與 Claude Code，涵蓋需求分析、規格設計、DB 設計、架構設計、程式碼骨架產生、品質審查到結案的完整生命週期管理。

## 安裝

```bash
claude plugin marketplace add mark22013333/crew && \
claude plugin install feature-workflow && \
claude plugin enable feature-workflow
```

首次使用前執行設定引導：

```
/feature-setup
```

### 更新

```bash
claude plugin update feature-workflow@company-marketplace
```

更新完成後**重啟 Claude Code** 使新版生效。

> 若 `update` 顯示已是最新但功能未生效，可先移除再重裝：
> ```bash
> claude plugin uninstall feature-workflow@company-marketplace && \
> claude plugin install feature-workflow@company-marketplace
> ```

## 流程總覽

```
/feature-setup (首次，一次性)
        │
        ▼
/feature-start <功能簡述>          ← 建立 Notion 頁面 + Git branch
  │  階段: 需求分析
  ▼
/feature-spec [補充需求]           ← Agent(opus) 產出技術規格書
  │  階段: 規格設計
  ▼
/feature-db [補充說明]             ← Agent(opus) 設計 DB + 產出 SQL
  │  階段: DB 設計
  ▼
/feature-arch [補充說明]           ← Agent(opus) 設計分層架構 + 介面
  │  階段: 架構設計
  ▼
/feature-scaffold [--dry-run]     ← Agent(opus) 產生程式碼骨架
  │  階段: 開發中
  │
  ├── /feature-update <進度>       ← 隨時可穿插使用
  │
  ▼
/feature-review                    ← 程式碼品質檢查
  │  階段: 程式碼審查
  ▼
/feature-close                     ← 結案 + 同步設計庫
     階段: 測試中
```

流程非強制線性，可跳過任何步驟、反覆執行、隨時用 feature-update 記錄。

## 使用範例

### 快捷方式：一鍵自動化（/feature-auto）

以 **Agent Team 協作模式**（Leader + 4 Teammates）自動執行完整流程。需先完成以下設定：

**前置設定**：

```bash
# 1. 啟用 Agent Teams（加入 ~/.zshrc 永久生效）
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

```json
// 2. 啟用 Extended Thinking（~/.claude/settings.json）
{
  "alwaysThinkingEnabled": true
}
```

如果已有規格書檔案，可直接一行指令完成從建立到骨架的全流程：

```
/feature-auto doc/訂閱推播統計.md
```

執行後會展示計畫並等待確認：

```
📄 規格書：doc/訂閱推播統計.md
📝 功能名稱：訂閱推播統計報表
📋 需求摘要：提供後台查詢訂閱推播的開封率與點擊率統計...
🤖 執行模式：Agent Team（Leader + 4 Teammates）

即將依序執行：
  1. ✅ feature-start   — Leader 建立 Notion 條目 + Git branch
  2. ✅ feature-spec    — spec-analyst 產出技術規格書
  3. ✅ feature-db      — db-designer 設計資料庫
  4. ✅ feature-arch    — arch-designer 設計架構
  5. ✅ feature-scaffold — code-generator 產生程式碼骨架

確認執行？[Y/n]
```

確認後 Agent Team 依序執行，每完成一個階段會顯示進度：

```
✅ [1/5] feature-start 完成 — Notion 頁面已建立
✅ [2/5] spec-analyst 完成 — 3 個 API、5 項業務規則
✅ [3/5] db-designer 完成 — 2 個表、4 個索引
✅ [4/5] arch-designer 完成 — 8 個類別、策略模式
✅ [5/5] code-generator 完成 — 8 個檔案已建立

🎉 功能建立完成！
📊 Notion 頁面：https://notion.so/xxx
🔀 Git branch：feature/subscription-push-statistics
```

支援選項：

```bash
/feature-auto doc/spec.md --stop-at spec    # 只到規格書階段
/feature-auto doc/spec.md --skip db         # 跳過 DB 設計（功能不涉及資料庫）
/feature-auto doc/spec.md --dry-run         # scaffold 僅預覽，不建立檔案
```

#### 規格書範本

規格書無強制格式，但結構化內容能讓 Agent 產出更精確。建議範本：

```markdown
# 訂閱推播統計報表

## 需求描述
- **功能目的**：提供後台查詢訂閱推播的開封率與點擊率統計，供營運人員分析推播成效
- **目標使用者**：營運管理人員
- **使用情境**：
  1. 營運人員選擇日期範圍，查看各推播訊息的開封數、點擊數、開封率、點擊率
  2. 可依推播類型篩選（一般推播 / 訂閱推播）
  3. 支援匯出 Excel 報表

## 驗收條件
- [ ] 可依日期範圍查詢推播統計
- [ ] 統計數據包含：傳送數、開封數、點擊數、開封率、點擊率
- [ ] 支援分頁顯示
- [ ] 支援匯出 Excel

## 技術備註
- API 需遵循現有 `/api/analysis/*` 路徑風格
- 統計資料來源：LINE Messaging API 的 aggregation 回傳
- 大量資料需分頁，單頁上限 50 筆
- 需要新增統計結果暫存表，避免每次即時查詢 LINE API
```

> 規格書也可以很簡短（例如只有三行需求描述），Agent 會根據專案 CLAUDE.md 自動補充推斷。但內容越完整，產出品質越高。

### 手動逐步執行

以「新增訂閱推播統計報表」功能為例，展示完整開發流程：

#### 1. 建立功能條目

```
/feature-start 新增訂閱推播統計報表
```

自動偵測當前專案、建立 Notion 頁面（含 7 區塊模板）、詢問優先順序與難度，可選建立 Git branch：

```
✅ 功能條目已建立！
📄 Notion：https://notion.so/xxx
🔀 分支：feature/subscription-push-statistics
📋 階段：需求分析
```

#### 2. 產出技術規格

```
/feature-spec 需要依日期範圍查詢，含開封率與點擊率
```

Opus Agent 讀取專案 CLAUDE.md 和現有 Controller 風格，產出 API 設計、業務邏輯規則、錯誤處理策略，自動寫入 Notion「📐 技術規格」區塊。

#### 3. 設計資料庫

```
/feature-db 需要支援軟刪除
```

Opus Agent 根據技術規格和現有 Entity 慣例，產出 CREATE TABLE / INDEX / 範例資料 / Rollback SQL，寫入 Notion「🗄️ 資料庫設計」區塊，可選匯出 SQL 檔案到專案目錄。

#### 4. 設計架構

```
/feature-arch
```

Opus Agent 產出分層架構圖（Mermaid）、類別清單、介面定義、設計模式選擇，寫入 Notion「🏗️ 架構設計」區塊。

#### 5. 產生程式碼骨架

```
/feature-scaffold --dry-run    ← 先預覽檔案清單
/feature-scaffold              ← 確認後實際建立
```

Opus Agent 掃描專案現有程式碼學習風格，產生 POJO、Mapper、Service、Controller 等骨架檔案，風格與專案完全一致。

#### 6. 開發過程中記錄進度

```
/feature-update Service 層查詢邏輯已完成，剩餘 Controller 單元測試
```

#### 7. 程式碼審查

```
/feature-review
```

根據專案 CLAUDE.md 動態產生檢查項目，對程式碼進行品質審查。

#### 8. 結案

```
/feature-close
```

從 Git diff 自動擷取分層變更摘要、更新 Notion 頁面、同步功能設計庫，並依專案 Git Flow 提示後續合併步驟。

## Skill 清單

| Skill | 說明 |
|-------|------|
| `/feature-setup` | 首次設定引導（含 Agent 安裝選項） |
| `/feature-start` | 建立功能需求 Notion 頁面 + Git branch |
| `/feature-spec` | 技術規格書（Agent, opus） |
| `/feature-db` | 資料庫設計（Agent, opus） |
| `/feature-arch` | 架構設計（Agent, opus） |
| `/feature-scaffold` | 程式碼骨架產生（Agent, opus） |
| `/feature-update` | 更新開發進度 |
| `/feature-review` | 程式碼品質檢查 |
| `/feature-close` | 結案 + 同步設計庫 |
| `/feature-auto` | 讀取規格書自動執行完整流程 |
| `/project-add` | 新增或更新專案對應（來自 bug-workflow Plugin） |

## 技術棧支援

### 內建技術棧

| ID | 框架 | ORM | scaffold 行為 |
|----|------|-----|--------------|
| `spring-mvc-mybatis` | Spring MVC 4.x | MyBatis + tk.mybatis | POJO + Mapper XML + Service(Interface+Impl) + Controller |
| `spring-boot-mybatis` | Spring Boot 2.x+ | MyBatis + tk.mybatis | Entity + Mapper + Service + Controller + DTO |
| `spring-boot-jpa` | Spring Boot 2.x+ | JPA/Hibernate | Entity + Repository + Service + Controller + DTO |
| `spring-boot-mybatis-plus` | Spring Boot 2.x+ | MyBatis-Plus | Entity + BaseMapper + Service(IService+Impl) + Controller |

### 自訂技術棧

適用於內建技術棧未涵蓋的框架（如 Spring WebFlux、Vert.x、純 JDBC 等）。

#### 設定步驟

**Step 1**：在設定檔（`feature-workflow-config.md`）的「自訂技術棧」總表新增一列：

```markdown
| 技術棧 ID | 框架 | ORM | DB | 說明 |
|-----------|------|-----|-----|------|
| spring-webflux-r2dbc | Spring WebFlux 3.x | R2DBC | PostgreSQL | 響應式 API |
```

**Step 2**：在總表下方新增 `#### {技術棧 ID}` 區塊，定義各層級的範本掃描規則：

```markdown
#### spring-webflux-r2dbc

| 層級 | 名稱 | Glob Pattern | 說明 |
|------|------|-------------|------|
| Entity | 資料實體 | `**/entity/*.java` | R2DBC Entity |
| Repository | 資料存取 | `**/repository/*Repository.java` | ReactiveCrudRepository |
| Service | 業務邏輯 | `**/service/*Service.java` | 回傳 Mono/Flux |
| Controller | API 端點 | `**/controller/*Controller.java` | @RestController |
| DTO | 資料傳輸 | `**/dto/*DTO.java` | 請求/回應物件 |
```

scaffold 會依照每列的 Glob Pattern 從專案中找到現有程式碼作為風格範本，學習後產生新的骨架檔案。

**Step 3**（建議）：在專案 CLAUDE.md 描述該框架的分層慣例，例如：

```markdown
## 分層架構
- Controller 回傳 `Mono<ResponseEntity<T>>`
- Service 層全部使用響應式鏈（不可 block）
- Repository 繼承 `ReactiveCrudRepository`
```

#### 注意事項

- 技術棧 ID 不可與內建 ID 重複
- Glob Pattern 必須能在專案中匹配到至少一個檔案，否則 scaffold 會提示手動指定範本
- 層級數量不限，可依專案需求增減（如不需要 DTO 就不加）
- 在專案對應表中將專案的「技術棧」欄位填入自訂 ID 即可生效

## Agent 雙模式

### 模式 A：SKILL.md 內嵌指示（預設）

安裝 Plugin 即可使用，Skill 執行時透過 Agent tool 內嵌完整 prompt 啟動 opus Agent。

### 模式 B：獨立 Agent 檔案（選用）

`/feature-setup` 時可選安裝 4 個獨立 Agent 到 `~/.claude-company/agents/` 或 `~/.claude/agents/`，安裝後可在任何對話中獨立使用。

| Agent | 用於 | 核心能力 |
|-------|------|---------|
| feature-spec-analyst | feature-spec | 需求拆解、API 設計 |
| feature-db-designer | feature-db | 表結構、索引、遷移 SQL |
| feature-backend-designer | feature-arch | 分層設計、設計模式 |
| feature-code-generator | feature-scaffold | 按專案慣例產生程式碼 |

## 通用化設計

此 Plugin 不綁定任何特定專案架構。所有 Agent/Skill 在執行時會先讀取當前專案的 CLAUDE.md，動態適配：

- 技術棧和框架版本
- 分層慣例和 package 結構
- 命名規範和程式碼風格
- 設計模式偏好
- Git Flow 和部署流程

## 專案管理（/project-add）

專案的新增與更新統一由 bug-workflow 的 `/project-add` 處理（兩個 Plugin 共用同一個專案資料庫）。

在新專案目錄下執行：

```
/project-add
```

自動完成：
1. 偵測 Git Repo 識別碼（支援公司 GitLab 與 GitHub）
2. 偵測技術棧（掃描 pom.xml / build.gradle）
3. 搜尋 Notion 專案資料庫，比對或建立專案條目
4. 同步更新所有 Workflow 設定檔（bug-workflow + feature-workflow）

> `/feature-setup` 完成後會自動詢問是否執行 `/project-add` 新增當前專案。

## 與 bug-workflow 的關係

- 共用「任務追蹤工具」和「專案資料庫」Notion 資料庫
- 共用 `/project-add` 管理專案對應（需安裝 bug-workflow Plugin）
- setup 自動匯入 bug-workflow 的共用 ID 和專案對應
- 互不干擾，可同時使用

## 授權

MIT License
