# Notion 專案頁面內容模版

`/project-add` 在 Notion 專案資料庫建立或更新專案時，根據偵測到的專案類型套用對應模版產生頁面內容。

---

## 專案類型判斷

| 條件 | 判定 |
|------|------|
| 存在 `kernel/` 或類似外部資源目錄 | 產品型 |
| Gradle 多模組（根 `build.gradle` + 子目錄 `build.gradle`） | 產品型 |
| 偵測到 Solr、Hazelcast 等中介軟體設定 | 產品型 |
| VM Options 超過 5 個自訂參數 | 產品型 |
| 以上皆無 | 簡單型 |

偵測後詢問使用者確認：
```
偵測到專案類型：{簡單型 / 產品型}
確認？[Y/n]（輸入 n 可手動切換）
```

---

## 模版 A — 簡單型專案

適用於單一 WAR/JAR、Maven 單模組、Spring MVC / Spring Boot 等常見 Web 應用。

```markdown
## 📋 專案概要

| 項目 | 說明 |
|------|------|
| 專案類型 | 簡單型 |
| 技術棧 | {自動偵測，如 Spring MVC 4.3 + MyBatis 3.2} |
| 建置工具 | {Maven / Gradle} |
| Java 版本 | {自動偵測} |
| DB | {自動偵測，如 MSSQL} |
| 架構特點 | {如 AP/WEB 分離、單體等} |

## 🏗️ 專案結構

{根據掃描結果填入，範例：}

AP/WEB 分離架構，單一 WAR 部署，透過 JVM 參數區分角色（ap1/ap2/web）。

```
./
├── src/main/java/        # Java 原始碼
├── src/main/resources/   # 設定檔（properties / Spring XML）
├── src/test/             # 測試
├── doc/                  # 部署文件、SQL
├── pom.xml
└── CLAUDE.md
```

## 🔧 建置與執行

### 建置
```
{如 mvn clean package -DskipTests}
```

### 本地執行
```
{如 mvn test -Dserver.role=ap1 -Dspring.profiles.active=test}
```

### VM Options
```
{必要的 JVM 參數，如：}
-Dserver.role=ap1
-Dspring.profiles.active=test
```

## 🗄️ 資料庫

| 環境 | DB 類型 | 說明 |
|------|---------|------|
| 本地測試 | {MSSQL} | {待填} |
| SIT | {MSSQL} | {待填} |
| UAT | {MSSQL} | {待填} |
| PROD | {MSSQL} | {待填} |

## 🖥️ 主機資訊

| 環境 | 角色 | 主機 |
|------|------|------|
| SIT | {角色} | {待填} |
| UAT | {角色} | {待填} |
| PROD | {角色} | {待填} |

## 🚀 部署流程

{待填，或參照專案內 doc/ 目錄}

## ⚠️ 注意事項

{根據 CLAUDE.md 擷取關鍵注意事項}

## 📚 參考連結

{相關文件、Wiki 連結等}
```

---

## 模版 B — 產品型專案

適用於公司產品（SmartRobot / SmartCore 等），特徵：Gradle 多模組、外部 kernel 目錄、大量 VM Options、多種中介軟體。

```markdown
## 📋 專案概要

| 項目 | 說明 |
|------|------|
| 專案類型 | 產品型 |
| 產品名稱 | {如 SmartRobot / SmartCore} |
| 技術棧 | {如 Spring Boot + Gradle} |
| 建置工具 | {Gradle / Maven + Gradle 混合} |
| Java 版本 | {自動偵測} |
| DB | MSSQL（業務資料）+ H2（Quartz 排程） |
| 中介軟體 | {如 Solr, Hazelcast} |

## 🏗️ 專案結構

```
./
├── kernel/                        # 外部資源目錄（不納入 Git）
│   ├── etc/                       # 設定檔（hazelcast, 系統設定）
│   ├── cores.v9/                  # Solr cores
│   └── db/robot/quartz.mv.db     # H2（Quartz 排程用）
├── {模組名稱}/                     # Gradle 子模組
│   ├── src/
│   └── build.gradle
├── build.gradle                   # 根建置檔
└── CLAUDE.md
```

> `kernel/` 目錄不納入 Git，需從指定位置複製或由 DevOps 提供。

## 🔧 建置與執行

### 建置
```
{如 gradle build -x test}
```

### VM Options

> 以下路徑使用 `{PROJECT_ROOT}` 表示專案根目錄，實際值請替換為本機路徑。

```
# JVM 調校
-Xmx3G -Xms512M
-XX:+UseG1GC
-XX:-UseGCOverheadLimit
-XX:+DisableExplicitGC

# 產品識別
-Dwise.version={產品代號，如 SRBT}

# 路徑設定
-D{product}.home={PROJECT_ROOT}
-D{product}.data.path={PROJECT_ROOT}/kernel
-D{product}.cfg.path={PROJECT_ROOT}/kernel/etc

# Solr
-Dsolr.solr.home={PROJECT_ROOT}/kernel/cores.v9
-Dsolr.coreRootDirectory={PROJECT_ROOT}/kernel/cores.v9

# Hazelcast
-Dhazelcast.config={PROJECT_ROOT}/kernel/etc/hazelcast.xml
-Dhazelcast.client.config={PROJECT_ROOT}/kernel/etc/hazelcast-client.xml
-Duse.standalone.hz=false
-Dhazelcast.ignoreXxeProtectionFailures=true

# DB
-Dsql=MSSQL

# 系統
-Dfile.encoding=UTF-8
-Duser.timezone=Asia/Taipei

# 第三方服務（請替換為實際 key）
-D{service}.key={YOUR_KEY}
```

## 🗄️ 資料庫

| DB | 類型 | 用途 | 位置/連線 |
|----|------|------|----------|
| 主資料庫 | MSSQL | 業務資料 | {host:port/database} |
| Quartz | H2（檔案） | 排程任務 | `kernel/db/robot/quartz.mv.db` |

### 各環境連線

| 環境 | MSSQL | 說明 |
|------|-------|------|
| 本地開發 | {待填} | |
| SIT | {待填} | |
| UAT | {待填} | |
| PROD | {待填} | |

## 📦 中介軟體

| 名稱 | 用途 | 設定檔位置 |
|------|------|-----------|
| Solr | 全文檢索 | `kernel/cores.v9/` |
| Hazelcast | 分散式快取/叢集 | `kernel/etc/hazelcast*.xml` |
| {其他} | {用途} | {位置} |

## 🖥️ 主機資訊

| 環境 | 角色 | 主機 |
|------|------|------|
| SIT | AP | {待填} |
| UAT | AP | {待填} |
| PROD | AP | {待填} |

## 🚀 部署流程

{待填}

## ⚠️ 注意事項

- `kernel/` 不納入 Git，新成員需從指定位置取得
- VM Options 的 `{PROJECT_ROOT}` 需替換為實際本機路徑
- H2 資料庫檔案在 `kernel/db/` 下，重建 kernel 時注意保留
- 第三方服務 key 請向專案負責人取得，勿寫入 Git
{根據偵測結果補充}

## 📚 參考連結

{相關文件、Wiki 連結等}
```

---

## 使用方式

`/project-add` 在步驟 4（建立新專案條目）時：

1. 偵測專案類型（簡單型 / 產品型）
2. 套用對應模版
3. 用偵測結果填充 `{佔位符}`
4. 無法偵測的欄位保留 `{待填}` 供使用者稍後在 Notion 補充
5. 使用 `notion-update-page` 將模版內容寫入頁面 body

更新已存在的專案時，**不覆蓋**現有頁面內容，僅在頁面頂部追加缺少的區段。
