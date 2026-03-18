# Notion 資料庫建立模版

本文件定義 Crew Workflow 所需的 4 個 Notion 資料庫完整 Schema，供 `bug-setup` 和 `plan-setup` 首次建立時參照。

---

## 建立順序（解決 Relation 循環依賴）

### 第一輪：建立資料庫（不含 Relation）

依序建立，每個資料庫建立後記錄其 Data Source ID：

1. **專案資料庫**
2. **任務追蹤工具**
3. **Bug 知識庫**
4. **功能設計庫**

### 第二輪：補上 Relation 欄位

使用 `notion-update-data-source` 的 ADD COLUMN ... RELATION 語法：

```
1. 任務追蹤工具 ADD COLUMN "專案資料庫" RELATION({專案DS_ID})
2. Bug 知識庫 ADD COLUMN "專案資料庫" RELATION({專案DS_ID})
3. 功能設計庫 ADD COLUMN "專案資料庫" RELATION({專案DS_ID})
4. 專案資料庫 ADD COLUMN "任務追蹤工具" RELATION({任務DS_ID}, DUAL)
5. 專案資料庫 ADD COLUMN "bug處理方式" RELATION({BugDS_ID}, DUAL)
```

> **注意**：DUAL 表示雙向 Relation，會在兩邊資料庫同時顯示關聯欄位。

---

## A. 專案資料庫

### Schema

使用 `notion-create-database` 建立，名稱為「專案資料庫」：

| 欄位名稱 | 類型 | 選項 / 說明 |
|----------|------|-------------|
| Name | title | 專案名稱 |
| Git Repo | url | Git 遠端倉庫 URL |
| 技術棧 | select | `spring-mvc-mybatis`(blue), `spring-boot-mybatis`(green), `spring-boot-jpa`(purple), `spring-boot-mybatis-plus`(orange), `spring-mvc-jpa`(red) |
| 狀態 | status | 未開始 / 進行中 / 已結束 |
| 程式版本 | multi_select | `碩網版本`(brown), `偉康版本`(blue), `極限版本`(green), `仁大版本`(pink), `中華版本`(red), `客製版本(SpringBoot)`(yellow) |
| SIT 主機 | rich_text | SIT 部署主機資訊 |
| UAT 主機 | rich_text | UAT 部署主機資訊 |
| 正式環境主機 | rich_text | 正式環境部署主機資訊 |
| 部署方式 | rich_text | 部署指令或流程簡述 |
| 本機路徑 | rich_text | 本地開發路徑 |
| JIRA | rich_text | JIRA 專案連結或代號 |
| 地址 | rich_text | 客戶地址或辦公室位置 |
| 說明 | rich_text | 專案簡要描述 |
| Created | created_time | 建立時間（自動） |
| 上次編輯時間 | last_edited_time | 最後編輯時間（自動） |

### Views

1. **預設 Table View**（Default）
   - 排序：Name 降序
   - 篩選：狀態 = 進行中 OR 已結束
   - 顯示欄位：Name, Git Repo, 技術棧, 狀態, 程式版本, 說明

2. **List View**（「列表」）
   - 顯示：Name + 狀態
   - 無篩選

---

## B. 任務追蹤工具

### Schema

使用 `notion-create-database` 建立，名稱為「任務追蹤工具」：

| 欄位名稱 | 類型 | 選項 / 說明 |
|----------|------|-------------|
| 任務名稱 | title | 任務標題 |
| 狀態 | status | 未開始 / 進行中 / 測試中 / 已完成 |
| 任務類型 | multi_select | `🐞 錯誤`(orange), `💬 功能要求`(green), `💅 細調`(pink) |
| 優先順序 | select | `高`(red), `中`(yellow), `低`(green) |
| 難度 | select | `小`(green), `中`(yellow), `大`(red) |
| 環境 | select | `測試`(blue), `UAT`(yellow), `正式`(red) |
| 根因分類 | select | `邏輯錯誤`(red), `資料異常`(orange), `設定問題`(yellow), `第三方API`(purple), `效能`(blue), `權限`(green), `前端UI`(pink) |
| 開發階段 | select | `需求分析`(blue), `規格設計`(purple), `DB 設計`(yellow), `架構設計`(orange), `開發中`(green), `程式碼審查`(pink), `測試中`(red) |
| 修復分支 | rich_text | Git 分支名稱 |
| 說明 | rich_text | 詳細描述 |
| JIRA | rich_text | JIRA 單號 |
| 負責人 | people | 指派人員 |
| 到期日 | date | 截止日期 |
| 建立時間 | created_time | 建立時間（自動） |

