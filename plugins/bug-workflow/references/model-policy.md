# 模型分工政策（共用）

> 適用 `bug-workflow` 與 `feature-workflow` 的所有 skill。
> 本檔只規範「哪個角色需要哪種模型能力、怎麼把模型目標交給 Host capability、誰可以改正式程式碼」，
> Host 工具對映見 `host-capabilities.md`。**不改變任何既有流程步驟**（判斷區塊、退出驗證、`.spec/` 狀態、Notion 同步一律照原本走）。
>
> 兩 plugin 各帶一份副本；權威來源是 `plugins/bug-workflow/references/model-policy.md`
> （同步規則見 CONTRIBUTING.md「共用 reference 同步規則」）。

---

## 鐵律：模型目標一律結構化，Host 不得假裝已套用

| 規則 | 說明 |
|------|------|
| 只認結構化目標，不認敘述 | prompt 裡寫「使用 Opus 模型」只是自然語言指示，**不保證生效**。Capability request 必須帶 `model: opus|sonnet|haiku` |
| 每個委派各自帶 | 多角色時每個 `delegate_readonly` / `delegate_write` 都各自帶自己的 `model` 目標；不可用自然語言假裝整個 team 已切模型 |
| 角色切換要拆工作單元 | 「先 Sonnet 探索、再 Opus 實作」必須是兩個 capability invocation；不可在同一個模糊工作單元裡說「中途換模型」 |
| Host 做不到就明說 | Host 若無 per-worker model selection，保留角色與權限邊界並回報 `routing_degraded=true`；**不得宣稱已套用指定模型** |
| 不許含糊 | 禁止寫「視情況選用模型」「依需求決定 model」這類沒有具體參數的措辭。條件式配置要寫清楚「什麼條件 → 哪個值」 |

正確寫法（Capability request）：

```yaml
capability: delegate_readonly
role: explorer
model: sonnet
```

```yaml
capability: delegate_write
role: implementer
model: opus
```

Claude Code adapter 會把上述 `model` 目標轉成實際 Agent/subagent 結構化參數；其他 Host 依 `host-capabilities.md` 對映。

---

## Sonnet：文件、探索與驗證（預設）

下列工作**固定或預設**使用 `model: "sonnet"`：

- 閱讀需求與規格文件
- 閱讀與整理 `.spec/` 文件
- 產出、摘要或修改技術規格
- 搜尋與閱讀既有程式碼
- 尋找相似功能與程式風格範本
- 追蹤呼叫關係及影響範圍
- 收集 Bug 證據
- 閱讀及分析日誌
- 分析 Git 歷史
- 分析編譯與測試輸出
- 一般程式碼品質檢查
- 整理交接給實作者的上下文

執行上述工作時：

- 優先使用唯讀工具。
- **不得修改正式產品程式碼**；可以寫入 `.spec/`、報告、規格與工作紀錄。
- 不得因文件數量多或內容較長，就自行升級為 Opus。
- capability request 必須實際帶 `model: sonnet`，不得只在 prompt 中寫「請使用 Sonnet」。
- 不得啟動實作委派、不得要求 Host-specific Dynamic Workflow、不得自行往下觸發實作階段的 skill。

---

## Opus：決策、開發與修正

只有下列工作使用 `model: "opus"`：

- 已確認規格後的功能實作
- 已確認根因後的 Bug 修正
- 複雜架構決策
- 跨模組正式程式碼修改
- 高風險業務邏輯
- 複雜交易與一致性問題
- 複雜並行或非同步問題
- 安全敏感修改
- 整合多個 Sonnet Agent 的探索結果

Opus 開工前**必須先吃 Sonnet 已整理好的交接內容**，不得重做 Sonnet 已完成的大範圍探索
（重複掃 repository 是純浪費 token，也會稀釋 Opus 的注意力）。

### 探索 → 實作交接模板

Sonnet 探索完成後產出下列交接，Opus 只讀這份加上指定的設計文件：

```markdown
## 實作交接

### 相關檔案與方法
- {檔案:行號} — {是什麼}

### 呼叫關係／影響範圍
- ...

### 既有程式風格範本（片段）
- {檔案:行號}：class 宣告 + 1 個代表方法 + import 區塊

### 規格與驗收條件
- ...

### 已確認限制
- ...

### 已排除方向
- ...

### 測試方式
- {建置指令}／{測試指令}
```

---

## 角色 → 模型對照表

