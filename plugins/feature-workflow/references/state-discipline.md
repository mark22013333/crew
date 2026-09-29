# State 斷點保險（共用紀律）

> **目的**：讓 CREW 長任務在**任何時點中斷**（crash、關機、隔天重開）時，
> 新 session 都能靠 `.spec/{slug}/state.json` 精確接手，**最多損失一個工作單元**。
> 本紀律不對抗 auto-compact、也不主動中斷 session —— 它只保證中斷發生時，狀態已經在磁碟上。

---

## 唯一寫者：`crew-state.py`

流程狀態的唯一權威是 `.spec/{slug}/state.json`，唯一寫者是
透過 `host-capabilities.md` 的 `plugin_root` 解析後執行 `scripts/crew-state.py`。**不要手寫或手改這個 JSON。**

理由有三，缺一不可：

1. **手寫會寫錯** —— 欄位名拼錯、列舉值用了未定義的字串、時間格式不一致，
   這些錯誤不會當場報錯，會在幾天後 `/plan-next` 判位錯誤時才爆出來。
2. **併發會寫壞** —— `parallel_delegate` 可能有多個 worker 同時在跑。script 用 `flock` 加鎖、
   `os.replace()` 原子寫入；手寫沒有這層保護，兩個成員同時寫就是一個半毀的 JSON。
3. **狀態要能被機器讀** —— `/plan-next`、`/plan-status` 與 SessionStart hook
   都直接讀這個檔做判斷。它是資料，不是給人看的文件。

給人看的東西（決策與理由、被否決的方案、取捨）寫在 `plan.md` 的「決策紀錄」章節，
不要塞進 state.json。

---

## Type-aware lifecycle（schema v2）

`crew-state.py` 共用同一份 runtime，但 **Feature 與 Bug 不共用同一條 phase/steps 鏈**：

```text
feature: start → spec → db → arch → build → security → verify → review → close
bug:     start → investigate → fix → close
```

- `state.json.steps` 只保留該 `type` 的有效步驟；Bug 不再出現假的 `spec/db/arch/security/review`。
- `next` 必須先看 `type` 再決定下一個 Skill；`type=bug` 不得回 `/plan spec`、`/plan-build` 等 Feature 指令。
- Bug 的編譯、測試、迴歸測試屬於 `fix` 階段的工作單元／證據，不為了套 Feature 模型而另外偽造 `verify/review` phase。
- UAT 仍是獨立 Approval Gate：Bug `fix=done` 後進 `/bug-close` 做 Human UAT；若 UAT rejected，`next` 回 `/bug-fix`。
- CLI 會拒絕跨 type 的 step/phase，例如 Bug 寫 `step=spec` 或 Feature 寫 `step=investigate`。

舊 `schema_version=1` state 由 normalize 升到 v2：Feature 保留原 lifecycle；Bug 保留 `start/close`，新增 `investigate/fix`，並可依 `work_unit.skill=bug-investigate|bug-fix` 修正 phase。舊 Feature step 不會被冒充成 Bug 進度。

---

## 觸發紀律：進度即寫

- **skill 開始執行時**：`crew-state.py set --slug {slug} --step {階段} --status in_progress`
- **每完成一個工作單元，立即**跑 `crew-state.py unit`，更新 `done`/`total`，
  把證據寫進 `evidence`、剩餘項寫進 `remaining`。
- **階段結束時**：`crew-state.py set --slug {slug} --step {階段} --status done`；
  有檢查結果的階段（verify／review／security）另跑 `crew-state.py result`。
- 禁止「等做完一批再一次補寫」—— **中斷不挑時間，事後補寫等於沒有保險。**

實際參數以 `crew-state.py <子命令> --help` 為準。

---

## 各 skill 的工作單元

