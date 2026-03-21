# plan-* 共用邏輯

所有 `plan-spec`、`plan-db`、`plan-arch` 共用以下邏輯。

---

## 定位活躍任務

按優先順序匹配：

1. 從 Git branch 匹配：讀取 `.spec/_index.md`，找「分支」欄位與當前 `git branch --show-current` 匹配的任務
2. 若匹配到的任務 status 為 `暫停` → 提示「此任務已暫停，是否恢復？[Y/n]」，確認後執行 unpark 流程（見 `/plan-status --unpark`）再繼續
3. 若只有一個進行中任務 → 自動選定
4. 若多個進行中 → 列出供選擇
5. 若無進行中 → 提示先執行 `/plan-start`

選定後讀取 `.spec/{slug}/README.md`，取得 `type`、`name`、`status`、`tech_stack` 等元資訊。

---

## 讀取專案上下文

### 專案 CLAUDE.md

讀取 `pwd` 下最近的 CLAUDE.md（向上搜尋），取得技術棧、架構模式、分層規則、命名慣例。

### 技術棧資訊

從 `.spec/{slug}/README.md` 的 `tech_stack` 欄位取得技術棧 ID，依 `references/config-resolver.md` 的第 3 層載入邏輯讀取對應定義：
- 內建技術棧 → `stacks/_builtin.md`
- 自訂技術棧 → `stacks/{id}.md`

### 現有程式碼參考

使用 Glob/Grep 掃描與需求相關的現有程式碼（1-2 個 Controller、Service、Entity），了解 API 風格、命名慣例。

### 規範檔案

讀取可用的規範檔案：
- `~/.claude/rules/database.md`（DB 設計時）
- `~/.claude/rules/design-patterns.md`（架構設計時）
- `~/.claude/rules/java-performance.md`（效能相關）

---

---

## 一致性驗證（自動）

每個 Skill 完成後，**自動**執行交叉比對，使用者無需手動觸發。

### 檢查項目

| 檢查項目 | 比對來源 | 具體檢查 |
|---------|---------|---------|
| API-DB 一致性 | spec.md ↔ db.md | spec 中每個 API 的請求/回應欄位，db.md 是否有對應表欄位 |
| DB-Arch 一致性 | db.md ↔ arch.md | db.md 的每個表，arch.md 是否有對應 POJO 和 Mapper |
| API-Arch 一致性 | spec.md ↔ arch.md | spec 的每個 API 端點，arch.md 是否有對應 Controller 方法 |
| 判斷區塊完整性 | spec.md | FRONTEND_REQUIRED / DB_REQUIRED 是否為 true/false |
| DB_TABLES 對應 | spec.md ↔ db.md | 判斷區塊的 DB_TABLES 是否與 db.md 表清單一致 |

> **觸發條件**：僅在比對的兩端檔案都存在時才執行該項檢查。例如執行 `/plan-spec` 時，因 db.md 和 arch.md 不存在，僅檢查「判斷區塊完整性」。

### 分類

- 🔴 **不一致**：文件間矛盾（如 spec 定義的 API 欄位在 db.md 找不到對應表欄位）
- 🟡 **遺漏**：缺少預期內容（如 db.md 有表但缺少索引建議）
- 🟢 **良好**：交叉比對通過

### 自動修復流程

發現問題時：
1. 顯示「發現 N 個不一致，修復中...（第 1/2 輪）」
2. 備份受影響的文件（`{file}.bak`）
3. 直接修改受影響的文件，補齊遺漏或修正矛盾
4. 重新執行檢查（最多 **2 輪**）
5. 2 輪後仍有問題 → 列出剩餘摘要，**不阻擋流程**

---

## 更新日誌

每次規劃完成，在 `.spec/{slug}/log.md` 追加一筆紀錄：

```markdown
### [{日期}] {Skill 名稱}完成
- 產出檔案：{檔案路徑}
- 摘要：{一句話描述}
```

若 `log.md` 不存在則建立。

---

## 共用 Gotchas

- **spec.md「判斷」區塊格式是 plan-build 的入口**：`FRONTEND_REQUIRED` 和 `DB_REQUIRED` 的值直接決定 plan-build 的團隊組成。格式錯誤（如用中文「是/否」而非 `true/false`）會 fallback 到預設值。
- **Agent subagent 的 model 參數**：prompt 中寫「使用 Opus 模型」只是自然語言指示，不保證生效。必須在 Agent tool 的 `model` 參數實際設定 `"opus"`。
- **重新執行覆蓋已有檔案**：覆蓋前會備份到 `{file}.bak`，但 `.bak` 只保留一份。

## 共用邊界情況

- **`.spec/` 目錄不存在**：提示先執行 `/plan-start`
- **找不到活躍任務**：提示先執行 `/plan-start` 或檢查 `_index.md`
- **前置檔案不存在**：提示建議先執行前置步驟，但不強制阻擋
- **重新執行同一 Skill**：覆蓋已有檔案（先備份舊版到 `{file}.bak`）
