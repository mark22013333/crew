---
name: crew-init
description: CREW 一鍵首次設定 —— 把 bug-workflow 與 feature-workflow 的初次設定整合成單一指令。當使用者提到 /crew-init、「CREW 一鍵設定」、「初始化 CREW」時觸發此 Skill。
argument-hint: "[--skip-bug] [--skip-plan] [--resume]"
---

# crew-init — CREW 一鍵首次設定

統合首次設定流程，讓新使用者只記得一個指令：

```
/crew-init
```

依序執行：
1. `/bug-setup`（建立 Notion 資料庫 + bug-workflow 設定檔）
2. `/plan-setup`（匯入共用 ID + feature-workflow 設定）
3. 檢查專案指令（`AGENTS.md` / `CLAUDE.md`）；缺失時提示對應 Host 初始化方式
4. 提示 `/project-add`（如當前專案未註冊）

---

## 紀律護欄

> 紀律護欄：`../../references/discipline-preamble.md`（通用紀律）＋ `../../references/anti-rationalizations.md`「crew-init 專用」＋ `../../references/boundaries.md`「crew-init」段。
> Portable config 的實體 root / fallback / representation contract 以 `../../references/config-contract.md` 與 `scripts/crew-config.py` 為權威；本 Skill 只做 read-only 偵測與委派。

---

## 使用方式

```
/crew-init                    # 完整跑首次設定流程
/crew-init --skip-bug         # 強制跳過階段 1，不執行 1a 偵測
/crew-init --skip-plan        # 強制跳過階段 2，不執行 2a 偵測
/crew-init --resume           # 從中斷點續跑，跳過各階段提示直接執行
```

三者關係：階段 1a/2a 本身就會自動偵測設定檔並跳過已完成的階段，因此單純重新執行 `/crew-init`（不加任何旗標）即等同於續跑。`--skip-bug`/`--skip-plan` 是使用者明確斷言「已完成」時的手動旗標，會跳過 1a/2a 的偵測直接進下一階段（用於偵測邏輯誤判或想省下檢查時間的情況）；`--resume` 不改變偵測邏輯，差異只在於不顯示「即將執行 X」的互動提示，直接執行未完成階段。

---

## 前置檢查

執行前自動檢查（不通過則先處理）：

| 項目 | 不通過時 |
|------|---------|
| Node.js ≥ 18 | 顯示對應 OS 安裝指令並終止 |
| Git | 顯示對應 OS 安裝指令並終止 |
| Notion MCP 已安裝 | 提示 `claude plugin install notion`，等使用者完成後重跑 |

進階檢查交由 `/crew-doctor`（完整 18 項，含必要 8 項），本 skill 只跑上表必要 3 項即可開始。

---

## 流程

### 階段 1：bug-workflow 設定

#### 1a. 偵測是否已設定

透過 portable resolver 判斷 `bug/config` 是否存在，不自行列舉 Host-specific path：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"

BUG_CONFIG_JSON="$(python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key bug/config \
  --mode read \
  --format json)"
```

- `source != missing` → 標示為 ✅ 跳過，進階段 2。
- `source=missing` → 進 1b。
- 若 read fallback 找到 legacy source，只代表「已設定」；crew-init 不搬檔、不改檔。

#### 1b. 觸發 /bug-setup

提示使用者：

```
階段 1/4：建立 bug-workflow 設定
即將執行 /bug-setup，這會：
  - 偵測 Notion Workspace 中的「任務追蹤工具」「專案資料庫」資料庫
  - 若不存在則引導從零建立（含標準欄位 + Views + Relation）
  - 依 `bug/config --mode write` contract 產出 canonical portable 設定（實際寫入由 /bug-setup 負責）

需要你的互動（選資料庫、確認 ID 等）

[Enter 繼續，Ctrl+C 終止]
```

呼叫 `/bug-setup` 流程（同 plugin 內可直接觸發），完成後重新執行 1a 的 `bug/config --mode read` 驗證設定已存在。

#### 1c. 失敗處理

bug-setup 失敗或使用者中斷 → 停止 crew-init，提示「下次可用 `/crew-init --resume` 從這裡續跑」。

### 階段 2：feature-workflow 設定

#### 2a. 偵測是否已設定

透過 portable resolver 判斷 `feature/config` 是否存在：

```bash
FEATURE_CONFIG_JSON="$(python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key feature/config \
  --mode read \
  --format json)"
```

- `source != missing` → 標示為 ✅ 跳過，進階段 3。
- `source=missing` → 進 2b。
- 若 `source=legacy`，可附註目前由 resolver compatibility fallback 讀取；是否遷移由 `/plan-setup` 決定，crew-init 不自行搬移。

#### 2b. 觸發 /plan-setup

提示：

```
階段 2/4：建立 feature-workflow 設定
即將執行 /plan-setup，這會：
  - 自動匯入 bug-workflow 共用的 Notion ID（任務追蹤工具、專案資料庫）
  - 提示是否建立「功能設計庫」資料庫（選填）
  - 偵測或設定常用技術棧
  - 依 Feature portable config contract 建立主設定與技術棧資料（實際寫入由 /plan-setup 負責）

