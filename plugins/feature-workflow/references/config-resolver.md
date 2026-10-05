# 設定解析器 — Portable logical config

所有 plan-* Skill 統一使用本文件定義的漸進式載入語意。
CREW-owned Feature 設定的實體 storage root、read/write path 與 legacy fallback，權威一律是 `references/config-contract.md` 與 `scripts/crew-config.py`；本文件不重複宣告 Host-specific 實體路徑。

---

## 邏輯目錄結構

```text
{portable-config-root}/feature/
├── config.md                           ← feature/config
├── stacks/
│   ├── _builtin.md                    ← 內建技術棧總表（唯讀參考）
│   └── {custom-id}.md                 ← feature/stack --stack-id {custom-id}
└── projects/
    └── {sanitized-repo-id}.md         ← feature/project --repo-id {repo-id}
```

`{portable-config-root}` 由 `config-contract.md` 的 canonical root 規則決定。Skill 不自行拼接或猜測 Host-specific path。

---

## Resolver contract

讀取 Feature 設定時，先透過共用 resolver 取得 path / representation：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"

python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key feature/config \
  --mode read \
  --format json

python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key feature/project \
  --repo-id "{repo-id}" \
  --mode read \
  --format json

python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key feature/stack \
  --stack-id "{stack-id}" \
  --mode read \
  --format json
```

解析 resolver 結果時：

- `source=missing` → 依既有 Skill 邊界提示先完成對應 setup / registration，不自行 fallback。
- `representation=hierarchical` → 直接依本文件的 config / project / stack 格式解析 resolver 回傳的 `path`。
- `representation=legacy_monolith` → 僅 `feature/project` / `feature/stack` 可能出現；caller 必須沿用舊單一設定檔 parser 擷取對應區塊，不得把 monolith 當成獨立 project/stack 檔。
- 實際 legacy fallback candidate 與優先順序只在 `config-contract.md` 定義，本文件不維護第二份清單。

需要建立或更新 CREW-owned Feature 設定時，使用相同 logical key 搭配 `--mode write` 取得 canonical portable path。Resolver 本身不建立目錄、不搬檔、不修改使用者檔案。

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
| `ORG01P2401/PushAPIService` | `ORG01P2401--PushAPIService.md` |
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
notion_name: 範例銀行Push API(微服務)-ORG01P2401
git_repo: ORG01P2401/PushAPIService
stack: spring-boot-jpa
prod_branch: production
uat_branch: uat
dev_branch: ORG01P2401_DEV
product_id: example-admin
e2e_adapter: company-admin-e2e
e2e_workspace: ../AdminE2ETest
e2e_profile: uat
e2e_command: npx playwright test
---
範例銀行 LINE 推播微服務
```

frontmatter 欄位：
- `notion_name`（必要）：Notion 專案資料庫中的專案名稱
- `git_repo`（必要）：Git Repo 識別碼（用於自動匹配）
- `stack`（選填）：技術棧 ID（內建或自訂）
- `prod_branch`（必要）：正式環境分支名稱（`/plan-start` 從此分支建立 feature branch）
- `uat_branch`（選填）：測試環境分支名稱
- `dev_branch`（選填）：開發分支名稱（`/bug-close` merge-back 目標）
- `product_id`（選填）：plan-verify 的 product knowledge ID
- `e2e_adapter`（選填）：project-local / plugin E2E adapter ID
- `e2e_workspace`（選填）：相對於受測 application repo root 的 E2E repo path
- `e2e_profile`（選填）：邏輯 profile ID，不得放 secret
- `e2e_command`（選填）：在 E2E workspace 執行的 runner command

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

## 舊格式相容與遷移

### Read compatibility

向下相容由 `crew-config.py --mode read` 統一負責：

- `feature/config`：resolver 回傳可讀的設定 path。
- `feature/project` / `feature/stack`：resolver 同時回傳 `representation`。
- `representation=legacy_monolith` 時，沿用既有單一設定檔 parser；不得自行推導或搬移實體路徑。
- `source=missing` 時才提示執行對應 setup / registration。

### Migration ownership

舊單一設定格式的實際拆分、備份與寫檔屬 setup/admin 流程；本 reference 只定義 portable destination contract，不直接執行遷移。

`/plan-setup --migrate` 若進行格式遷移，目的地必須透過 resolver 的 write contract 取得：

1. 主設定 → `feature/config --mode write`
2. 各專案對應 → `feature/project --repo-id {repo-id} --mode write`
3. 各自訂技術棧 → `feature/stack --stack-id {id} --mode write`
4. 內建技術棧仍維持 `stacks/_builtin.md` 的既有 bundle/parser 語意

實際 legacy source、canonical root 與 fallback 規則以 `config-contract.md` 為準，不在本文件重複定義。

---

## Git Repo 識別碼解析規則

所有 Skill 共用此規則（與舊版一致）：

- 公司 GitLab（host 含 `intumit`）：`{group}/{repo}`（如 `ORG01P2401/PushAPIService`）
- 外部（GitHub、Azure DevOps 等）：`{host}/{path}`（如 `ssh.dev.azure.com/v3/chte/fia/wcs`）
- 自動去除 `.git` 後綴，支援 HTTPS / SSH 格式