| skill | 一個工作單元 = |
|-------|---------------|
| plan-build | **一個檔案**。由協調者在 role/worker 回報後寫入；worker 不碰 state.json（避免多執行單元同寫） |
| plan-review | **一位審查員的報告** |
| plan-security | **一個掃描層**（Layer 1 靜態規則／Layer 2 上下文感知／Layer 3 對抗性思維） |
| plan-verify | **一條驗收條件**（`plan.md` 的 `AC-n`） |
| bug-investigate | **一個假說的驗證結果**（確認或否定都算完成一個單元） |
| bug-fix | **一個修復步驟** —— 根因確認、程式碼修改、迴歸測試各算一個單元 |

---

## bug 型任務無 `.spec/{slug}/` 目錄時

bug 流程（`/bug-start` 建立的任務）預設不建 `.spec/` 目錄。此時**建輕量目錄，只放 state.json**
（不建 `plan.md`）。slug 取法：

1. bug 流程以 Notion「修復分支」欄位對應當前 Git branch 識別任務
   （見 bug-workflow plugin 的 `references/locate-bug.md`），沒有獨立的 slug 慣例
   → slug 用**當前 Git branch 名去掉分支前綴**（`feature/`、`fix/`、`hotfix/`）。
   例：branch `fix/push-timeout` → `.spec/push-timeout/state.json`。
2. 若 bug 任務由 `/plan-start` 建立（`.spec/{slug}/` 已存在）→ 直接沿用該目錄與 slug。

建檔用 `crew-state.py init --slug {slug} --type bug`。

---

## 斷點資訊放哪個欄位

| 要記的東西 | 欄位 | 怎麼寫 |
|-----------|------|--------|
| 目前階段與時間 | `phase`、`updated` | `set` 子命令自動維護 |
| ⚠ 歧義點與風險 | `work_unit.ambiguities` | 規格沒寫清楚之處、用保守解讀猜的決定、可能踩雷點 |
| 已完成（附證據） | `work_unit.evidence` + `steps[].commit` | 每項一句：做了什麼＋本 session 證據 |
| 進行中／未完成 | `work_unit.remaining` + `done`/`total` | 剩餘工作單元清單；做到一半的單元標注確切中斷點 |
| 接手前要準備 | `resume_hint` | branch、要啟動的服務、接手前要先讀的檔案 |
| 本階段決策紀錄 | **不放這裡** | 寫進 `plan.md`「決策紀錄」章節（`D-n [階段] 決策｜理由｜被否決方案`） |

---

## 硬規則

1. **「已完成」必附本 session 的證據**（測試輸出、檔案存在、指令結果）。
   沒有證據的項目只能留在 `remaining`，不得寫進 `evidence`。
2. **歧義點當場記**：發現的當下就寫進 `work_unit.ambiguities`，不要靠記憶等到最後補。
   `/plan-next` 會把它印在接手簡報最前面 —— 埋在別處等於沒寫。
3. **不手寫 JSON**：一律透過 `crew-state.py`。

---

## 自我修復

state.json 遺失、解析失敗、或 `schema_version` 不符時，跑：

```bash
crew-state.py rebuild --slug {slug}
```

它依「現存 state.json → git log → 檔案系統（plan.md 章節、deploy.sql）→ 無法判定則留空」
的優先序重建，並把頂層 `inferred` 設為 `true`。
`/plan-next` 看到 `inferred: true` 會加註「狀態為推測，請確認」——
**看到這個提示要人工核對一次**，不要當作正常狀態繼續跑。

---

## 生命週期

| 階段 | 動作 |
|------|------|
| `/plan-start`、`/bug-start` | `crew-state.py init` 建立 |
| skill 開始執行 | `set --status in_progress` |
| 每完成一個工作單元 | `unit`（進度即寫） |
| 階段結束 | `set --status done`（＋ `result`） |
| `/plan-close`、`/bug-close` 結案 | `set --step close --status done`，**保留檔案並入版控** |

**結案不刪除。** 舊版的 `handoff.md` 是純過程性檔案、結案即刪；`state.json` 結案後仍要留著 ——
`/plan-deploy-confirm` 事後要靠它查 `steps.close.status` 與 `deploy` 的執行進度，
刪掉就查不到「這個任務的 SQL 到底跑了沒」。
