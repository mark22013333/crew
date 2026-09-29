# DB MCP（DBHub）— 選配資料庫能力

DBHub 是可選的 database MCP server。CREW 把它視為 `tool_probe(tool_kind=database)` 可以發現的一種 adapter capability，不把 DBHub、某一家 MCP CLI 或固定安裝路徑當成核心 workflow 前置。

官方 DBHub 目前支援 PostgreSQL、MySQL、MariaDB、SQL Server、Oracle 與 SQLite，並提供 `execute_sql`、`search_objects` 等 MCP tools。實際版本、安裝方式與 Node runtime 需求請以 DBHub upstream 文件為準。

## CREW 使用原則

- 有 DB capability：可查真實 schema/object/query evidence。
- 沒有 DB capability：走既有 no-DB fallback，**不得猜 schema**。
- 預設優先 read-only / guardrail 設定；任何寫入資料操作都要符合專案權限與 Human approval。
- 密碼/DSN 不應提交到 Git。

---

## Claude Code adapter 範例

若目前 Claude Code 版本支援 MCP CLI，可用類似：

```bash
claude mcp add dbhub --scope project -- \
  npx @bytebase/dbhub@latest --transport stdio \
  --dsn "sqlserver://user:password@host:1433/database"
```

安裝後以**實際工具可呼叫性**確認成功，不要只看 `claude mcp list` 字串就當成 CREW portable contract。

Claude project-level MCP/settings 檔屬 Host adapter；其中若含密碼，必須確認已被 gitignore。

## Codex / 其他 Host

使用該 Host 當下支援的 MCP / plugin / tool integration 方式啟動 DBHub。CREW 不在文件中臆造某個固定 Codex MCP CLI 語法；只要目前 session 能實際 probe 到 database tools，就可使用同一套 workflow。

---

## 多連線 / TOML

DBHub 支援 TOML 設定多個 sources 與 guardrails。示意：

```toml
[[sources]]
id = "mydb"
dsn = "postgres://user:password@host:5432/database"

[[tools]]
name = "execute_sql"
source = "mydb"
readonly = true
max_rows = 1000
```

不同 DB / DBHub 版本支援的 TOML 欄位可能不同，請依 upstream 文件驗證，不要把這份示例當完整 schema。

---

## 安全建議

- 開發/除錯優先唯讀連線。
- 使用最小權限帳號。
- DSN 優先由環境變數或 Host secret/settings 提供。
- production troubleshooting 應另外套用組織層級的 approval / audit / access-control 規則。

## 相關

- DBHub upstream: <https://github.com/bytebase/dbhub>
- CREW Host Capability Contract: [../plugins/bug-workflow/references/host-capabilities.md](../plugins/bug-workflow/references/host-capabilities.md)
