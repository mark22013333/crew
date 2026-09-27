---
name: plan-security
description: 專職安全掃描 —— CREW 三層架構（靜態規則/上下文感知/對抗性思維），涵蓋 OWASP Top 10、SQLi、XSS、權限控制、敏感資料，報告全文在對話輸出、摘要一行進 plan.md。當使用者提到 /plan-security、「CREW 安全掃描」、「.spec 安全檢查」時觸發此 Skill。
argument-hint: "[--quick] [--fix]"
---

# plan-security — 安全掃描（零 Notion 呼叫）

對 plan-build 產出的程式碼執行三層安全掃描。

> **報告不落檔**：完整報告在**對話輸出**。落檔的只有 `plan.md`「檢查報告摘要」節的**一行**摘要與 `state.json` 的 `results.security`。
> 安全發現要當下處理；存成 `.spec/security.md` 只會在下次改碼後失準，還會被 `/plan-close` 原樣推上 Notion。

---

## 前置條件

> **前置檢查**：參照 plugin 根目錄 `references/prerequisites.md`（相對 SKILL.md 為 `../../references/`）檢查專案指令是否存在。

- 建議已執行 `/plan-build` 產生程式碼
- 若無 plan-build 產出，可對任何已有程式碼執行

---

## 紀律護欄

> 紀律護欄：`../../references/discipline-preamble.md`（通用紀律）＋ `../../references/anti-rationalizations.md`「plan-security 專用」＋ `../../references/boundaries.md`「plan-security」段；斷點保險改為**進度即寫 `state.json`**（`crew-state.py unit`／`result`）；有「可以跳過」「應該夠了」的衝動時，停下查表確認是否為已知偏離模式。

---

## 使用方式

```
/plan-security                # 完整三層掃描
/plan-security --quick        # 只執行 Layer 1 靜態掃描（Subagent）
/plan-security --fix          # 掃描 + 自動修復 🔴 問題
```

---

## 流程

### 1. 定位活躍任務

參照 plugin 根目錄 `references/plan-common.md`（相對 SKILL.md 為 `../../references/`）的「定位活躍任務」（`crew-state.py list`），流程位置一律以 `state.json` 為準。

### 2. 收集掃描範圍（git 是唯一事實來源）

`{prod_branch}` 從專案設定讀取；未設定時，先取 `origin/HEAD` 指向的分支，若無則依序嘗試 `production` → `master` → `main`：

```bash
git diff $(git merge-base HEAD {prod_branch})..HEAD --name-only   # 已 commit 的變更
git status --porcelain                                            # 尚未 commit 的變更
```

兩者合併去重即為掃描範圍。🔴 不要去找檔案清單文件（已廢除）。兩邊都空 → 提示使用者指定檔案，或先 `/plan-build`。

### 3. 讀取上下文

- `.spec/{slug}/plan.md` — 目標與範圍、驗收條件 `AC-n`、決策紀錄 `D-n`（權限模型、遮罩策略等安全相關決策與**被否決的方案**）、已知取捨與風險（已列為接受的風險不要再報成漏洞）、指路錨點
- `.spec/{slug}/deploy.sql` — 表結構與欄位（敏感欄位的唯一事實來源；欄位名、型別、約束都在這裡）
- `project_instructions` — 安全框架（ESAPI? Spring Security? 自訂 Filter?）

### 4. 確認執行計畫

```
即將執行安全掃描：

📁 掃描範圍：N 個檔案
🔍 掃描層級：
  • Layer 1 — 靜態規則掃描（grep + pattern matching）
  • Layer 2 — 上下文感知掃描（AI + 設計文件比對）
  • Layer 3 — 對抗性思維（三角色攻擊模擬）

確認開始？[Y/n]
```

### 5. Layer 1：靜態規則掃描（自動，無需 AI 判斷）

用 grep / find 掃描已知的危險模式：

