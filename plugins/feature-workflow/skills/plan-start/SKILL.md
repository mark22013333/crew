---
name: plan-start
description: 建立 Notion 條目 + .spec/ 本地規劃目錄 + Git branch 的統一入口。支援 feature 和 bug 兩種類型。當使用者提到「plan-start」、「新任務」、「開始規劃」時觸發此 Skill。
---

# plan-start — 統一任務入口（本地規劃模式）

在 Notion「任務追蹤工具」建立條目，同時在專案根目錄建立 `.spec/{slug}/` 本地規劃目錄，並可選建立 Git branch。支援 Feature 和 Bug 兩種類型。

---

## 設定檔

執行前依序檢查以下路徑，讀取第一個找到的設定檔：
1. `~/.claude-company/feature-workflow-config.md`（公司環境）
2. `~/.claude/feature-workflow-config.md`（個人環境）

Bug 類型還需檢查：
1. `~/.claude-company/bug-workflow-config.md`
2. `~/.claude/bug-workflow-config.md`

若都不存在，提示使用者先執行 `/plan-setup` 或 `/bug-setup`。

---

## 流程

> **前置檢查**：參照 bug-workflow plugin 的 `references/prerequisites.md` 執行完整前置檢查（CLAUDE.md + 設定檔 + 專案註冊）。

### 1. 解析使用者輸入

使用者會以以下格式觸發：

```
/plan-start <任務簡述> [選項]
```

**類型推斷**：
- 明確指定：`/plan-start feature 推播標籤查詢` 或 `/plan-start bug SSO 登入錯誤`
- 關鍵字推斷：輸入含「bug」、「錯誤」、「問題」、「修復」、「異常」→ type=bug
- 預設為 feature

**Bug 關聯選項**：
- `--related <feature-slug>`：手動指定關聯的 feature

### 2. 偵測環境資訊（自動專案對應）

自動偵測環境：

```bash
git branch --show-current 2>/dev/null || echo ""
pwd
git remote get-url origin 2>/dev/null || echo ""
```

Git Repo 識別碼解析規則：
- Git host 含 `intumit`（公司 GitLab）→ 只取 `{group}/{repo}`
- 其他（GitHub 等）→ 加上 host：`{host}/{group}/{repo}`
- 去除 `.git` 後綴

自動專案對應：讀取設定檔「專案對應」表，精確匹配「Git Repo」欄位。匹配失敗則進入互動式選擇。

### 3. 互動式補充資訊

#### Feature 類型

1. **所屬專案**（若自動偵測失敗）
2. **優先順序**（預設「中」）：`高` / `中` / `低`
3. **難度**（預設「中」）：`小` / `中` / `大`

#### Bug 類型

1. **所屬專案**（若自動偵測失敗）
2. **環境**（預設「正式」）：`測試` / `UAT` / `正式`
3. **優先順序**（預設「中」）：`高` / `中` / `低`

### 4. 產生 slug

從任務簡述產生英文 slug：
- 中文 → 翻譯為簡短英文（如「推播標籤查詢」→ `push-tag-query`）
- 已經是英文 → 轉為 kebab-case
- 確認 `.spec/{slug}/` 不存在，若存在則加數字後綴

### 5. 建立 Notion 條目

#### Feature 類型

使用 `notion-create-pages` 在「任務追蹤工具」建立，Properties：

| 欄位 | 值 |
|------|-----|
| 任務名稱 | 使用者提供的任務簡述 |
| 任務類型 | `["💬 功能要求"]` |
| 狀態 | `進行中` |
| 優先順序 | 使用者選擇 |
| 難度 | 使用者選擇 |
| 開發階段 | `需求分析` |
| 專案資料庫 | 關聯的專案頁面 URL |

頁面 content 使用 `references/notion-page-template.md` 的標準 7 區塊模板。

#### Bug 類型

使用 `notion-create-pages`，Properties 同 `bug-start`：

| 欄位 | 值 |
|------|-----|
| 任務名稱 | 使用者提供的任務簡述 |
| 任務類型 | `["🐞 錯誤"]` |
| 狀態 | `進行中` |
| 優先順序 | 使用者選擇 |
| 環境 | 使用者選擇 |
| 專案資料庫 | 關聯的專案頁面 URL |

頁面 content 使用 bug-start 的標準模板。

