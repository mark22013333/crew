# 設定解析器 — 階層式設定目錄

所有 plan-* Skill 統一使用此文件定義的解析邏輯載入設定。

---

## 目錄結構

```
~/.claude-company/feature-workflow/     # 公司環境（優先）
├── config.md                           # 主索引（Notion IDs、工作區、欄位對照）
├── stacks/                             # 技術棧定義
│   ├── _builtin.md                     # 內建技術棧總表（唯讀參考）
│   ├── spring-mvc-jpa.md               # 自訂技術棧（每個獨立檔案）
│   └── ...
└── projects/                           # 專案對應（每個專案一個檔案）
    ├── FUB02P2101--LineBC.md
    ├── FUB03P2402--PushAPIService.md
    └── ...
```

備用路徑：`~/.claude/feature-workflow/`（個人環境）

---

## 解析優先順序

依序檢查以下路徑，使用**第一個找到的目錄**：

1. `~/.claude-company/feature-workflow/config.md`
2. `~/.claude/feature-workflow/config.md`

若都不存在，**向下相容檢查舊格式**：

3. `~/.claude-company/feature-workflow-config.md`（舊單一檔案）
4. `~/.claude/feature-workflow-config.md`（舊單一檔案）

若找到舊格式 → 提示使用者執行 `/plan-setup --migrate` 遷移。遷移前仍可正常讀取舊格式。

若全部不存在 → 提示使用者先執行 `/plan-setup`。

---

## 漸進式載入

Skill 依需求**按需載入**，不需要一次讀取所有檔案：

### 第 1 層：主索引（所有 Skill 都讀）

讀取 `config.md`，取得：
- Notion 資料庫 Data Source IDs
- CREW 工作區頁面 ID
- 欄位對照

### 第 2 層：專案對應（需要專案資訊時）

用 `git remote get-url origin` 解析 Git Repo 識別碼，轉換為檔名格式後讀取：

```
projects/{sanitized-repo-id}.md
```

**檔名規則**：Git Repo 識別碼中的 `/` 替換為 `--`，其餘保持不變。

| Git Repo 識別碼 | 檔名 |
|-----------------|------|
| `FUB03P2402/PushAPIService` | `FUB03P2402--PushAPIService.md` |
| `ssh.dev.azure.com/v3/chte/fia/wcs` | `ssh.dev.azure.com--v3--chte--fia--wcs.md` |
| `github.com/org/repo` | `github.com--org--repo.md` |

取得：Notion 專案名稱、技術棧 ID、說明。

### 第 3 層：技術棧定義（需要掃描規則時）

從專案檔的 `stack` 欄位取得技術棧 ID：

- 若 ID 屬於內建技術棧（`spring-mvc-mybatis`、`spring-boot-mybatis`、`spring-boot-jpa`、`spring-boot-mybatis-plus`）→ 讀取 `stacks/_builtin.md` 中的對應區塊
- 若為自訂技術棧 → 讀取 `stacks/{id}.md`

取得：框架、ORM、DB、scaffold 行為、掃描規則。

---

## 各 Skill 載入需求

| Skill | 第 1 層（config） | 第 2 層（project） | 第 3 層（stack） |
|-------|:-:|:-:|:-:|
| `plan-setup` | 寫入 | 寫入 | 寫入 |
| `plan-stack` | — | 讀取 | 寫入 |
| `plan-start` | 讀取 | 讀取 | — |
| `plan` | — | 讀取 | 讀取 |
| `plan-build` | — | 讀取 | 讀取 |
| `plan-close` | 讀取 | 讀取 | 讀取 |
| `plan-sync` | 讀取 | 讀取 | — |
| `plan-status` | — | — | — |
| `plan-verify` | — | — | — |
| `plan-review` | — | — | — |
| `project-add` | 讀取 | 寫入 | — |

---

## 檔案格式

### config.md

```markdown
# Feature Workflow 設定

## Notion 資料庫 Data Source ID

| 資料庫 | Data Source ID | 用途 |
|--------|---------------|------|
| 任務追蹤工具 | `{ID}` | 功能生命週期管理 |
| 功能設計庫 | `{ID}` | 設計文件索引（結案同步） |
| 專案資料庫 | `{ID}` | 專案 Relation 來源 |

## CREW 工作區

| 項目 | 值 |
|------|-----|
| 工作區頁面 ID | `{ID}` |
| 工作區頁面 URL | `https://www.notion.so/{ID}` |

