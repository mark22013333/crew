# Feature Workflow 設定檔模板

此目錄由 `/plan-setup` 自動產生，儲存於 `~/.claude-company/feature-workflow/`。
所有 plan-* Skill 依 `references/config-resolver.md` 的漸進式載入邏輯讀取此目錄。

---

## 目錄結構

```
feature-workflow/
├── config.md          ← 本檔案模板
├── stacks/
│   ├── _builtin.md    ← 內建技術棧模板
│   └── {custom}.md    ← 自訂技術棧模板
└── projects/
    └── {repo-id}.md   ← 專案對應模板
```

---

## config.md 模板

```markdown
# Feature Workflow 設定

此檔案由 `/plan-setup` 自動產生。
所有 plan-* Skill 會讀取此檔案取得 Notion ID 與欄位對照。

## Notion 資料庫 Data Source ID

| 資料庫 | Data Source ID | 用途 |
|--------|---------------|------|
| 任務追蹤工具 | `<待填入>` | 功能生命週期管理 |
| 功能設計庫 | `<待填入>` | 設計文件索引（結案同步） |
| 專案資料庫 | `<待填入>` | 專案 Relation 來源 |

## CREW 工作區

| 項目 | 值 |
|------|-----|
| 工作區頁面 ID | `<待填入>` |
| 工作區頁面 URL | `https://www.notion.so/<待填入>` |

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
```

---

## stacks/_builtin.md 模板

```markdown
# 內建技術棧

初始版本提供常見 Java ORM 技術棧。使用者可透過 `/plan-stack` 新增自訂技術棧。
scaffold 會根據技術棧 ID + 專案 CLAUDE.md + 現有程式碼範本，產出對應風格的程式碼。

| 技術棧 ID | 框架 | ORM | DB | scaffold 行為 |
|-----------|------|-----|-----|--------------|
| spring-mvc-mybatis | Spring MVC 4.x | MyBatis + tk.mybatis | MSSQL/MySQL | POJO + Mapper XML + Service(Interface+Impl) + Controller |
| spring-boot-mybatis | Spring Boot 2.x+ | MyBatis + tk.mybatis | MySQL/MSSQL | Entity + Mapper + Mapping XML + Service + Controller + DTO |
| spring-boot-jpa | Spring Boot 2.x+ | JPA/Hibernate | MySQL/PostgreSQL | Entity(@Entity) + Repository + Service + Controller + DTO |
| spring-boot-mybatis-plus | Spring Boot 2.x+ | MyBatis-Plus | MySQL/MSSQL | Entity + BaseMapper + Service(IService+Impl) + Controller |
```

---

## stacks/{custom-id}.md 模板

```markdown
---
id: {技術棧 ID}
framework: {框架名稱與版本}
orm: {ORM 名稱與版本}
db: {資料庫類型}
scaffold: {scaffold 行為摘要}
---

## 掃描規則

{多模組說明，若適用}

| 層級 | 說明 | Glob Pattern | 範例 Package |
|------|------|-------------|-------------|
| Entity | {說明} | `{pattern}` | {package} |
| Repository | {說明} | `{pattern}` | {package} |
| Service | {說明} | `{pattern}` | {package} |
| Controller | {說明} | `{pattern}` | {package} |
| DTO | {說明} | `{pattern}` | {package} |

## 特殊慣例

- {慣例 1}
- {慣例 2}
```

---

## projects/{sanitized-repo-id}.md 模板

檔名規則：Git Repo 識別碼中的 `/` 替換為 `--`。

```markdown
---
notion_name: {Notion 專案名稱}
git_repo: {Git Repo 識別碼}
stack: {技術棧 ID，選填}
---
{專案說明}
```

### 範例

檔名：`FUB03P2402--PushAPIService.md`

```markdown
---
notion_name: 北富銀Push API(微服務)-FUB03P2402
git_repo: FUB03P2402/PushAPIService
stack: spring-boot-jpa
---
富邦銀行 LINE 推播微服務
```
