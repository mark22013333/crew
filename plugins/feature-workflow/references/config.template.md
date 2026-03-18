# Feature Workflow 設定檔

此檔案由 `/plan-setup` 自動產生，儲存於 `~/.claude-company/feature-workflow-config.md`。
所有 plan-* Skill 會讀取此檔案取得 Notion ID、專案對應與技術棧設定。

---

## Notion 資料庫 Data Source ID

| 資料庫 | Data Source ID | 用途 |
|--------|---------------|------|
| 任務追蹤工具 | `<待填入>` | 功能生命週期管理 |
| 功能設計庫 | `<待填入>` | 設計文件索引（結案同步） |
| 專案資料庫 | `<待填入>` | 專案 Relation 來源 |

## 專案對應

Skill 透過 `git remote get-url origin` 取得 Git 遠端 URL，解析為識別碼後精確匹配對應的 Notion 專案。

**識別碼解析規則**：
- 公司 GitLab（host 含 `intumit`）：`{group}/{repo}`（如 `FUB03P2402/PushAPIService`）
- 外部（GitHub 等）：`{host}/{group}/{repo}`（如 `github.com/org/repo`）
- 自動去除 `.git` 後綴，支援 HTTPS / SSH 格式

| Notion 專案名稱 | Git Repo | 技術棧 | 說明 |
|----------------|----------|--------|------|
| （範例）我的專案 | `FUB03P2402/MyProject` | spring-boot-mybatis | 範例，請替換 |

## CREW 工作區

| 項目 | 值 |
|------|-----|
| 工作區頁面 ID | `<待填入>` |
| 工作區頁面 URL | `https://www.notion.so/<待填入>` |

## 技術棧定義

初始版本提供常見 Java ORM 技術棧。使用者可自行新增自訂技術棧。
scaffold 會根據技術棧 ID + 專案 CLAUDE.md + 現有程式碼範本，產出對應風格的程式碼。

### 內建技術棧

| 技術棧 ID | 框架 | ORM | DB | scaffold 行為 |
|-----------|------|-----|-----|--------------|
| spring-mvc-mybatis | Spring MVC 4.x | MyBatis + tk.mybatis | MSSQL/MySQL | POJO + Mapper XML + Service(Interface+Impl) + Controller |
| spring-boot-mybatis | Spring Boot 2.x+ | MyBatis + tk.mybatis | MySQL/MSSQL | Entity + Mapper + Mapping XML + Service + Controller + DTO |
| spring-boot-jpa | Spring Boot 2.x+ | JPA/Hibernate | MySQL/PostgreSQL | Entity(@Entity) + Repository + Service + Controller + DTO |
| spring-boot-mybatis-plus | Spring Boot 2.x+ | MyBatis-Plus | MySQL/MSSQL | Entity + BaseMapper + Service(IService+Impl) + Controller |

### 自訂技術棧

使用者可在此新增自訂技術棧。scaffold 會根據技術棧 ID 讀取下方定義的範本掃描規則，從專案中找到現有程式碼學習風格後產生骨架。

**新增步驟**：
1. 在下方總表新增一列（技術棧 ID、框架、ORM、DB、說明）
2. 在總表下方新增一個 `#### {技術棧 ID}` 區塊，定義各層的範本掃描規則
3. （建議）在專案 CLAUDE.md 描述該框架的分層慣例，讓 Agent 產出更精確

| 技術棧 ID | 框架 | ORM | DB | 說明 |
|-----------|------|-----|-----|------|

<!-- 範本掃描規則：每個自訂技術棧需在下方新增一個區塊 -->
<!-- 格式範例：

#### my-custom-stack

| 層級 | 名稱 | Glob Pattern | 說明 |
|------|------|-------------|------|
| Entity | 資料實體 | `**/entity/*.java` | 資料庫對應物件 |
| Repository | 資料存取 | `**/repository/*Repository.java` | DAO 層 |
| Service | 業務邏輯 | `**/service/*Service.java` | 排除 Impl |
| ServiceImpl | 業務邏輯實作 | `**/service/impl/*ServiceImpl.java` | Service 實作 |
| Controller | API 端點 | `**/controller/*Controller.java` | REST 端點 |
| DTO | 資料傳輸 | `**/dto/*DTO.java` | 請求/回應物件 |

-->

## 欄位對照

### 任務追蹤工具（功能開發新增欄位）

| 欄位 | 類型 | 選項值 |
|------|------|--------|
| 任務名稱 | Title | — |
| 狀態 | Status | `未開始` / `進行中` / `測試中` / `已完成` |
| 任務類型 | Multi-select | `🐞 錯誤` / `💬 功能要求` / `💅 細調` |
| 優先順序 | Select | `高` / `中` / `低` |
| 難度 | Select | `小` / `中` / `大` |
| 開發階段 | Select | `需求分析` / `規格設計` / `DB 設計` / `架構設計` / `開發中` / `程式碼審查` / `測試中` |
| 修復分支 | Text | Git branch 名稱 |
| 專案資料庫 | Relation | 關聯至專案資料庫 |

### 功能設計庫

| 欄位 | 類型 | 選項值 |
|------|------|--------|
| Name | Title | — |
| Tags | Multi-select | `API`(blue) / `報表`(purple) / `標籤`(green) / `推播`(orange) / `排程`(yellow) / `綁定`(pink) / `權限`(red) / `Rich Menu`(brown) / `匯出匯入`(gray) / `Flex Message`(default) |
| 設計類型 | Select | `規格書` / `DB 設計` / `架構設計` / `完整設計` |
| 技術棧 | Select | 對應技術棧 ID |
| 參考連結 | URL | 任務追蹤工具頁面連結 |
| 專案資料庫 | Relation | 關聯至專案資料庫 |