### 6. 建立 .spec/ 本地規劃目錄

#### 6-1. 確保 .gitignore 包含 .spec/

檢查專案根目錄的 `.gitignore`，若不包含 `.spec/` 則追加：

```
# Local spec files (managed by plan-* skills)
.spec/
```

#### 6-2. 建立目錄結構

**Feature 類型**：

```bash
mkdir -p .spec/{slug}
```

建立 `README.md`：

```markdown
---
type: feature
name: {任務簡述}
slug: {slug}
status: 需求分析
notion_url: {Notion 頁面 URL}
notion_page_id: {Notion 頁面 ID}
branch: {Git branch 名稱，若後續建立}
tech_stack: {技術棧 ID，從設定檔取得}
created: {當前日期 YYYY-MM-DD}
---

# {任務簡述}

## 需求描述

{使用者提供的描述，或待填寫}
```

**Bug 類型**：

```bash
mkdir -p .spec/{slug}
```

建立 `README.md`：

```markdown
---
type: bug
name: {任務簡述}
slug: {slug}
status: 調查中
notion_url: {Notion 頁面 URL}
notion_page_id: {Notion 頁面 ID}
branch: {Git branch 名稱，若後續建立}
related_feature: {關聯的 feature slug，若有}
related_feature_notion: {關聯 feature 的 Notion URL，若有}
created: {當前日期 YYYY-MM-DD}
---

# {任務簡述}

## 問題描述

{使用者提供的描述，或待填寫}
```

#### 6-3. Bug 自動關聯 Feature

若使用者指定 `--related <feature-slug>`：
- 驗證 `.spec/{feature-slug}/` 存在
- 讀取其 `README.md` 取得 `notion_url`
- 填入 Bug README.md 的 `related_feature` 和 `related_feature_notion`

若未指定，嘗試智慧匹配：
1. 掃描 `.spec/` 下所有目錄的 `README.md`（type=feature 且 status 非「需求分析」）
2. 從 Bug 描述中擷取關鍵字（Controller 名稱、Service 名稱、表名等）
3. 比對各 feature 的 `spec.md`、`arch.md`、`db.md` 中的類別名和表名
4. 若匹配成功，提示使用者確認
5. 若無法判斷，跳過（使用者可後續手動指定）

### 7. 更新 .spec/_index.md

讀取或建立 `.spec/_index.md`：

```markdown
# 任務索引

## 進行中

| slug | 類型 | 名稱 | 狀態 | 分支 | Notion | 建立日期 |
|------|------|------|------|------|--------|---------|
| {slug} | {feature/bug} | {名稱} | {狀態} | {branch} | [連結]({url}) | {日期} |

## 已完成

| slug | 類型 | 名稱 | 完成日期 | Notion |
|------|------|------|---------|--------|
```

在「進行中」表格新增一列。

### 8. 建立 Git branch

```
是否建立 Git branch？
1. 是，建立 {feature|hotfix}/{slug}（從當前分支）
2. 是，自訂分支名稱
3. 否，稍後再建立
```

若選擇建立：
1. `git checkout -b {type}/{slug}`（feature → `feature/{slug}`，bug → `hotfix/{slug}`）
2. 更新 Notion 條目的「修復分支」欄位
3. 更新 `.spec/{slug}/README.md` 的 `branch` 欄位

### 9. 回傳結果

```
任務已建立！

📋 Notion 頁面：{URL}
📁 本地規劃：.spec/{slug}/
🔀 Git branch：{branch}（若有）
📊 類型：{Feature / Bug}

後續可使用：
  • /plan [spec|db|arch]    — 本地規劃（不呼叫 Notion）
  • /plan-build             — Agent Teams 產生程式碼
  • /plan-review            — Agent Teams 審查
  • /plan-status            — 查看所有任務狀態
  • /plan-close             — 結案並同步 Notion
```

---

## 邊界情況

- **設定檔不存在**：提示先執行 `/plan-setup` 或 `/bug-setup`
- **不在 Git repo 中**：跳過分支和專案自動偵測
- **`.spec/` 目錄已存在同名 slug**：加數字後綴或詢問使用者
- **Notion API 失敗**：仍建立本地 `.spec/` 目錄，`notion_page_id` 留空，提示使用者可稍後用 `/plan-sync` 補建
- **分支名稱衝突**：提示自訂名稱