| 流程 | 角色 | 模型 | 可改正式程式碼 |
|------|------|------|----------------|
| `/plan` spec pass | 規格分析（`feature-spec-analyst`） | `sonnet` | ✗ |
| `/plan` db pass | DB 設計（`feature-db-designer`） | `opus` | ✗（只產 `deploy.sql` 與決策條目） |
| `/plan` arch pass | 架構設計（`feature-backend-designer`） | `opus` | ✗ |
| `/plan-build` | 探索官（專案結構、相似功能、風格範本、交叉引用） | `sonnet` | ✗ |
| `/plan-build` | DB／後端／API／前端／測試工程師（`feature-code-generator`） | `opus` | ✓ |
| `/plan-review` | Reviewer 1 邏輯正確性 | `sonnet` | ✗ |
| `/plan-review` | Reviewer 2 程式碼品質 | `sonnet` | ✗ |
| `/plan-review` | Reviewer 3 效能審查 | `opus` | ✗ |
| `/plan-review --quick` | 單一快速審查員 | `sonnet` | ✗ |
| `/plan-security` | 安全審查 | `opus` | ✗ |
| `/bug-investigate` | 證據收集、模式比對、假說驗證 | `sonnet` | ✗ |
| `/bug-investigate` | 深度根因推理（僅升級條件成立時） | `opus` | ✗ |
| `/bug-fix` | 定位、相似修正搜尋、測試範本、編譯／測試輸出分析 | `sonnet` | ✗ |
| `/bug-fix` | 修復實作者 | `opus` | ✓ |

> **為何設計類（`/plan-db`、`/plan-arch`、`/plan-security`）保留 Opus**：
> 它們雖然只產出 `.spec/` 文件、不碰正式程式碼，但內容是 DB schema／索引／交易一致性、
> 分層架構決策與安全判斷 —— 屬於本檔 Opus 清單的「複雜架構決策」與「安全敏感修改」。
> **不要因為「只產文件」就把它們降為 Sonnet**：錯誤的 schema 或分層決策會被下游 Opus
> 實作者忠實放大成整批程式碼。

### 小變更的例外（`/plan-review`）

變更範圍小、且不涉及安全、交易、並行或效能敏感區域時，三位 Reviewer 可全部使用
`model: "sonnet"`，或直接建議使用者改跑 `/plan-review --quick`。判斷依據要寫在確認畫面上。

---

## 只有兩條流程可以改正式程式碼

- `/plan-build` — 功能開發（依已確認規格）
- `/bug-fix` — Bug 修正（必須先有已確認根因）

其餘所有 skill 一律唯讀：可以寫 `.spec/`、報告、Notion 紀錄，**不可**改正式產品程式碼。

---

## Bug 調查何時可以升級 Opus

`/bug-investigate` 預設 `model: "sonnet"`，且**不得因第一次假說被否定就升級**。
只有符合下列任一條件才允許升級 Opus 做深度根因推理：

- 連續三個可驗證假說都被證據否定（`bug-investigate` 的 3-Strike）
- 問題跨越三個以上模組
- 涉及複雜並行、交易一致性、記憶體或分散式狀態
- 多份證據互相矛盾
- 一般 Sonnet 調查無法收斂
- 使用者明確要求深度分析

升級前 Sonnet 必須先整理下列交接，Opus **只針對「尚未解答的問題」推理**，不得重做全部證據收集：

```markdown
## 深度調查交接

### 已確認事實
- ...

### 已排除假說
- ...

### 相關檔案與方法
- ...

### 關鍵證據
- ...

### 尚未解答的問題
- ...
```

---

## Host-specific orchestration 是最佳化，不是流程前置

CREW 的 `feature-workflow` 與 `bug-workflow` 只依賴
`host-capabilities.md` 定義的委派語意，不依賴任何單一產品的 Team/Dynamic Workflow。

Claude Code 的 Dynamic Workflow、Subagent 或 Team 能力，以及 Codex 的 multi-agent，
都只是 capability adapter。未啟用額外平行能力時，CREW 仍必須能以序列／inline 降級完成。

Dynamic Workflow 僅適合額外用於：
- 大量檔案遷移
- 全 repository 平行稽核
- 大規模重複性檢查
- 需要可重跑 orchestration script 的工作

一般規格閱讀、功能開發與 Bug 修正不得自動要求 Dynamic Workflow。

> 這不是說「一般模式不能用 workflow」：使用者仍可在任何模式下明確要求 Dynamic Workflow，
> CREW 只是**不依賴**它 —— 沒有它，所有 skill 都要能跑完。

---

## 環境變數

- Claude Code adapter：不要用全域環境變數覆寫所有 worker 的模型選擇；若啟用其平行 Team 能力，相關環境設定只屬該 adapter。
- Codex adapter：surface 若無法精準指定 per-worker model，回報 `routing_degraded=true`，但仍遵守 role 與 write boundary。
- 任何 Host 的加速／平行設定都**不是 CREW workflow 的跨 Host 前置條件**。

---

## 相關

- `references/plan-common.md`「共用 Gotchas」（feature-workflow）— 模型參數 gotcha 的出處
- `references/host-capabilities.md` — Host adapter 與降級規則
- `scripts/lint-agent-model.py` — CI 強制檢查本檔規則（strict 模式）
