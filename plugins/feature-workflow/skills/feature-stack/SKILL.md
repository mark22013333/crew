---
name: feature-stack
description: 自動偵測或互動式建立自訂技術棧，掃描專案分層結構產生範本掃描規則，寫入設定檔。當使用者提到「feature-stack」、「自訂技術棧」、「新增技術棧」、「設定技術棧」、「tech stack」時觸發此 Skill。
---

# feature-stack — 自訂技術棧設定

自動掃描專案的分層結構，偵測各層級的 package 與命名慣例，產生範本掃描規則並寫入 feature-workflow 設定檔。

---

## 設定檔

執行前依序檢查以下路徑，讀取第一個找到的設定檔：
1. `~/.claude-company/feature-workflow-config.md`（公司環境）
2. `~/.claude/feature-workflow-config.md`（個人環境）

若都不存在，提示使用者先執行 `/feature-setup`。

---

## 參數

```
/feature-stack [技術棧 ID]
```

- 不帶參數：自動偵測後引導設定
- 帶 ID：直接使用指定 ID，跳過偵測步驟

---

## 流程

### 1. 檢查現有技術棧

讀取設定檔，取得當前專案在「專案對應」表中的技術棧 ID。

- 若已是內建技術棧（`spring-mvc-mybatis` 等）→ 提示已有內建支援，詢問是否仍要建立自訂覆蓋
- 若已有自訂技術棧且 `#### {ID}` 區塊存在 → 詢問是否「更新」或「取消」
- 若為空或不存在 → 繼續

### 2. 偵測框架資訊

掃描專案的建置檔：

```bash
# 尋找建置檔
find . -maxdepth 3 -name "pom.xml" -o -name "build.gradle" -o -name "build.gradle.kts" | head -5
```

從建置檔擷取：
- **框架**：Spring MVC / Spring Boot / Spring WebFlux / Micronaut / Quarkus 等
- **ORM**：MyBatis / JPA / R2DBC / JDBC / jOOQ / MyBatis-Plus 等
- **DB**：從 JDBC driver 推斷（mssql-jdbc → MSSQL、mysql-connector → MySQL 等）

若無法判斷 → 詢問使用者手動輸入。

### 3. 決定技術棧 ID

```
偵測到的框架資訊：
  框架：Spring WebFlux 3.2
  ORM：R2DBC
  DB：PostgreSQL

建議的技術棧 ID：spring-webflux-r2dbc
確認使用此 ID？（Enter 確認或輸入自訂 ID）
```

驗證 ID：
- 不可與內建 ID 重複（`spring-mvc-mybatis`、`spring-boot-mybatis`、`spring-boot-jpa`、`spring-boot-mybatis-plus`）
- 不可與設定檔中已有的自訂 ID 重複（除非步驟 1 選擇「更新」）
- 格式限制：小寫英文 + 數字 + 連字號，如 `my-custom-stack`

### 4. 掃描專案分層結構

這是核心步驟。掃描 `src/main/java` 下的 package 結構，辨識各層級。

#### 4-1. 掃描 package 目錄

```bash
# 列出 src/main/java 下所有含 .java 檔案的 package 目錄
find src/main/java -name "*.java" -exec dirname {} \; | sort -u
```

#### 4-2. 辨識層級

根據目錄名稱和檔案命名模式，辨識常見分層：

| 辨識規則 | 層級 | 常見目錄名 |
|---------|------|-----------|
| 目錄含 `entity` / `model` / `pojo` / `domain` | Entity | entity, model, pojo, domain |
| 目錄含 `dao` / `mapper` / `repository` / `repo` | Repository/Mapper | dao, mapper, repository |
| 目錄含 `mapping` 且有 `.xml` 檔案 | Mapper XML | mapping, mappers, xml |
| 目錄含 `service` 且無 `impl` | Service | service |
| 目錄含 `service/impl` 或 `serviceimpl` | ServiceImpl | service/impl |
| 目錄含 `controller` / `rest` / `api` / `web` | Controller | controller, rest, api |
| 目錄含 `dto` / `vo` / `request` / `response` | DTO | dto, vo, request, response |
| 目錄含 `config` / `configuration` | Config | config |
| 目錄含 `handler` / `listener` / `event` | Handler | handler, listener |
| 目錄含 `converter` / `adapter` / `transform` | Converter | converter, adapter |

