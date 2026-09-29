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
| 只認結構化目標，不認敘述 | 新流程 capability request 必須帶 `routing.task + profile`；尚未遷移的 call site 才直接帶 `model: opus|sonnet|haiku`。prompt 文字裡只寫模型名稱**不算** |
| 每個委派各自帶 | 多角色時每個 `delegate_readonly` / `delegate_write` 都各自帶自己的 `routing` 或 legacy `model` 目標；不可用自然語言假裝整個 team 已切模型 |
| 角色切換要拆工作單元 | 「先 Sonnet 探索、再 Opus 實作」必須是兩個 capability invocation；不可在同一個模糊工作單元裡說「中途換模型」 |
| Host 做不到就明說 | Host 若無 per-worker model selection，保留角色與權限邊界並回報 `routing_degraded=true`；**不得宣稱已套用指定模型** |
| 不許含糊 | 禁止寫「視情況選用模型」「依需求決定 model」這類沒有具體參數的措辭。條件式配置要寫清楚「什麼條件 → 哪個值」 |

正確寫法（新式 Capability request）：

```yaml
capability: delegate_readonly
role: explorer
routing:
  task: repository_search
  profile: FAST
  risk: low
  complexity: low
```

尚未遷移的高風險實作者可暫時維持：

```yaml
capability: delegate_write
role: implementer
model: opus
```

Host adapter 依 `host-capabilities.md` 執行 router；Claude 目前 FAST → haiku/low，Codex FAST → inherit/low reasoning。

---

## Provider-neutral Model Profile（權威：model-routing.json）

Workflow 先選 Profile，再由 Host adapter 對映實際模型。**Profile 是流程契約，model 名稱不是。**

| Profile | 適合工作 | Claude adapter | Codex adapter |
|---|---|---|---|
| `NONE` | Git、grep、JSON/schema validation、build/test 等 deterministic tooling | 不呼叫 LLM | 不呼叫 LLM |
| `FAST` | repository search、證據蒐集、log/test output 摘要、分類抽取 | `haiku` / low | inherit model / low reasoning |
| `STANDARD` | 需求分析、一般 review、一般實作與 debugging | `sonnet` / medium | inherit model / medium reasoning |
| `DEEP` | architecture、DB schema、security、performance、複雜根因、高風險修改 | `opus` / high | inherit model / high reasoning |

實際路由由 `scripts/crew-model-route.py` 讀取 `references/model-routing.json` 決定。Skill 不自行複製 routing table。

範例：

```bash
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-model-route.py" route \
  --task repository_search --risk low --complexity low --host portable --format json
```

路由會依 task default 再套用三種 escalation：

- `risk=medium/high` → 至少 STANDARD / DEEP
- `complexity=medium/high` → 至少 STANDARD / DEEP
- sensitive tag（security/payment/concurrency/transaction/schema migration 等）→ DEEP
- 同類工作連續失敗達門檻 → 升一級，最多 DEEP

> Host adapter 必須確認自己真的能套用 mapping。做不到 per-worker model/reasoning 時，保留 role/write boundary 並標 `routing_degraded=true`，不得假裝成功。

---

## FAST：機械型唯讀工作

下列工作優先 `profile: FAST`：

- repository 搜尋、檔案／symbol inventory
- 尋找相似功能與風格範本
- Bug 證據蒐集與既有 log / Git history 摘要
- build/test output 摘要
- 分類、抽取、格式轉換

FAST **不得**負責架構決策、正式程式碼修改或自行擴大需求範圍。需要一般推理時由 Router 升至 STANDARD；碰到 sensitive/high risk 時直接 DEEP。

---

## STANDARD：一般工程推理

需求分析、一般品質 review、routine implementation/debugging 的預設 Profile 是 `STANDARD`。
Phase 3A 為降低一次改動風險，既有正式實作者暫時仍維持 DEEP；等 D-1 加入 risk/complexity/sensitive 後，再由 Router 動態決定 STANDARD/DEEP。

