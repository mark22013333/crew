# v1 `.spec/` 相容層（過渡期專用）

> **Retirement contract（AC-31）**
>
> - 過渡期起點：`feature-workflow@5.0.0`，發布日 `2026-07-28`。
> - Removal eligibility：**第一個 `feature-workflow@5.1.0`（或更高版本）發布，或 `2026-10-26`（5.0.0 發布後 90 天），以先到者為準。**
> - 在上述任一門檻到達前，**不得**刪除本檔、各 Skill 的 v1 分支、`/plan-status --migrate` 或 crew-doctor 的 v1 偵測。
> - 到達門檻只代表「可以開始清理」，**不代表自動刪除**；實際移除仍必須以單一、可驗證的 cleanup batch 完成。
>
> 本檔集中放 v1 的相容邏輯，讓各 skill 用**一行引用**分支，不要每個 skill 各留一份副本
> —— 那會讓過渡期結束時清不乾淨，v1 邏輯永遠留在 repo 裡。

---

## 判定鍵

```
.spec/{slug}/plan.md 存在 → v2（新結構）
否則                      → v1（舊結構）
```

只看這一個檔。不要用 `README.md` 是否存在來判定（v2 任務也可能因為別的原因有 README）。

---

## v1 與 v2 的對照

| v1 | v2 |
|----|-----|
| `README.md`（frontmatter 含 `status`／`branch`／`notion_*`） | `plan.md` frontmatter（只留身分與漂移欄位）＋ `state.json` |
| `spec.md` | `plan.md`「目標與範圍」「驗收條件」＋`[spec]` 決策條目 |
| `db.md`、`db.sql` | `deploy.sql`（唯一 SQL 事實來源）＋`[db]` 決策條目 |
| `arch.md` | `[arch]` 決策條目＋「指路」節的 `@code:` 錨點 |
| `files.md` | 不再產出，改用 `git diff --name-only` |
| `deploy-checklist.md` | `state.json` 的 `deploy` 欄位 |
| `log.md` | `state.json` 的 `history`（有上限） |
| `handoff.md` | `state.json`（結案**保留**，不像 handoff 結案即刪） |
| `review.md`、`security.md` | 不落檔；摘要一行進「檢查報告摘要」 |
| `verify.md` | `.cache/verify.md`（一次性暫存，gitignore） |
| `.spec/_index.md` | 廢除；即時掃 `.spec/*/state.json` |

---

## 兩條路怎麼選

### A. 舊任務照舊跑完（預設，推薦）

**適合**：任務已經跑到 build 之後，只差 verify／review／close。

v1 任務**不要中途換軌** —— 遷移只搬得動結構，搬不動語意，中途換軌會讓你在收尾階段
面對一份半空的 `plan.md`。讓它用 v1 的方式跑完，結案後自然淘汰。

skill 遇到 v1 任務時的行為：
1. 開頭提示一次「這是 v1 任務，將以相容模式執行；移除門檻為 feature-workflow@5.1.0 發布或 2026-10-26，以先到者為準」
2. 讀寫沿用 v1 檔案（`spec.md`／`arch.md`／`README.md` frontmatter 的 `status`）
3. **不呼叫 `crew-state.py`**（v1 沒有 `state.json`），也不做漂移檢查（v1 沒有錨點）
4. `plan-close` 對 v1 任務跳過漂移硬關卡，但要在回報中明寫「v1 任務，未做漂移檢查」

### B. 主動遷移（`/plan-status --migrate {slug}`）

**適合**：任務還在早期（規劃階段、尚未大量產碼），或你打算長期維護這份文件。

遷移只做**機械搬移**，語意內容留佔位由人補。詳見 `plan-status` 的 `--migrate` 一節。

---

## 為什麼不做自動語意轉換

把 425 行的 `spec.md` 壓成 80 行的 `plan.md` 看起來很適合交給 LLM，但：

1. **不可驗證** —— 沒有任何檢查能判斷「這份摘要有沒有漏掉關鍵決策」。
2. **會幻覺出從未做過的決策** —— 壓縮就是取捨，LLM 取捨時會補上看似合理、實際上
   當初根本沒討論過的理由。這些假決策會被後人當成史實引用。
3. **錯了沒人發現** —— 原文被搬進 `archive/` 之後不會有人再去對照。

所以：**結構自動搬、語意人工補**。`plan.md` 的內容章節留 `TODO(migrate)` 佔位，
archive 的原文一個字都不改，你自己看著補。補不完也沒關係 —— 一份誠實的空白，
比一份看似完整的幻覺有用。

---

## Removal eligibility 與到期清理清單

### 先判斷是否有資格移除

只有以下任一條件成立，才可開始 cleanup：

1. Feature workflow 已發布 `5.1.0` 或更高版本；**或**
2. 日期已到 `2026-10-26` 或之後。

兩者都未成立 → **停止，不得移除任何 v1 compatibility surface**。

> 目前 contract 的基準是 `5.0.0 / 2026-07-28`；90 天日期固定為 `2026-10-26`。
> CI 的 `scripts/lint-state-writers.py --strict` 會在 removal eligibility 尚未成立時，阻擋提前刪除核心相容入口。

### 門檻到達後，一個 cleanup batch 一次完成

1. 刪除本檔 `references/legacy-v1.md`。
2. 刪除各 Skill 的「v1 分支」引用段（用 `grep legacy-v1.md` / code search 找齊）。
3. 刪除 `plan-status` 的 `--migrate` 使用方式與「遷移模式」整段。
4. 刪除 `crew-doctor` 的「v1 舊結構任務」檢查項，並同步必要／建議／選配／進階與總項數等相關計數文字。
5. 從 `scripts/lint-state-writers.py` 移除 v1 過渡期專用 EXEMPTIONS 與 retirement-presence guard；保留一般 state single-writer lint。
6. 更新 root / feature-workflow README 中仍指向 `legacy-v1.md` 或 `--migrate` 的現行使用說明，避免 dead link；歷史 CHANGELOG/ADR 可保留歷史事實，但不得再宣稱目前仍支援。
7. 跑完整 CI，確認沒有 dangling reference、skill contract / README sync / state writer / portability regression。

**禁止分批刪一半。** eligibility 到達前不得提前移除；到達後若決定退休，應以同一 cleanup batch 收斂，避免「文件說已刪、入口仍存在」或相反狀態。