| 規則 ID | 掃描目標 | 指令 | 嚴重度 |
|---------|---------|------|--------|
| L1-SQL-1 | MyBatis ${} 使用 | `grep -rn -F '${' --include='*.xml' --include='*.java'`（用 `-F` 做字面字串比對；原本的正規表示式寫法會轉義過度而完全匹配不到 `${}`，pattern 調整後需以測試檔實測命中） | 🔴 |
| L1-SQL-2 | 字串拼接 SQL | `grep -rn 'sql.*+=\|"SELECT.*"+\|"INSERT.*"+\|"UPDATE.*"+\|"DELETE.*"+'  --include='*.java'` | 🔴 |
| L1-XSS-1 | JSP 未轉義輸出 | `grep -rn '<%=' --include='*.jsp'` 後過濾非 JSTL 使用 | 🟡 |
| L1-XSS-2 | innerHTML / v-html | `grep -rn 'innerHTML\|v-html' --include='*.jsp' --include='*.vue' --include='*.js'` | 🟡 |
| L1-SEC-1 | 硬編碼密碼 | `grep -rn 'password\s*=\s*"\|secret\s*=\s*"\|token\s*=\s*"' --include='*.java' --include='*.properties' --include='*.yml'` | 🔴 |
| L1-SEC-2 | 缺少參數驗證 | `grep -rn '@RequestBody\|@RequestParam' --include='*.java' \| grep -v '@Valid\|@Validated'`（命中列為疑似缺驗證，需人工確認） | 🟡 |
| L1-SEC-3 | CORS 配置 | `grep -rn 'Access-Control-Allow-Origin\|@CrossOrigin\|CorsConfiguration' --include='*.java'` | 🟡 |

每條匹配結果需 AI 判斷是否為 false positive（如 ${} 在註解中、password 是欄位名不是值等）。

### 6. Layer 2：上下文感知掃描（AI 判斷，需讀設計文件）

依 `../../references/host-capabilities.md` 使用 **`delegate_readonly`**（role=`security-reviewer`、`model: opus`）：

```
你是安全工程師，負責上下文感知的安全掃描。

## 規劃文件
{plan.md 的 目標與範圍 / 驗收條件 AC-n / 決策紀錄 D-n / 已知取捨與風險}

## 表結構
{deploy.sql 全文（表、欄位、索引、約束）}

## 專案安全框架
{project_instructions 中的安全相關段落}

## 程式碼
{Layer 1 掃描過的檔案內容}

## 檢查清單

### 權限控制
- 每個 API endpoint 是否有對應的權限檢查？
- 是否有水平越權風險（A 用戶存取 B 用戶的資料）？
- 批量操作 API 是否有 Rate Limiting？

### 敏感資料
- `deploy.sql` 中屬個資／機敏性質的欄位（身分證、手機、Email、金流、密碼雜湊）在 API response 中是否遮罩？
- Log 輸出是否包含敏感資料（身分證、手機、信用卡）？
- 錯誤訊息是否洩漏內部實作細節？

### 輸入驗證
- 所有外部輸入（API 參數、查詢條件）是否有型別和範圍驗證？
- 檔案上傳是否有類型和大小限制？
- 分頁參數是否有上限（防止一次撈全表）？

### 框架正確使用
- 專案的安全框架（ESAPI/Spring Security/自訂 Filter）是否在新程式碼中正確使用？
- 新增的 Controller 是否被安全 Filter 覆蓋？
- Session 管理是否正確？

標記嚴重程度：🔴 安全漏洞 / 🟡 安全風險 / 🟢 良好
輸出使用繁體中文。
```

### 7. Layer 3：對抗性思維（AI 扮演攻擊者）

依 `../../references/host-capabilities.md` 使用 **`delegate_readonly`**（role=`security-reviewer`、`model: opus`）：

