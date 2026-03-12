# Claude Code Plugins — 公司內部 Marketplace

整合 Notion 與 Claude Code 的自訂 Plugin 集合，涵蓋 Bug 處理與功能開發的完整工作流。

## 快速安裝

```bash
# 1. 加入 Marketplace（一次性）
claude marketplace add --github mark22013333/bug-workflow

# 2. 安裝需要的 Plugin
claude plugin install bug-workflow
claude plugin install feature-workflow
```

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

詳細說明見 [plugins/feature-workflow/README.md](plugins/feature-workflow/README.md)

## 前置條件

1. **Claude Code** — [安裝指南](https://docs.anthropic.com/en/docs/claude-code)
2. **Notion Plugin** — 需先安裝 Notion MCP Server
   ```bash
   claude plugin install Notion
   ```
3. **Notion Workspace** — 需有以下資料庫（或由 setup 引導設定）：
   - **任務追蹤工具**：Bug / 功能 生命週期管理（兩個 Plugin 共用）
   - **專案資料庫**：管理專案與本機路徑對應（兩個 Plugin 共用）
   - **Bug 知識庫**（選用）：Bug 精簡索引
   - **功能設計庫**（選用）：設計文件索引

## 首次設定

安裝 Plugin 後，各自執行一次 setup：

```
/bug-setup        ← 偵測 Notion 資料庫、設定專案對應
/feature-setup    ← 自動匯入 bug-workflow 共用 ID + 設定技術棧
```

建議先執行 `/bug-setup`，`/feature-setup` 會自動匯入共用的 Notion ID 和專案路徑。

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