### Views

1. **所有任務**（table）
   - 排序：建立時間降序
   - 篩選：專案資料庫（建立 Relation 後設定）
   - 顯示欄位：任務名稱, 狀態, 任務類型, 優先順序, 環境, 負責人, 到期日

2. **依狀態**（board）
   - Group by：狀態
   - 顯示：任務名稱, 任務類型, 優先順序, 負責人

3. **我的任務**（table）
   - 篩選：負責人 = me
   - 排序：狀態（進行中優先）, 到期日升序
   - 顯示欄位：任務名稱, 狀態, 優先順序, 到期日

4. **核對清單**（list）
   - 顯示：狀態 + 任務名稱
   - 排序：建立時間降序

---

## C. Bug 知識庫

### Schema

使用 `notion-create-database` 建立，名稱為「Bug 知識庫」：

| 欄位名稱 | 類型 | 選項 / 說明 |
|----------|------|-------------|
| Name | title | Bug 名稱 / 摘要 |
| Tags | multi_select | `SSO`(blue), `推播`(orange), `排程`(yellow), `報表`(purple), `標籤`(green), `綁定`(pink), `權限`(red), `Rich Menu`(brown), `API`(gray), `Flex Message`(default), `資料異常`(orange), `效能`(blue), `前端UI`(pink) |
| 難易度 | select | `普通(2~4h)`(green), `困難(4~6h)`(red) |
| 參考連結 | url | 相關參考資料 URL |
| 建立時間 | created_time | 建立時間（自動） |

### Views

1. **預設 Table View**（Default）
   - 排序：建立時間降序
   - 顯示欄位：Name, Tags, 難易度, 參考連結, 建立時間

---

## D. 功能設計庫

### Schema

使用 `notion-create-database` 建立，名稱為「功能設計庫」：

| 欄位名稱 | 類型 | 選項 / 說明 |
|----------|------|-------------|
| Name | title | 功能名稱 |
| Tags | multi_select | `API`(blue), `報表`(purple), `標籤`(green), `推播`(orange), `排程`(yellow), `綁定`(pink), `權限`(red), `Rich Menu`(brown), `匯出匯入`(gray), `Flex Message`(default) |
| 設計類型 | select | `規格書`(blue), `DB 設計`(yellow), `架構設計`(orange), `完整設計`(green) |
| 技術棧 | select | `spring-mvc-mybatis`(blue), `spring-boot-mybatis`(green), `spring-boot-jpa`(purple), `spring-boot-mybatis-plus`(orange), `spring-mvc-jpa`(red) |
| 參考連結 | url | 相關參考資料 URL |
| 日期 | date | 設計日期 |

### Views

1. **預設 Table View**（Default）
   - 排序：日期降序
   - 顯示欄位：Name, Tags, 設計類型, 技術棧, 日期

2. **按專案看板**（board）
   - Group by：專案資料庫（建立 Relation 後設定）
   - 顯示：Name, 設計類型, Tags

---

## E. CREW 工作區頁面

### 頁面內容模板

建立工作區頁面時使用以下 Notion-flavored Markdown 作為 content：

```markdown
<database data-source-url="collection://{任務DS_ID}" inline="true" icon="✅">任務追蹤工具</database>

{若有功能設計庫}
<database data-source-url="collection://{功能設計庫DS_ID}" inline="true" icon="📐">功能設計庫</database>

{若有 Bug 知識庫}
<database data-source-url="collection://{BugKB_DS_ID}" inline="true" icon="🐛">Bug 知識庫</database>

<database data-source-url="collection://{專案DS_ID}" inline="true" icon="📂">專案資料庫</database>
```

### 建立步驟

1. 使用 `notion-create-pages` 建立頁面，title=「🚀 CREW 工作區」，icon=「🚀」
2. 使用 `notion-update-page` 的 `replace_content` 寫入上述模板（替換變數）

### 更新步驟（plan-setup 追加功能設計庫時）

使用 `notion-update-page` 的 `update_content`，在 Bug 知識庫前插入功能設計庫的 linked view。

### 排版順序

最終工作區頁面中資料庫的排列順序：

1. 任務追蹤工具
2. 功能設計庫（若有）
3. Bug 知識庫（若有）
4. 專案資料庫