```
你是滲透測試工程師，對以下程式碼進行三角色對抗分析。

## 程式碼
{Layer 1 和 Layer 2 掃描的檔案}

## 三個角色

### 壞蛋（Scoundrel）
思考：「我怎麼濫用這個系統？」
- 設定能否關閉安全機制？
- 參數能否注入繞過驗證？
- 能否透過 API 順序漏洞執行未授權操作？
- 能否利用批量 API 進行列舉攻擊？

### 懶惰開發者（Lazy Developer）
思考：「預設行為安全嗎？」
- 預設值是否安全？零值/空值行為是否安全？
- 未初始化的狀態是否有害？
- 如果中途失敗，半完成的狀態是否安全？
- 新功能如果未設定某個 config，行為是什麼？

### 搞混開發者（Confused Developer）
思考：「如果用錯了會怎樣？」
- 參數能否交換而無型別錯誤？
- 安全檢查失敗是否被靜默忽略？
- 錯誤路徑是否洩漏資訊？
- 是否有 TOCTOU（Time-of-Check to Time-of-Use）問題？

每個發現標記嚴重程度：🔴 可利用 / 🟡 潛在風險 / 🟢 安全
輸出使用繁體中文。
```

### 8. 彙整安全報告（對話輸出，不落檔）

合併三層掃描結果，去重後**直接輸出在對話**（🔴 不寫成 `.spec/` 下的檔案）：

```markdown
# 安全掃描報告

## 摘要

| 項目 | 值 |
|------|-----|
| 掃描日期 | {YYYY-MM-DD} |
| 掃描範圍 | {N} 個檔案 |
| 模式 | {完整 / quick / fix} |

## 統計

| 層級 | 🔴 漏洞 | 🟡 風險 | 🟢 良好 |
|------|---------|---------|---------|
| Layer 1 靜態掃描 | {N} | {N} | {N} |
| Layer 2 上下文感知 | {N} | {N} | {N} |
| Layer 3 對抗性思維 | {N} | {N} | {N} |
| **合計** | **{N}** | **{N}** | **{N}** |

## 🔴 安全漏洞

### [{序號}] {漏洞標題}
- **檔案**：{路徑}:{行號}
- **層級**：Layer {1/2/3}
- **規則**：{規則 ID，如 L1-SQL-1}
- **描述**：{問題描述}
- **影響**：{攻擊場景}
- **修復建議**：{具體修復方式，含程式碼範例}
{若 --fix 模式：- **已修復**：✅ / ❌}

## 🟡 安全風險
（同上格式）

## 🟢 安全良好實踐
（正面反饋）
```

### 9. --fix 模式

掃描完成後，對所有 🔴 漏洞嘗試自動修復：

| 漏洞類型 | 自動修復策略 |
|---------|------------|
| MyBatis ${} | 替換為 #{} + 若為 ORDER BY 則加 allowlist |
| 硬編碼密碼 | 移至 .properties + 加 @Value 注入 |
| 缺少參數驗證 | 加 @Valid + 建立對應 DTO validation |
| innerHTML | 替換為 textContent 或使用 DOMPurify |

修復後重新執行 Layer 1 確認問題消除。修復動到程式碼 → 在回報中列出改了哪些檔案（`git diff --name-only`）。

### 10. 落檔的兩件事（摘要一行 + 狀態）

**10a. plan.md「檢查報告摘要」節 append 一行**

依 `references/plan-common.md`「寫入紀律」用 **Edit** 對 `<!-- crew:rep  append-only -->` 那一整行插入，格式固定：

```text
- [{YYYY-MM-DD}] security {PASS|WARN|FAIL}｜🔴{N} 🟡{N}｜{一句話結論}
```

🔴 只寫這一行：逐條發現不進 plan.md（該節上限 6 行），🔴 不得整節取代、不得動別節。
日期用 `date +%F` 的實際輸出。結論詞：無 🔴 → `PASS`；有 🟡 無 🔴 → `WARN`；有 🔴 → `FAIL`。

