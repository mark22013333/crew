---
name: feature-scaffold
description: 使用 Agent(opus) 根據 DB 設計與架構設計，按專案既有風格產生程式碼骨架。支援 --dry-run 預覽。當使用者提到「feature-scaffold」、「產生程式碼」、「骨架」、「scaffold」時觸發此 Skill。
---

# feature-scaffold — 程式碼骨架產生

使用 Agent（Opus 模型）根據資料庫設計與架構設計，按專案既有風格產生程式碼骨架，並更新 Notion 功能頁面的「📁 程式碼清單」區塊。

---

## 設定檔

執行前依序檢查以下路徑，讀取第一個找到的設定檔：
1. `~/.claude-company/feature-workflow-config.md`（公司環境）
2. `~/.claude/feature-workflow-config.md`（個人環境）

若都不存在，提示使用者先執行 `/feature-setup`。

---

## 參數

```
/feature-scaffold [--dry-run]
```

- `--dry-run`：僅預覽檔案清單，不實際建立檔案

---

## 前置條件

- 已使用 `/feature-start` 建立功能條目
- 建議已執行 `/feature-db` 和 `/feature-arch`（非強制，但產出品質更高）

---

## 流程

### 1. 定位目標功能 Notion 頁面

使用與 feature-update 相同的定位邏輯。

### 2. 取得設計資訊

使用 `notion-fetch` 取得目標頁面完整內容，擷取：
- 「🗄️ 資料庫設計」區塊（CREATE TABLE 語句）
- 「🏗️ 架構設計」區塊（類別清單、介面定義）
- 「📐 技術規格」區塊（API 端點設計、業務邏輯）

### 3. 讀取專案上下文與風格範本

#### 3-1. 技術棧 ID

從設定檔的「專案對應」表取得當前專案的技術棧 ID。

#### 3-2. 掃描風格範本

根據技術棧 ID，掃描專案中同類型的現有程式碼**各一個**作為風格範本。

**spring-mvc-mybatis** 需要的範本：
- POJO 範本：`Glob **/pojo/*.java`，取第一個
- Mapper 範本：`Glob **/dao/*Mapper.java`，取第一個
- Mapper XML 範本：`Glob **/mapping/*.xml`，取第一個
- Service Interface 範本：`Glob **/service/*Service.java`（排除 Impl），取第一個
- Service Impl 範本：`Glob **/service/impl/*ServiceImpl.java` 或 `**/service/*ServiceImpl.java`，取第一個
- Controller 範本：`Glob **/controller/*Controller.java`，取第一個

**spring-boot-mybatis** 需要的範本：
- Entity 範本、Mapper 範本、Mapper XML 範本、Service 範本、Controller 範本、DTO 範本

**spring-boot-jpa** 需要的範本：
- Entity 範本、Repository 範本、Service 範本、Controller 範本、DTO 範本

**spring-boot-mybatis-plus** 需要的範本：
- Entity 範本、Mapper 範本、Service Interface 範本、Service Impl 範本、Controller 範本、DTO 範本

**自訂技術棧**：

從設定檔的「自訂技術棧」區塊讀取該技術棧 ID 對應的範本掃描規則表（`#### {技術棧 ID}` 區塊）。表中每一列定義一個層級的 Glob Pattern，依序掃描每個 Pattern 取第一個匹配的檔案作為範本。

例如設定檔中定義了：

