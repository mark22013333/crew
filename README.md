# Claude Code Plugins

整合 Notion 與 Claude Code 的自訂 Plugin 集合，涵蓋 Bug 處理與功能開發的完整工作流。

## 快速安裝

```bash
# 安裝 Notion MCP Server（提供 Notion 讀寫能力）
claude plugin install Notion

# 加入 Marketplace → 安裝 → 啟用（用 && 確保依序執行）
claude plugin marketplace add mark22013333/bug-workflow && \
claude plugin install bug-workflow && \
claude plugin install feature-workflow && \
claude plugin enable bug-workflow && \
claude plugin enable feature-workflow
```

安裝完成後**重啟 Claude Code**，然後在專案目錄下執行 `/bug-setup` 和 `/feature-setup` 進行初始化。

> 可用 `claude plugin list` 確認狀態，確保 Plugin 顯示為 `✔ enabled`。

## Plugin 一覽

### Bug Workflow

自動化 Bug 生命週期管理 — 建立、調查、結案、搜尋、復發處理。

| 指令 | 說明 |
|------|------|
| `/bug-setup` | 首次設定引導 |
| `/bug-start <問題簡述>` | 建立 Bug 條目 |
| `/bug-update <內容>` | 更新調查資訊（Log、SQL、判斷） |
| `/bug-update reopen <Bug>` | 重新開啟已結案 Bug |
| `/bug-close` | 結案 + 同步知識庫 |
| `/bug-search <關鍵字>` | 搜尋過往 Bug 解法 |
| `/project-add` | 新增專案到共用專案資料庫 |

詳細說明見 [plugins/bug-workflow/README.md](plugins/bug-workflow/README.md)

### Feature Workflow

功能開發全生命週期管理 — 需求分析、規格設計、DB 設計、架構設計、程式碼骨架產生、品質審查、結案。

含 4 個 Opus Agent，在規格、DB、架構、程式碼產生階段提供專家級輸出。

| 指令 | 說明 |
|------|------|
| `/feature-setup` | 首次設定引導（含 Agent 安裝） |
| `/feature-start <功能簡述>` | 建立功能需求 + Git branch |
| `/feature-spec` | 技術規格書（Agent） |
| `/feature-db` | 資料庫設計（Agent） |
| `/feature-arch` | 架構設計（Agent） |
| `/feature-scaffold [--dry-run]` | 程式碼骨架產生（Agent） |
| `/feature-update <進度>` | 更新開發進度 |
| `/feature-review` | 程式碼品質檢查 |
| `/feature-close` | 結案 + 同步設計庫 |
| `/feature-auto <檔案路徑>` | 讀取規格書自動執行完整流程 |

詳細說明見 [plugins/feature-workflow/README.md](plugins/feature-workflow/README.md)

## 前置條件

1. **Claude Code** — [安裝指南](https://docs.anthropic.com/en/docs/claude-code)
2. **Notion Workspace** — 需有以下資料庫（或由 setup 引導建立）：
   - **任務追蹤工具**：Bug / 功能 生命週期管理（兩個 Plugin 共用）
   - **專案資料庫**：管理專案與本機路徑對應（兩個 Plugin 共用）
   - **Bug 知識庫**（選用）：Bug 精簡索引
   - **功能設計庫**（選用）：設計文件索引

## 首次設定詳細說明

### Step 1：安裝 Notion MCP Server

```bash
claude plugin install Notion
```

安裝後**重啟 Claude Code**，首次使用 Notion 工具時會自動開啟瀏覽器進行 OAuth 授權：

1. 瀏覽器彈出 Notion 授權頁面
2. 選擇要授權的 Workspace
3. 點擊「允許存取」
4. 授權完成後回到 Claude Code

> 每位使用者需各自完成 OAuth 授權，授權範圍僅限自己選擇的 Workspace。

### Step 2：安裝並啟用 Workflow Plugin

```bash
claude plugin marketplace add mark22013333/bug-workflow && \
claude plugin install bug-workflow && \
claude plugin install feature-workflow && \
claude plugin enable bug-workflow && \
claude plugin enable feature-workflow
```

啟用後**重啟 Claude Code**。

### 更新 Plugin

當 Plugin 有新版本時，執行以下指令更新：

```bash
claude plugin update bug-workflow@company-marketplace && \
claude plugin update feature-workflow@company-marketplace
```

更新完成後**重啟 Claude Code** 使新版生效。

> 若 `update` 顯示已是最新但功能未生效，可先卸載再重裝：
> ```bash
> claude plugin uninstall feature-workflow@company-marketplace && \
> claude plugin install feature-workflow@company-marketplace
> ```

### Step 3：執行 Setup 引導

在專案目錄下執行：

```
/bug-setup        ← 偵測 Notion 資料庫、設定專案對應
/feature-setup    ← 自動匯入 bug-workflow 共用 ID + 設定技術棧
```

建議先執行 `/bug-setup`，`/feature-setup` 會自動匯入共用的 Notion ID 和專案路徑。

> Setup 會自動偵測 Workspace 中的資料庫並列出候選讓你選擇，不需要手動輸入任何 ID。

## 跨專案支援

Plugin 透過 `pwd` 自動偵測當前工作目錄，比對設定檔中的「本機路徑」前綴，自動關聯到正確的 Notion 專案。

在不同專案目錄下執行指令，會自動對應不同的 Notion 專案，無需手動切換。

## 設定檔

| 設定檔 | 路徑 | 說明 |
|--------|------|------|
| Bug Workflow | `~/.claude-company/bug-workflow-config.md` | Notion ID、專案對應、欄位對照 |
| Feature Workflow | `~/.claude-company/feature-workflow-config.md` | 同上 + 技術棧定義 |

設定檔儲存位置可在 setup 時選擇公司環境（`~/.claude-company/`）或個人環境（`~/.claude/`）。

## 授權

MIT License