#### 4-3. 產生 Glob Pattern

對每個辨識到的層級，根據實際找到的檔案產生 Glob Pattern：

1. 取得該目錄下的 `.java` 檔案清單
2. 分析命名模式（如 `*Controller.java`、`*Service.java`）
3. 產生精確的 Glob Pattern

**範例**：

找到 `src/main/java/com/example/controller/UserController.java` 和 `OrderController.java`

→ 產生 Pattern：`**/controller/*Controller.java`

找到 `src/main/java/com/example/service/impl/UserServiceImpl.java`

→ 產生 Pattern：`**/service/impl/*ServiceImpl.java`

#### 4-4. 驗證 Pattern

對每個產生的 Glob Pattern 實際執行掃描，確認能匹配到至少一個檔案：

```bash
# 驗證每個 Pattern
Glob {pattern}
```

匹配不到 → 嘗試放寬 Pattern（如 `**/service/**/*Service.java`），或標記為「需手動確認」。

### 5. 展示結果並確認

```
偵測到以下分層結構：

技術棧 ID：spring-webflux-r2dbc
框架：Spring WebFlux 3.2 | ORM：R2DBC | DB：PostgreSQL

| # | 層級 | 名稱 | Glob Pattern | 匹配數 | 範例檔案 |
|---|------|------|-------------|--------|---------|
| 1 | Entity | 資料實體 | `**/entity/*.java` | 5 | UserEntity.java |
| 2 | Repository | 資料存取 | `**/repository/*Repository.java` | 4 | UserRepository.java |
| 3 | Service | 業務邏輯 | `**/service/*Service.java` | 6 | UserService.java |
| 4 | Controller | API 端點 | `**/controller/*Controller.java` | 3 | UserController.java |
| 5 | DTO | 資料傳輸 | `**/dto/*DTO.java` | 8 | UserDTO.java |

操作選項：
  Enter — 確認並寫入設定檔
  e — 編輯（新增/移除/修改層級）
  c — 取消
```

若使用者選擇 **編輯**，進入互動式修改：

```
請選擇操作：
  a — 新增層級
  d {#} — 刪除層級（如 d 5）
  m {#} — 修改層級（如 m 3）
```

### 6. 寫入設定檔

確認後，更新 feature-workflow 設定檔：

#### 6-1. 更新「自訂技術棧」總表

在總表新增一列：

```markdown
| spring-webflux-r2dbc | Spring WebFlux 3.2 | R2DBC | PostgreSQL | 響應式 API |
```

#### 6-2. 新增掃描規則區塊

在總表下方（`## 欄位對照` 之前）新增：

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

#### 6-3. 更新專案對應表的技術棧欄位

若當前專案在「專案對應」表中技術棧欄位為空或不同，詢問是否更新：

```
是否將當前專案的技術棧更新為 "spring-webflux-r2dbc"？[Y/n]
```

確認後同時更新 Notion 專案資料庫中的「技術棧」欄位（使用 `notion-update-page`）。

### 7. 回傳結果

```
自訂技術棧設定完成！

  技術棧 ID：spring-webflux-r2dbc
  框架：Spring WebFlux 3.2 | ORM：R2DBC | DB：PostgreSQL
  層級數：5（Entity / Repository / Service / Controller / DTO）

已寫入：~/.claude-company/feature-workflow-config.md

現在執行 /feature-scaffold 時會自動使用此技術棧的掃描規則。

提示：建議在專案 CLAUDE.md 補充分層慣例說明，讓 Agent 產出更精確的程式碼。
```

---

## 邊界情況

- **設定檔不存在**：提示先執行 `/feature-setup`
- **專案不在設定檔的專案對應中**：提示先執行 `/project-add`
- **已有同名自訂技術棧**：詢問是否更新覆蓋
- **掃描不到任何分層結構**：進入完全手動模式，逐一詢問層級名稱和 Glob Pattern
- **非 Java 專案**：掃描 `src/main` 或專案根目錄，Pattern 改為對應語言（如 `**/*.py`、`**/*.go`）
- **多模組專案**：詢問要掃描哪個模組，或掃描所有模組取聯集
- **ID 與內建重複**：提示改名，不允許覆蓋內建技術棧
