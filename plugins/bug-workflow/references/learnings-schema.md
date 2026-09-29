# Bug 學習系統

## 儲存位置

Learning storage 使用 portable logical key：

`bug/learning --project-slug {project-slug}`

Canonical path 由 `scripts/crew-config.py` 依 `references/config-contract.md` 決定；
consumer 不應自行拼 Host-specific 實體路徑。

概念結構：

```text
{portable-config-root}/bug/learnings/
├── {project-slug-1}.jsonl    # 專案 A 的學習
├── {project-slug-2}.jsonl    # 專案 B 的學習
└── ...
```

`project-slug` 來自 Git Repo 識別碼（`/` 替換為 `-`），並必須符合 resolver 的安全單一檔名規則。

## JSONL 格式

每行一筆 JSON：

```json
{
  "date": "2026-04-24",
  "skill": "bug-close",
  "bug_title": "推播排程發送失敗",
  "root_cause": "LINE API refresh 回傳 503 未處理",
  "pattern": "third-party-api",
  "type": "pitfall",
  "insight": "LINE API 的 refresh token 端點偶爾回傳 503",
  "confidence": 9,
  "files": ["PushService.java"],
  "notion_url": "https://www.notion.so/xxx"
}
```

## 欄位定義

| 欄位 | 必要 | 說明 |
|------|:---:|------|
| date | ✅ | 學習日期 YYYY-MM-DD |
| skill | ✅ | 來源 Skill（bug-close / bug-investigate） |
| bug_title | ✅ | Bug 標題 |
| root_cause | ✅ | 根因摘要 |
| pattern | ✅ | 匹配的 bug 模式（npe / sql / third-party-api / concurrency / config / cache / frontend） |
| type | ✅ | 學習類型（pattern / pitfall / architecture / environment） |
| insight | ✅ | 可複用的洞察（一句話） |
| confidence | ✅ | 信心度 1-10（10=確認的事實，5=推論，1=猜測） |
| files | ✅ | 相關檔案路徑（用於過時偵測：檔案刪除時標記 stale） |
| notion_url | 選填 | Notion 頁面連結（可追溯原始 bug） |

## 搜尋邏輯（bug-investigate 使用）

### 基本搜尋

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
LEARN_FILE="$(python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key bug/learning \
  --project-slug "{project-slug}" \
  --mode read \
  --format path)"

[ -f "$LEARN_FILE" ] && grep -i "<keyword>" "$LEARN_FILE" | tail -10
```

Read resolution 順序由 `config-contract.md` 定義；reference 不直接依賴 Host-specific storage path。

### 進階搜尋（AI 執行）

1. 從 bug 描述和 stacktrace 擷取關鍵字
2. grep 搜尋 `.jsonl`，取得候選學習
3. AI 判斷相關性，過濾 false positive
4. 檢查 files 欄位的檔案是否仍存在（過時偵測）
5. 按 confidence 降序排列，取前 5 筆

### 過時偵測

```bash
for file in $(echo "$learning" | jq -r '.files[]'); do
  [ ! -f "$file" ] && echo "STALE: $file"
done
```

若所有 files 都不存在 → 標記為可能過時，顯示時加 `⚠️ 檔案已不存在，可能過時` 提示。

## 寫入時機

| Skill | 何時寫入 | 條件 |
|-------|---------|------|
| bug-close | 學習捕捉步驟 | AI 判斷有學習價值；以 `bug/learning --mode write` 寫 portable canonical path |
| bug-investigate | Phase 4 根因確認後 | 根因涉及非顯而易見的知識 |

## 容量管理

- 每個專案的 `.jsonl` 不主動清理
- 若超過 500 行 → 在搜尋時提示使用者「學習檔案較大，建議定期檢視」
- 未來可考慮依 confidence 和 date 自動淘汰
