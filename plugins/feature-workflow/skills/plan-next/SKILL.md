---
name: plan-next
description: 智慧推薦 CREW 當前任務下一步 —— 呼叫 crew-state.py 讀 state.json 算出下一個 /plan-* 指令並轉成人話。當使用者提到 /plan-next、「CREW 下一步指令」、「這個 spec 接下來做什麼」時觸發此 Skill。
argument-hint: "[<slug>] [--all]"
---

# plan-next — 智慧推薦下一步

流程位置由 `state.json`（唯一權威）決定。**本 skill 不自行推理流程**：呼叫 `crew-state.py` 拿結構化答案，只負責轉成人話並附環境提醒。

> 紀律護欄：`../../references/discipline-preamble.md`（通用紀律）＋ `../../references/anti-rationalizations.md`「plan-next 專用」＋ `../../references/boundaries.md`「plan-next」段。

> **v1 舊任務**：`.spec/{slug}/plan.md` 不存在 → 這是 v1 結構（無 `state.json`），依
> `../../references/legacy-v1.md` 的相容模式判位並提示一次。
> 過渡期限定，到期本段連同該檔一併刪除。

## 使用方式

`/plan-next`（當前活躍任務）｜`/plan-next <slug>`（指定任務）｜`/plan-next --all`（所有活躍任務）

## 流程

### 1. 定位任務

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" list --format json
```

帶 `<slug>` → 直接用。否則：`git branch --show-current` 對上某任務 slug → 自動選定；只有一個未結案任務 → 自動選定；多個 → 列出讓使用者選（**不得自行挑一個**）；空清單 → 提示 `/plan-start <任務名>`。`parked` 非 null 的任務先問是否 `/plan-status --unpark <slug>`。

### 2. 取得下一步

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" next --slug <slug> --format json
```

回傳的 `command` 與 `reason` 就是答案，照實轉述，**不得改寫或另給建議**。`command` 為 `null`（例：已結案）→ 不推薦任何指令，只轉述 `reason`。exit 1（查無任務／參數錯）→ 見 Gotchas；其他非 0 exit（例：取不到檔案鎖）→ 照 script 訊息明說「讀不到狀態」，**不要猜流程位置**。`--all` 直接用步驟 1 結果（每筆已含 `next`），不必逐一再呼叫。
接手中斷任務時，若 `.spec/<slug>/state.json` 的 `work_unit.ambiguities` 非空，把那些歧義點列在建議**之前**（中斷前留下的未決問題，先看再動手）。

### 3. 順帶提醒（獨立於主建議，最多 3 行）

| 條件 | 提醒 |
|------|------|
| `inferred` 為 `true`（狀態由 `rebuild` 推測而來） | ⚠️ 狀態為推測，請確認後再繼續 |
| 當前 branch ≠ 任務分支（唯讀取 `.spec/<slug>/state.json` 的 `resume_hint.branch`，非 null 才比） | 提示 `git checkout <branch>` |
| `AGENTS.md` / `CLAUDE.md` 都不存在 | 提示建立專案指令；Claude Code 可用 `/init` |
| 專案未在 `projects/` 註冊 | 提示 `/project-add` |

### 4. 輸出格式

一行標頭（`{name}（{slug}）｜🌿 {branch}｜📂 階段：{phase}`；`list` 沒有 branch 欄位，`{branch}` 取步驟 3 讀到的 `resume_hint.branch`，為 null 就整段省略）＋ `💡 下一步：{command}` ＋ `理由：{reason}` ＋ 順帶提醒（如有）。
`--all` 模式每任務一行 `{slug}（{phase}｜停滯 N 天）→ {command}`，不顯示順帶提醒。

## 何時不用

一般對話「接下來呢」→ 直接回答｜任務清單 → /plan-status｜規劃內容 → /plan-browse｜文件與程式碼是否同步 → /plan-drift

## Gotchas

- **狀態檔缺失或 exit 1**：不要退回「猜哪些檔案存在」。先跑 `crew-state.py rebuild --slug <slug>` 自我修復（結果會標 `inferred`），仍失敗才提示確認目錄狀態後重跑 `/plan-start <同任務簡述>`。
- **決策表不在本檔**：流程決策是 `crew-state.py next` 的 Python 實作。要改流程改那裡，**別在 SKILL.md 複製一份**（複製即漂移）。
- **bug 型任務走同一套階段機**：`next` 的決策**不看 `type`**，bug 與 feature 拿到的都是 `/plan-*` 指令（實作見 `crew-state.py` 的 `_compute_next_rule`）。`/bug-investigate`／`/bug-fix` 不在 `next` 的回傳範圍；使用者做的是 bug 調查時照 script 建議轉述並補一句說明，**不要自行改推 `/bug-*`**。