[Enter 繼續]
```

呼叫 `/plan-setup`，完成後重新執行 2a 的 `feature/config --mode read` 驗證設定已存在。

### 階段 3：當前專案指令

#### 3a. 偵測

依 `../../references/host-capabilities.md` 的 `project_instructions` 檢查當前 working directory 是否有 `AGENTS.md` 或 `CLAUDE.md`：

```bash
test -f AGENTS.md || test -f CLAUDE.md
```

**至少一份存在** → 標示為 ✅，進階段 4。
**都不存在** → 進 3b。

#### 3b. 提示

```
階段 3/4：當前專案指令
偵測當前目錄：{pwd}
此目錄沒有 AGENTS.md 或 CLAUDE.md，CREW 缺少專案架構與規範上下文。

請依目前 Host 建立至少一份：
  • Codex：建立 AGENTS.md
  • Claude Code：可用 /init 建立 CLAUDE.md
  • 其他 Host：建立 CREW 可讀的 AGENTS.md

建立後建議 commit 並 push，讓團隊共用：
  git add AGENTS.md CLAUDE.md 2>/dev/null || true
  git commit -m "docs: add project instructions" && git push

[Enter 我已建立專案指令，或 s 跳過此步驟]
```

使用者選擇 Enter 後重新檢查；選 s 則標示為 ⚠️ 跳過。

### 階段 4：專案註冊

#### 4a. 偵測

讀取 Git remote 取得 repo identifier：

```bash
git remote get-url origin
# 依共用 repo-id 規則解析為 {repo-id}

PROJECT_CONFIG_JSON="$(python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
  --key feature/project \
  --repo-id "{repo-id}" \
  --mode read \
  --format json)"
```

依 resolver 結果判斷：

- `source=missing` → 尚未註冊，進 4b。
- `representation=hierarchical` → project file 已存在，標示為 ✅ 跳過。
- `representation=legacy_monolith` → 使用既有 monolith parser 確認該 `repo-id` 是否有對應列；有則標示為 ✅，沒有則進 4b。
- legacy source 只作 read compatibility；crew-init 不建立、不更新 project mapping，實際註冊仍委派 `/project-add`。

#### 4b. 提示

```
階段 4/4：專案註冊
當前專案：{repo-id}
此專案尚未註冊，無法用 plan-* / bug-* 指令。

請執行：

  /project-add

這會：
  - 偵測專案類型（簡單型 / 產品型）
  - 偵測建置工具、技術棧、DB 類型
  - 註冊到 Notion 專案資料庫
  - 可選安裝 DB MCP（DBHub）

[Enter 我已執行 /project-add，或 s 跳過]
```

### 5. 結尾摘要

```
═══════════════════════════════════════════
🎉 CREW 一鍵設定完成
═══════════════════════════════════════════

階段 1/4 bug-workflow 設定        ✅
階段 2/4 feature-workflow 設定    ✅
階段 3/4 當前專案指令            ✅
階段 4/4 專案註冊                  ✅

可用指令：
  /bug-investigate              開始調查 Bug
  /plan-start <任務簡述>        建立功能任務
  /plan-next                    查看下一步建議

進階：
  /crew-doctor                  18 項依賴完整檢查
  /crew-upgrade                 更新 CREW plugins
```

若有跳過步驟，摘要會顯示 ⚠️ 並提示對應的單獨指令補做。

---

## --resume 模式

省略階段 1-4 中已 ✅ 的部分，直接進到第一個未完成階段。

實作上 `--resume` = 跑每階段的偵測（1a/2a/3a/4a），自動跳過 ✅，從第一個未完成處執行。
與不加 `--resume` 的差別：不加時每階段都顯示提示「即將執行 X」；加 `--resume` 時跳過提示直接執行。

---

## 何時不用

- 只想設定 bug 側 → 改用 `/bug-setup`
- 只想設定 feature 側 → 改用 `/plan-setup`
- 只想註冊專案到 Notion → 改用 `/project-add`
- 只想初始化專案指令 → Codex 建立 `AGENTS.md`；Claude Code 可用內建 `/init`
- 只想做 CREW 環境檢查 → 改用 `/crew-doctor`

---

## Gotchas

- **/bug-setup 或 /plan-setup 中斷不會自動回滾**：使用者選 Ctrl+C 後可能留下半成品設定檔。crew-init 不嘗試清理，由使用者下次用 `--resume` 接續
- **Notion OAuth 未完成**：bug-setup 第一次使用 Notion MCP 會觸發 OAuth，使用者必須切瀏覽器完成授權。crew-init 不能加速這部分
- **同名 Notion Workspace**：bug-setup 偵測 Workspace 時若使用者有多個同名 → 由 bug-setup 內部處理，crew-init 不介入
- **路徑空格**：當前目錄含空格時 `git remote` 不受影響，但專案路徑要正確引用

---

## 邊界情況

- **專案指令存在但不完整**：本 skill 只檢查 `AGENTS.md` / `CLAUDE.md` 至少一份存在，不判斷內容品質；後續 Skill 依 `project_instructions` 讀取
- **使用者跳過所有步驟（連按 s）**：摘要顯示全部 ⚠️，提示「至少需完成階段 1+2 才能用大部分 Skill」
- **非 Git 專案**：階段 4 偵測 `git remote` 失敗時，標示為 ⏭️ 不適用（非 git 專案不需註冊）
- **跨 Host / WSL2 / Windows 桌面版混用**：是否已設定只看 `crew-config.py` resolver 結果；portable root 可由 `CREW_CONFIG_HOME` 或 XDG-style root 統一。crew-init 不假設任何 Host-specific 共用目錄。
