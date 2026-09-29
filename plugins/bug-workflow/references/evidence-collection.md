# 環境快照／證據收集（共用邏輯）

`/bug-start`（建立時的初始快照）與 `/bug-investigate`（Phase 1 完整證據收集）共用以下收集指令與 Notion 寫入格式，兩者皆為自動執行、不需使用者介入。

---

## 共用收集項目

### 環境狀態

```bash
git branch --show-current
git status --short
```

寫入「調查過程 > 環境狀態」：分支名稱、未提交變更檔案數。

### 知識庫搜尋

用 bug 標題／描述關鍵字搜尋 Notion Bug 知識庫（Data Source ID 見設定檔）：

- 若有相似案例 → 寫入「調查過程 > 歷史參考」
- 格式：「[{日期}] {類似 bug 標題} — 根因：{摘要}」

### 學習搜尋

先用 portable config resolver 解析本專案的 learning read path：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
LEARN_FILE="$(python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key bug/learning \
  --project-slug "{project-slug}" \
  --mode read \
  --format path)"

[ -f "$LEARN_FILE" ] && grep -i "<keywords>" "$LEARN_FILE" | tail -3
```

`--mode read` 會先找 portable canonical file，再依 `config-contract.md` 使用現役 Host fallback；
全部不存在時回 canonical missing path，因此既有 `[ -f ... ]` 會自然靜默跳過。

若有匹配 → 寫入「調查過程 > 歷史學習」，格式：「{insight}（confidence {N}/10，{date}）」。

---

## 共用 Notion 寫入格式

使用 `update_content` 前，必須先 `notion-fetch` 取得現有內容，將新內容附加到現有內容後面再寫回，避免覆蓋。

三段共用區塊格式：

```markdown
**環境狀態**：
- 分支：{branch}
- 未提交變更：{N} 個檔案

**歷史參考**：
- [{日期}] {類似 bug 標題} — 根因：{摘要}

**歷史學習**：
- {insight}（confidence {N}/10，{date}）
```

> **格式說明**：「歷史參考」為 `/bug-start` 與 `/bug-investigate` 兩個 skill 統一後的格式；bug-investigate 原本「{標題}：{根因}（{日期}）」的寫法已併入此格式，不再單獨使用。

呼叫端在此三段前後可自行加上專屬區塊（如最近 commit、錯誤 Log、stacktrace）與各自的標題（如「### [HH:mm] 初始環境快照」或「### [HH:mm] 自動收集的證據」）。

---

## 不阻擋流程

任何收集步驟失敗（如知識庫未設定、不在 Git repo 中、學習檔案不存在）都靜默跳過，不影響主流程。
