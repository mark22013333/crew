# 共用前置檢查

所有 CREW Skill（除 `bug-setup`、`plan-setup`、`project-add` 本身外）在流程開始前必須執行以下檢查。

---

## 檢查項目

### 1. CLAUDE.md 是否存在？

檢查當前專案根目錄（`pwd` 或 Git root）是否有 `CLAUDE.md`。

- **存在** → 繼續
- **不存在** → 提示並中止：
  ```
  ⚠️ 當前專案尚未初始化。
  請先執行 /init 建立 CLAUDE.md，讓 Claude Code 了解專案架構。
  建立後建議 commit 並 push，讓團隊成員共用。
  ```

### 2. Workflow 設定檔是否存在？

依序檢查：
1. `~/.claude-company/bug-workflow-config.md`
2. `~/.claude/bug-workflow-config.md`
3. `~/.claude-company/feature-workflow-config.md`
4. `~/.claude/feature-workflow-config.md`

- **至少找到一個** → 繼續
- **全部不存在** → 提示並中止：
  ```
  ⚠️ 尚未完成 Workflow 初始設定。
  請先執行 /bug-setup（Bug 工作流）或 /plan-setup（功能開發工作流）。
  ```

### 3. 當前專案是否已註冊？

從 `git remote get-url origin` 解析 Git Repo 識別碼，比對設定檔中的「專案對應」表。

- **已註冊** → 繼續，取得對應的 Notion 專案名稱
- **未註冊** → 提示（非中止，部分 Skill 仍可使用）：
  ```
  ⚠️ 當前專案尚未註冊到 Notion。
  建議執行 /project-add 將專案加入 Notion 專案資料庫。
  ```

---

## 適用範圍

| Skill | 需要前置檢查？ | 說明 |
|-------|:---:|------|
| `bug-setup` | ❌ | 本身就是初始化 |
| `plan-setup` | ❌ | 本身就是初始化 |
| `project-add` | ⚠️ | 只檢查第 2 項（設定檔），不檢查第 1、3 項 |
| `bug-start` | ✅ | 完整檢查 1 + 2 + 3 |
| `bug-update` | ✅ | 完整檢查 1 + 2 + 3 |
| `bug-close` | ✅ | 完整檢查 1 + 2 + 3 |
| `bug-search` | ✅ | 只檢查第 2 項 |
| `plan-start` | ✅ | 完整檢查 1 + 2 + 3 |
| `plan` | ✅ | 只檢查第 1 項 |
| `plan-build` | ✅ | 只檢查第 1 項 |
| `plan-verify` | ✅ | 只檢查第 1 項 |
| `plan-review` | ✅ | 只檢查第 1 項 |
| `plan-close` | ✅ | 完整檢查 1 + 2 + 3 |
| `plan-sync` | ✅ | 完整檢查 1 + 2 + 3 |
| `plan-status` | ✅ | 只檢查第 1 項 |
| `plan-stack` | ✅ | 只檢查第 1 項 |
