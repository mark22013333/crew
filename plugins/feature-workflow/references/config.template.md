# Feature Workflow 設定檔

此檔案由 `/feature-setup` 自動產生，儲存於 `~/.claude-company/feature-workflow-config.md`。
所有 Feature Skill 會讀取此檔案取得 Notion ID、專案對應與技術棧設定。

---

## Notion 資料庫 Data Source ID

| 資料庫 | Data Source ID | 用途 |
|--------|---------------|------|
| 任務追蹤工具 | `<待填入>` | 功能生命週期管理 |
| 功能設計庫 | `<待填入>` | 設計文件索引（結案同步） |
| 專案資料庫 | `<待填入>` | 專案 Relation 來源 |

## 專案路徑對應

Skill 透過 `pwd` 取得當前工作目錄，以前綴匹配方式自動對應 Notion 專案。

| Notion 專案名稱 | 本機路徑 | 技術棧 | 說明 |
|----------------|----------|--------|------|
| （範例）我的專案 | `/Users/xxx/projects/my-project` | spring-boot-mybatis | 範例，請替換 |

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

使用者可在此新增自訂技術棧。scaffold 會根據 ID 讀取專案中的範本程式碼來產生。
新增方式：填入下表 + 在專案 CLAUDE.md 描述該框架的分層慣例。

| 技術棧 ID | 框架 | ORM | DB | 說明 |
|-----------|------|-----|-----|------|

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