---

## DEEP：複雜／高風險推理

DB schema、architecture、security、performance、複雜交易／並行、跨服務與深度根因分析固定或最低為 `DEEP`。

---

## 舊有 Claude mapping：Sonnet（STANDARD）

下列工作原本以 `model: "sonnet"` 表示；Phase 3 起應優先理解為 `profile: STANDARD`，其中純機械探索已拆到 FAST：

- 閱讀需求與規格文件
- 閱讀與整理 `.spec/` 文件
- 產出、摘要或修改技術規格
- 需要語意判斷的程式碼閱讀與跨檔推理
- 一般程式碼品質檢查
- 整理交接給實作者的上下文

執行上述工作時：

- 優先使用唯讀工具。
- **不得修改正式產品程式碼**；可以寫入 `.spec/`、報告、規格與工作紀錄。
- 不得因文件數量多或內容較長，就自行升級為 Opus。
- capability request 必須實際帶 `model: sonnet`，不得只在 prompt 中寫「請使用 Sonnet」。
- 不得啟動實作委派、不得要求 Host-specific Dynamic Workflow、不得自行往下觸發實作階段的 skill。

---

## 舊有 Claude mapping：Opus（DEEP）

下列工作以 `profile: DEEP` 為最低目標；Claude adapter 目前對映 `model: opus`：

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

| 流程 | 角色 | Profile | Claude mapping | 可改正式程式碼 |
|------|------|------|------|----------------|
| `/plan` spec pass | 規格分析（`feature-spec-analyst`） | STANDARD | sonnet | ✗ |
| `/plan` db pass | DB 設計（`feature-db-designer`） | DEEP | opus | ✗（只產 `deploy.sql` 與決策條目） |
| `/plan` arch pass | 架構設計（`feature-backend-designer`） | DEEP | opus | ✗ |
| `/plan-build` | 探索官（搜尋／範本／交叉引用） | **FAST** | haiku | ✗ |
| `/plan-build` | DB／後端／API／前端／測試工程師 | DEEP（Phase 3A 保守值） | opus | ✓ |
| `/plan-review` | Reviewer 1 邏輯正確性 | STANDARD | sonnet | ✗ |
| `/plan-review` | Reviewer 2 程式碼品質 | STANDARD | sonnet | ✗ |
| `/plan-review` | Reviewer 3 效能審查 | DEEP | opus | ✗ |
| `/plan-review --quick` | 單一快速審查員 | STANDARD | sonnet | ✗ |
| `/plan-security` | 安全審查 | DEEP | opus | ✗ |
| `/bug-investigate` | 證據收集、模式比對 | **FAST** | haiku | ✗ |
| `/bug-investigate` | 一般假說推理 | STANDARD | sonnet | ✗ |
| `/bug-investigate` | 深度根因推理（升級條件成立） | DEEP | opus | ✗ |
| `/bug-fix` | 定位、相似修正搜尋、測試輸出整理 | **FAST** | haiku | ✗ |
| `/bug-fix` | 修復實作者 | DEEP（Phase 3A 保守值） | opus | ✓ |

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

`/bug-investigate` 的證據收集預設 `profile: FAST`；一般假說推理為 STANDARD，且**不得因第一次假說被否定就升級**。
只有符合下列任一條件才允許升級 `profile: DEEP` 做深度根因推理：

- 連續三個可驗證假說都被證據否定（`bug-investigate` 的 3-Strike）
- 問題跨越三個以上模組
- 涉及複雜並行、交易一致性、記憶體或分散式狀態
- 多份證據互相矛盾
- 一般 Sonnet 調查無法收斂
- 使用者明確要求深度分析

升級前 FAST/STANDARD 工作單元必須先整理下列交接，DEEP worker **只針對「尚未解答的問題」推理**，不得重做全部證據收集：

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
