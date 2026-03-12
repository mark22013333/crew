# Feature Workflow Plugin

功能開發工作流 — 整合 Notion 與 Claude Code，涵蓋需求分析、規格設計、DB 設計、架構設計、程式碼骨架產生、品質審查到結案的完整生命週期管理。

## 安裝

```bash
claude plugin marketplace add mark22013333/bug-workflow && \
claude plugin install feature-workflow && \
claude plugin enable feature-workflow
```

首次使用前執行設定引導：

```
/feature-setup
```

## 流程總覽

```
/feature-setup (首次，一次性)
        │
        ▼
/feature-start <功能簡述>          ← 建立 Notion 頁面 + Git branch
  │  階段: 需求分析
  ▼
/feature-spec [補充需求]           ← Agent(opus) 產出技術規格書
  │  階段: 規格設計
  ▼
/feature-db [補充說明]             ← Agent(opus) 設計 DB + 產出 SQL
  │  階段: DB 設計
  ▼
/feature-arch [補充說明]           ← Agent(opus) 設計分層架構 + 介面
  │  階段: 架構設計
  ▼
/feature-scaffold [--dry-run]     ← Agent(opus) 產生程式碼骨架
  │  階段: 開發中
  │
  ├── /feature-update <進度>       ← 隨時可穿插使用
  │
  ▼
/feature-review                    ← 程式碼品質檢查
  │  階段: 程式碼審查
  ▼
/feature-close                     ← 結案 + 同步設計庫
     階段: 測試中
```

流程非強制線性，可跳過任何步驟、反覆執行、隨時用 feature-update 記錄。

## Skill 清單

| Skill | 說明 |
|-------|------|
| `/feature-setup` | 首次設定引導（含 Agent 安裝選項） |
| `/feature-start` | 建立功能需求 Notion 頁面 + Git branch |
| `/feature-spec` | 技術規格書（Agent, opus） |
| `/feature-db` | 資料庫設計（Agent, opus） |
| `/feature-arch` | 架構設計（Agent, opus） |
| `/feature-scaffold` | 程式碼骨架產生（Agent, opus） |
| `/feature-update` | 更新開發進度 |
| `/feature-review` | 程式碼品質檢查 |
| `/feature-close` | 結案 + 同步設計庫 |

## 技術棧支援

### 內建技術棧

| ID | 框架 | ORM | scaffold 行為 |
|----|------|-----|--------------|
| `spring-mvc-mybatis` | Spring MVC 4.x | MyBatis + tk.mybatis | POJO + Mapper XML + Service(Interface+Impl) + Controller |
| `spring-boot-mybatis` | Spring Boot 2.x+ | MyBatis + tk.mybatis | Entity + Mapper + Service + Controller + DTO |
| `spring-boot-jpa` | Spring Boot 2.x+ | JPA/Hibernate | Entity + Repository + Service + Controller + DTO |
| `spring-boot-mybatis-plus` | Spring Boot 2.x+ | MyBatis-Plus | Entity + BaseMapper + Service(IService+Impl) + Controller |

### 自訂技術棧

1. 在設定檔的「自訂技術棧」表新增一筆
2. 在專案 CLAUDE.md 描述該框架的分層慣例
3. scaffold 會根據 ID 讀取專案中的範本程式碼來產生

## Agent 雙模式

### 模式 A：SKILL.md 內嵌指示（預設）

安裝 Plugin 即可使用，Skill 執行時透過 Agent tool 內嵌完整 prompt 啟動 opus Agent。

### 模式 B：獨立 Agent 檔案（選用）

`/feature-setup` 時可選安裝 4 個獨立 Agent 到 `~/.claude-company/agents/` 或 `~/.claude/agents/`，安裝後可在任何對話中獨立使用。

| Agent | 用於 | 核心能力 |
|-------|------|---------|
| feature-spec-analyst | feature-spec | 需求拆解、API 設計 |
| feature-db-designer | feature-db | 表結構、索引、遷移 SQL |
| feature-backend-designer | feature-arch | 分層設計、設計模式 |
| feature-code-generator | feature-scaffold | 按專案慣例產生程式碼 |

## 通用化設計

此 Plugin 不綁定任何特定專案架構。所有 Agent/Skill 在執行時會先讀取當前專案的 CLAUDE.md，動態適配：

- 技術棧和框架版本
- 分層慣例和 package 結構
- 命名規範和程式碼風格
- 設計模式偏好
- Git Flow 和部署流程

## 與 bug-workflow 的關係

- 共用「任務追蹤工具」和「專案資料庫」Notion 資料庫
- setup 自動匯入 bug-workflow 的共用 ID 和專案路徑
- 互不干擾，可同時使用

## 授權

MIT License