## 欄位對照

### 任務追蹤工具（功能開發新增欄位）

| 欄位 | 類型 | 選項值 |
|------|------|--------|
| ... | ... | ... |

### 功能設計庫

| 欄位 | 類型 | 選項值 |
|------|------|--------|
| ... | ... | ... |
```

### projects/{id}.md

```markdown
---
notion_name: 北富銀Push API(微服務)-FUB03P2402
git_repo: FUB03P2402/PushAPIService
stack: spring-boot-jpa
---
富邦銀行 LINE 推播微服務
```

frontmatter 欄位：
- `notion_name`（必要）：Notion 專案資料庫中的專案名稱
- `git_repo`（必要）：Git Repo 識別碼（用於自動匹配）
- `stack`（選填）：技術棧 ID（內建或自訂）

body：專案說明（一句話）。

### stacks/_builtin.md

```markdown
# 內建技術棧

| 技術棧 ID | 框架 | ORM | DB | scaffold 行為 |
|-----------|------|-----|-----|--------------|
| spring-mvc-mybatis | Spring MVC 4.x | MyBatis + tk.mybatis | MSSQL/MySQL | POJO + Mapper XML + Service(Interface+Impl) + Controller |
| spring-boot-mybatis | Spring Boot 2.x+ | MyBatis + tk.mybatis | MySQL/MSSQL | Entity + Mapper + Mapping XML + Service + Controller + DTO |
| spring-boot-jpa | Spring Boot 2.x+ | JPA/Hibernate | MySQL/PostgreSQL | Entity(@Entity) + Repository + Service + Controller + DTO |
| spring-boot-mybatis-plus | Spring Boot 2.x+ | MyBatis-Plus | MySQL/MSSQL | Entity + BaseMapper + Service(IService+Impl) + Controller |
```

### stacks/{custom-id}.md

```markdown
---
id: spring-mvc-jpa
framework: Spring MVC 5.3.x
orm: JPA/Hibernate 5.6
db: SQL Server
scaffold: Entity + Repository + DB Service + Domain Service + Controller + DTO
---

## 掃描規則

多模組專案，模組依賴：`web` → `core.*` → `core`。

| 層級 | 說明 | Glob Pattern | 範例 Package |
|------|------|-------------|-------------|
| Entity | JPA @Entity | `**/db/entity/*.java` | `com.bcs.core.db.entity` |
| Repository | Spring Data JPA | `**/db/repository/**/*.java` | `com.bcs.core.db.repository` |
| ... | ... | ... | ... |

## 特殊慣例

- Service 不分 Interface/Impl，直接使用 `@Service` class
- DB 層統一放在 `db` package 下
```

---

## 舊格式遷移

### 觸發條件

執行 `/plan-setup --migrate` 或 `/plan-setup` 偵測到舊格式時自動提議。

### 遷移步驟

1. 讀取舊 `feature-workflow-config.md`
2. 建立 `feature-workflow/` 目錄結構
3. 擷取 Notion IDs + 工作區 + 欄位對照 → 寫入 `config.md`
4. 擷取內建技術棧表 → 寫入 `stacks/_builtin.md`
5. 擷取自訂技術棧（`#### {id}` 區塊）→ 各寫入 `stacks/{id}.md`
6. 擷取專案對應表各列 → 各寫入 `projects/{sanitized-id}.md`
7. 將舊檔案重新命名為 `feature-workflow-config.md.bak`
8. 顯示遷移結果

### 向下相容

遷移前，所有 Skill 遇到舊格式時仍可正常讀取（回退到原有解析邏輯）。僅在控制台顯示一次提示：

```
💡 偵測到舊版設定檔格式。建議執行 /plan-setup --migrate 遷移到階層式目錄結構。
```

---

## Git Repo 識別碼解析規則

所有 Skill 共用此規則（與舊版一致）：

- 公司 GitLab（host 含 `intumit`）：`{group}/{repo}`（如 `FUB03P2402/PushAPIService`）
- 外部（GitHub、Azure DevOps 等）：`{host}/{path}`（如 `ssh.dev.azure.com/v3/chte/fia/wcs`）
- 自動去除 `.git` 後綴，支援 HTTPS / SSH 格式
