# Agent Team Review Prompt 模板

> 此檔案由 plan-review 步驟 5「完整多角色審查」按需載入。
> 模板中的 `{slug}` 需替換為實際值。
> `{檔案清單}` 一律由 `git diff --name-only <base>...HEAD` 取得（三點語法自動以 merge-base 為起點；`<base>` 讀 `.spec/{slug}/state.json` 的 `git.base`，缺值時用專案正式分支）——
> **審查範圍以 git 為唯一事實來源**，不再讀任何「本次改了哪些檔」的清單檔（那種清單一寫下去就開始漂移）。

## 模型配置（硬性）

| Reviewer | 參數 | 理由 |
|----------|------|------|
| 1 邏輯正確性 | `model: sonnet` | 規格符合度與一般邏輯檢查 |
| 2 程式碼品質 | `model: sonnet` | 風格與一般品質檢查 |
| 3 效能審查 | `model: opus` | 效能／交易／並行屬高風險判斷 |

三者都使用 `delegate_readonly`；Host 支援時可包成 `parallel_delegate`。每個 role 的模型目標以結構化參數傳入（`model: sonnet` / `model: opus`）。
🔴 不可只在 prompt 文字裡寫「使用 Opus 模型」——那不是參數，不保證生效（見共用 reference `model-policy.md`）。

小變更且不涉及安全／交易／並行／效能敏感區域時，三者可全部用 `model: sonnet`，或直接建議改跑 `--quick`。

## 完整審查（parallel_delegate 優先）

建立 3 個 Reviewer capability request（一個角色一次 `delegate_readonly`，各自帶 `model: sonnet` 或 `model: opus`）：

```
Code Review 分工，建立 3 個 Reviewer role（Host 支援時平行；每個 request 帶 role 與 model）：

【Reviewer 1：邏輯正確性】Logic Reviewer
- 讀取 `project_instructions` 了解架構慣例
- 讀取 .spec/{slug}/plan.md：目標與範圍、驗收條件（`AC-n`）、決策紀錄（`[spec]`／`[arch]` 條目）、已知取捨與風險
  * 指路節的 `@code:` 錨點指到哪，就 Read 哪個檔案的哪個符號
  * 「已知取捨與風險」列出的技術債**不算發現**，不要重複回報
- 若 .spec/{slug}/.cache/verify.md 存在：
  * 讀取驗證結果，關注 ❌ FAIL 項目
  * 檢查失敗原因是否對應到程式碼問題
  * 審查報告中引用驗證結果作為佐證
- 讀取本次新增/修改的所有程式碼檔案：
  {檔案清單}
- 檢查：
  * API 參數驗證是否完整
  * 業務邏輯是否符合規格
  * 查詢條件是否正確
  * 例外處理是否恰當
  * 邊界條件是否考慮
  * 回傳格式是否一致
- 標記嚴重程度：🔴 嚴重 / 🟡 建議 / 🟢 良好
- spawn 參數：name=logic-reviewer、model: sonnet
- 使用繁體中文

【Reviewer 2：程式碼品質】Quality Reviewer
- 掃描專案中 2-3 個同類型的現有檔案作為風格基準
- 讀取本次新增/修改的所有程式碼檔案：
  {檔案清單}
- 檢查：
  * 程式碼風格、命名規範是否與專案一致
  * package 結構和 import 順序
  * Lombok 使用方式
  * 註解風格和位置
  * Error handling 是否完善
  * 有沒有 edge case 沒處理（空數據、數據不足等）
- 標記：🟡 不一致 / 🟢 一致
- spawn 參數：name=quality-reviewer、model: sonnet
- 使用繁體中文

【Reviewer 3：效能審查】Performance Reviewer
- 讀取 `project_instructions` 了解效能相關配置
- 讀取 .spec/{slug}/deploy.sql 了解表結構與索引（唯一 SQL 事實來源），
  並讀 .spec/{slug}/plan.md 的 `[db]` 決策條目了解索引／正規化的取捨理由
- 讀取本次新增/修改的所有程式碼檔案：
  {檔案清單}
- 效能檢查：
  * N+1 查詢
  * 缺少分頁
  * 缺少索引
  * 迴圈內 DB 呼叫
  * 大量資料未串流
  * 潛在的效能問題（大數據量回測）
  * 查詢執行計畫分析（若 DB MCP 可用）
  * 效能指標預估（回應時間、吞吐量）
  * 快取策略建議
  * 連線池配置
- 標記：🔴 效能瓶頸 / 🟡 效能風險 / 🟢 良好
- spawn 參數：name=performance-reviewer、model: opus
- 使用繁體中文

三位 Reviewer 完成後請互相分享各自的發現，
看看有沒有交叉觀點或遺漏（如邏輯問題可能導致安全風險），
最後由 Lead 彙整產出完整的 Review Report。

請使用 delegate mode，Lead 只負責協調，不要自己寫 code。
所有輸出使用繁體中文。
```