```
#### my-custom-stack

| 層級 | 名稱 | Glob Pattern | 說明 |
|------|------|-------------|------|
| Entity | 資料實體 | `**/entity/*.java` | 資料庫對應物件 |
| Service | 業務邏輯 | `**/service/*Service.java` | 排除 Impl |
| Controller | API 端點 | `**/controller/*Controller.java` | REST 端點 |
```

則依序執行 `Glob **/entity/*.java`、`Glob **/service/*Service.java`、`Glob **/controller/*Controller.java`，各取第一個作為範本。

若設定檔中找不到對應的 `#### {技術棧 ID}` 區塊，則提示使用者：
```
找不到技術棧 "{技術棧 ID}" 的範本掃描規則。
請在設定檔的「自訂技術棧」區塊新增 #### {技術棧 ID} 並定義各層的 Glob Pattern。
或者，手動指定一個現有類別作為範本。
```

讀取每個範本檔案的完整內容（用於 Agent 學習風格）。

### 4. 啟動程式碼產生 Agent

使用 **Agent tool** 啟動 subagent，參數：
- **model**: `opus`
- **prompt**: 組合以下內容傳入 Agent：

```
你是一位嚴謹的程式碼產生器。最重要的原則：產出的程式碼風格必須與專案現有程式碼完全一致。

## 技術棧
{技術棧 ID}

## DB 設計（CREATE TABLE）
{從 Notion 取得的 CREATE TABLE 語句}

## 架構設計（類別清單 + 介面定義）
{從 Notion 取得的架構設計}

## API 設計
{從 Notion 取得的 API 端點設計}

## 風格範本

### POJO/Entity 範本
{現有範本程式碼}

### Mapper/Repository 範本
{現有範本程式碼}

### Mapper XML 範本（若適用）
{現有範本程式碼}

### Service 範本
{現有範本程式碼}

### Controller 範本
{現有範本程式碼}

## 任務
根據以上資訊，按技術棧 {技術棧 ID} 產生所有程式碼檔案。

要求：
1. 每個檔案的 package、import 順序、註解風格、縮排必須與範本完全一致
2. Getter/Setter 風格從範本學習（Lombok? 手動? IDE 產生?）
3. Service 方法骨架含 TODO 註解標記待實作的業務邏輯
4. 不強加任何風格假設，一切從範本推斷
5. 註解和說明使用繁體中文

輸出格式：
A. 先輸出檔案清單表格（#、檔案路徑、類型、說明）
B. 再輸出每個檔案的完整程式碼（java/xml code block）
```

### 5. 展示檔案清單預覽

Agent 完成後，先向使用者展示檔案清單：

```
即將建立以下檔案：

| # | 檔案路徑 | 類型 | 說明 |
|---|---------|------|------|
| 1 | src/main/java/com/.../pojo/MsgExport.java | POJO | 訊息匯出實體 |
| 2 | src/main/java/com/.../dao/MsgExportMapper.java | Mapper | 資料存取 |
| 3 | src/main/resources/.../CustomMsgExportMapper.xml | XML | 複雜查詢 |
| 4 | src/main/java/com/.../service/MsgExportService.java | Service | 業務邏輯介面 |
| 5 | src/main/java/com/.../service/impl/MsgExportServiceImpl.java | Impl | 業務邏輯實作 |
| 6 | src/main/java/com/.../controller/MsgExportController.java | Controller | API 端點 |

共 6 個檔案。確認建立？[Y/n]
```

若使用 `--dry-run`，到此為止，不建立檔案。

### 6. 建立檔案

確認後，使用 Write tool 建立所有程式碼檔案。

**注意**：
- 建立前檢查檔案是否已存在，若存在則詢問是否覆蓋
- 依序建立（先 Entity → Mapper → Service → Controller）

### 7. 更新 Notion

1. 使用 `notion-update-page` 的 `update_content`，將檔案清單寫入「📁 程式碼清單」區塊的「新增檔案」子區塊

2. 使用 `notion-update-page` 更新 Property：
   - 開發階段 = `開發中`

### 8. 回傳結果

向使用者顯示：
- 已建立的檔案清單
- Notion 頁面連結
- 提示後續操作：
  ```
  程式碼骨架已建立！接下來：
  1. 實作 Service 中的 TODO 業務邏輯
  2. 隨時用 /feature-update 記錄進度
  3. 完成後用 /feature-review 檢查品質
  4. 最後用 /feature-close 結案
  ```

---

## 邊界情況

- **無 DB 設計和架構設計**：從技術規格直接推斷，產出品質可能較低
- **技術棧無法識別**：詢問使用者確認，或讓 Agent 從範本推斷
- **自訂技術棧缺少掃描規則**：提示使用者在設定檔新增 `#### {技術棧 ID}` 區塊定義 Glob Pattern
- **範本掃描不到**：提示使用者手動指定一個現有類別作為範本
- **檔案已存在**：詢問是否覆蓋、跳過、或重新命名
- **--dry-run 後使用者修改需求**：重新執行 `/feature-scaffold`（不帶 --dry-run）