> 若某個 🔴 是「決定接受的風險」（例如內網環境不做 Rate Limiting），那屬於決策，
> 依寫入紀律另外 append 一條 `- D-n [security] {決策}｜理由：…｜否決：…` 到「決策紀錄」節，不要塞進摘要行。

**10b. 寫回 state.json（唯一狀態權威）**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" result --slug {slug} \
  --kind security --status {PASS|WARN|FAIL} \
  --set critical={🔴 數} --set warning={🟡 數} --set files={掃描檔案數} --set mode={full|quick|fix}
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" set --slug {slug} \
  --step security --status done --phase security
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew-state.py" validate --slug {slug} --expect-phase security
```

`validate` exit 1 → 依訊息修正後重跑；仍失敗 → `crew-state.py rebuild --slug {slug}`。

### 11. 回傳結果

```
安全掃描完成！

📋 報告：見上方對話全文（依設計不落檔）
📊 統計：🔴 {N} 漏洞 / 🟡 {N} 風險 / 🟢 {N} 良好
📝 已寫入：plan.md 摘要一行 + state.json results.security

{若有 🔴 漏洞}
⚠️  發現 {N} 個安全漏洞，強烈建議修復後再進 plan-review。
  • /plan-security --fix — 自動修復 🔴 問題

{若無 🔴 漏洞}
🎉 無嚴重安全漏洞！

後續可使用：
  • /plan-review  — 多角色程式碼審查
  • /plan-verify  — 驗收驗證
  • /plan-close   — 結案並同步 Notion
```

---

## 何時不用

本 skill 只負責對 `.spec/` 已產出程式碼做安全「掃描」，不負責實作安全功能、稽核基礎設施、審查當前分支變更或一般程式碼品質。

- 設定 Spring Security 等安全功能 → 直接開發，非掃描
- 基礎設施 / 供應鏈 / 秘密外洩稽核 → 個人 `cso` skill
- 當前分支變更安全審查 → 內建 `/security-review`
- 一般程式碼審查 → `/plan-review`

---

## Gotchas

- **Layer 1 的 grep pattern 需要持續維護**：新的危險模式（如新版 framework 的 API 變化）需要手動加入。考慮未來在 references/ 維護一份 security-patterns.md 供擴充。
- **Layer 2 和 Layer 3 分開 subagent 避免角色混淆**：合併成一個 subagent 時，「安全工程師」和「滲透測試員」的視角會互相干擾。保持分離。
- **--fix 的自動修復有限**：只處理機械性可修復的問題。涉及架構調整的問題（如缺少權限框架）只能建議，不能自動修。
- **與 plan-review Reviewer 3 的分工**：plan-security 專職安全掃描；plan-review 的 Reviewer 3 為專職效能審查，不負責安全。
- **報告不落檔是刻意的**：安全發現要當下修。存成 `.spec/security.md` 之後改一行程式就失準，還會被 `/plan-close` 原樣同步到 Notion 知識庫，把過期的漏洞清單傳播出去。
- **敏感欄位看 `deploy.sql` 不看文件敘述**：舊流程靠 `db.md` 標記敏感欄位，那是抄本、會漏。欄位清單的事實在 `deploy.sql`（與程式碼的 Entity）。

---

## 邊界情況

- **無程式碼可掃描**：提示先執行 `/plan-build` 或 commit 程式碼
- **Layer 1 結果全是 false positive**：仍需執行 Layer 2 和 Layer 3，不能因 Layer 1 雜訊而跳過
- **--quick 模式**：只執行 Layer 1 靜態掃描，適合快速檢查
- **--fix 修復失敗**：在對話報告中標記 ❌ 並寫失敗原因，摘要行結論維持 `FAIL`，不中斷流程
- **`deploy.sql` 不存在（DB_REQUIRED=false）**：跳過表結構相關檢查項，其餘照跑，報告中註明「無 DB 變更」
- **專案無安全框架**：Layer 2 的「框架正確使用」檢查項自動跳過，但在報告中標記 🟡 建議導入安全框架
