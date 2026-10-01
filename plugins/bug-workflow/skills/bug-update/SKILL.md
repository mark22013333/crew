---
name: bug-update
description: 調查 Bug 過程中隨時將 log、SQL、判斷、截圖更新到該 Bug 的 Notion 頁面，並支援重新開啟已結案 Bug。當使用者提到 /bug-update、「更新 bug 頁面」、「補充 bug 資訊」、「reopen bug」、「bug 復發」時觸發此 Skill。
---

# bug-update — 調查過程中更新 Bug 文件 / 重新開啟已結案 Bug

在調查 Bug 期間，將關鍵 Log、SQL 查詢、初步判斷、問題描述補充等資訊，即時寫入 Notion「任務追蹤工具」的 Bug 頁面對應區塊。

也支援將已結案（測試中/已完成）的 Bug **重新開啟（reopen）**，適用於上線後發現問題未完全修復的情境。

---

## 前置條件

- 已使用 `/bug-start` 建立 Bug 條目

> **前置檢查**：參照 plugin 根目錄 `references/prerequisites.md`（相對 SKILL.md 為 `../../references/`）執行完整前置檢查（專案指令 + 設定檔 + 專案註冊）。

---

## 流程

### 0. 判斷操作模式

根據使用者輸入判斷是「一般更新」還是「重新開啟」：

- 輸入包含 `reopen`、`重新開啟`、`復發`、`退回` → **Reopen 模式**（跳至步驟 1-B）
- 其他 → **一般更新模式**（跳至步驟 1-A）

### 1-A. 定位目標 Bug 頁面（一般更新）

參照 plugin 根目錄 `references/locate-bug.md`（相對 SKILL.md 為 `../../references/`）。選定後，使用 `notion-fetch` 取得頁面完整內容，以便後續 `update_content` 操作。

定位成功後 **跳到 Step 1.5**；不要執行 1-B。1.5 recovery 完成後，一般更新模式進 Step 2。

### 1-B. 定位目標 Bug 頁面（Reopen 模式）

Reopen 模式需要定位「測試中」或「已完成」的 Bug。

**Step 1 — 解析使用者輸入**

| 使用者輸入 | 判斷 |
|-----------|------|
| 包含 Notion URL（`notion.so/` 或 `notion.site/`） | → **直接定位模式**：以 URL 中的 page_id 定位頁面 |
| 包含非 URL 文字 | → **關鍵字搜尋模式**：在「任務追蹤工具」Data Source 中搜尋「測試中」+「已完成」的 Bug，以關鍵字匹配標題 |
| 什麼都沒提供（僅 `reopen`） | → **互動式清單模式** |

**Step 2 — 互動式清單模式（無參數時）**

當使用者只輸入 `/bug-update reopen`，不帶任何參數時：

1. 從設定檔讀取「任務追蹤工具」Data Source ID（**所有查詢都用此 ID，不做全 Workspace 搜尋**）
2. 取得當前 Git Repo 識別碼，匹配設定檔中的專案
3. 使用 `notion-search` 搭配 `data_source_url: collection://{任務追蹤工具 Data Source ID}`，搜尋狀態為「測試中」或「已完成」且所屬專案匹配的 Bug（按建立時間降序，最多顯示 10 筆）
4. 若當前在修復分支上且能匹配到 Bug，將該筆標記為推薦
5. 顯示互動式清單：

```
偵測到 Git Repo：ORG01P2401/sample-app

以下為該專案近期已結案的 Bug：

1. [2026-03-15] 訂閱推播開封數欄位與點擊率公式不一致
2. [2026-03-12] customAggregationUnits 含連字號導致 LINE API 400 錯誤  ⭐ 推薦（符合當前分支）
3. [2026-03-10] 傳送數重複計算與 API 回應格式處理

請選擇要重新開啟的 Bug：
  • 輸入編號（如 1）
  • 輸入關鍵字搜尋更多
  • 貼上 Notion 頁面連結
```

6. 根據使用者回應：
   - 數字 → 選定對應的 Bug
   - Notion URL → 直接定位頁面
   - 其他文字 → 作為關鍵字重新搜尋，顯示新的結果清單

**Step 3 — 定位失敗處理**

若以上方式都找不到目標 Bug：
```
找不到符合條件的已結案 Bug，請嘗試：
  1. 貼上 Notion 頁面連結（在 Notion 找到該 Bug 頁面，複製連結）
  2. 提供更精確的關鍵字
  3. 切換到當初的修復分支後重試
```

### 1.5 Bug intake recovery preflight（一般更新 / Reopen 共用）

定位到 Notion page 後，先取得 page ID，解析：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
python3 "${CREW_PLUGIN_ROOT}/scripts/crew-state.py" list --all --format json
```

以 `state.notion.page_id == 目前 page id` 綁定 `{slug}`：

- 唯一匹配 → 若 `.spec/{slug}/.cache/intake.md` 存在，執行 `../../references/intake-refinement.md`「Bug intake recovery preflight」。
- 找到多筆 → **BLOCK**，不得猜 slug。
- 找不到 → 視為 legacy page；可繼續既有 update/reopen 流程，但不得猜不存在的 intake original。

Recovery 若需要補頁面：
- 保留既有內容，只補 intake prefix / 缺少的標準 Bug sections。
- 再次 `notion-fetch`，確認兩個 intake headings **以及五個標準 Bug sections（調查過程／根因分析／修復方案／驗證／經驗教訓）**全部存在後才刪 cache。
- recovery 失敗 → **BLOCK 本輪 mutation**，保留 cache。

完成後依模式分流：
- 一般更新 → 直接進 **Step 2**。
- Reopen → 執行下方 Reopen 操作，完成後回傳，不再進一般更新 Step 2–5。

**Reopen 模式：執行 Reopen 操作**：

1. **更新狀態**：使用 `notion-update-page` 將狀態從「測試中/已完成」改回「進行中」
2. **新增復發紀錄**：使用 `notion-update-page` 的 `update_content`，在「驗證」區塊之前插入「復發紀錄」區塊：

```
---

## 🔄 復發紀錄

### [{日期} 復發] {使用者提供的復發說明，若無則留空待補}
- **復發環境**：{若使用者有提供則填入，否則留空}
- **復發現象**：{若使用者有提供則填入，否則留空}
- **前次修復為何無效**：

---
```

3. **取消驗證勾選**：將「驗證」區塊中已勾選的項目取消勾選（改回 `- [ ]`）
4. **回傳結果**：向使用者顯示：
   - 已重新開啟的 Bug 標題與 Notion 連結
   - 目前狀態已退回「進行中」
   - 提示後續用法：
     ```
     Bug 已重新開啟，後續可使用：
     • /bug-update <調查內容>  — 補充新的調查資訊
     • /bug-close              — 二次修復完成後結案
     ```

### 2. 判斷更新類型

根據使用者輸入的內容，自動判斷應更新哪個區塊：

| 使用者輸入特徵 | 目標區塊 | 說明 |
|--------------|---------|------|
| 包含「通報」、「回報」、「反映」、機關名稱 | 問題描述 > 通報來源 | 補充通報來源 |
| 包含重現步驟描述（「先...再...然後...」） | 問題描述 > 重現步驟 | 填入具體步驟 |
| 包含「預期」、「應該」 | 問題描述 > 預期行為 | 填入預期行為 |
| 包含 log、stacktrace、Exception、ERROR | 調查過程 > 關鍵 Log | 以 code block 格式貼入 |
| 包含 SQL、select、update、insert | 調查過程 > 相關 SQL 查詢 | 以 sql code block 格式貼入 |
| 包含「判斷」、「推測」、「可能是」、「初步」 | 調查過程 > 初步判斷 | 寫入判斷內容 |
| 使用者明確指定區塊 | 指定區塊 | 依使用者指示 |

若無法自動判斷，詢問使用者要更新哪個區塊。

### 3. 支援的輸入方式

#### 方式 A：直接在指令中提供內容

```
/bug-update 關鍵 log：NullPointerException at PushService.java:235
```

其他區塊寫法同理（`通報來源：`、`初步判斷：`…），完整範例見下方「快捷用法彙整」。

#### 方式 B：從剪貼簿或終端機貼入

使用者可直接貼入多行 log 或 SQL：

```
/bug-update
```

然後 Claude Code 會詢問「請貼上要更新的內容」，使用者貼入後自動判斷類型並更新。

#### 方式 C：從檔案讀取

```
/bug-update log /opt/tomcat/logs/catalina.out
```

讀取指定 log 檔案的最後 50 行，擷取 ERROR/Exception 相關內容，寫入「關鍵 Log」。

### 4. 更新 Notion 頁面

使用 `notion-update-page` 的 `update_content` 指令：

**原則**：
- **附加而非覆蓋**：同一區塊可多次更新，每次新內容附加在既有內容之後
- **加上時間戳**：每次更新前加上 `[HH:mm]` 時間標記，方便追溯調查過程
- **格式化**：Log 用 code block、SQL 用 sql code block、一般文字用 bullet point

### 5. 回傳結果

向使用者回傳：
- 已更新的區塊名稱
- 更新內容的前 2 行預覽
- Notion 頁面連結

---

## 快捷用法彙整

### 一般更新
```
/bug-update 通報來源：公共運輸處窗口         → 更新問題描述
/bug-update 預期行為：應正常顯示使用者列表    → 更新問題描述
/bug-update 重現步驟：1.登入後台 2.點選使用者管理 3.搜尋「嵇南淩」 → 更新問題描述
/bug-update <直接貼 stacktrace>               → 更新關鍵 Log
/bug-update <直接貼 SQL>                      → 更新相關 SQL 查詢
/bug-update 初步判斷：employees 表 status=99   → 更新初步判斷
/bug-update log /path/to/catalina.out         → 從檔案擷取 ERROR 寫入關鍵 Log
```

### 重新開啟（Reopen）
```
/bug-update reopen                                        → 顯示該專案近期已結案 Bug 清單，互動式選擇
/bug-update reopen SSO登入找不到使用者                      → 用關鍵字搜尋已結案 Bug
/bug-update reopen https://www.notion.so/abe41af9...      → 直接指定 Notion 頁面連結
/bug-update reopen SSO登入 正式環境仍出現相同錯誤            → 關鍵字 + 復發說明一起提供
```

更多範例（Log 貼入、SQL 查詢記錄、初步判斷、Reopen 復發紀錄的完整輸入輸出對照）見 `examples/update-patterns.md`（相對 SKILL.md 同層目錄）。

---

## 何時不用

sync 組 —— 本 skill 只更新「單一 bug 頁面」；.spec 任務的中途同步與結案同步不在此列。

- 修完要結案 → 情境是 bug 已修復要結案，建議改用 `/bug-close`
- feature/.spec 進度中途同步 Notion → 情境是 feature/.spec 任務尚未結案的中途同步，建議改用 `/plan-sync`
- feature/.spec 任務結案同步 Notion → 情境是 feature/.spec 任務要結案，建議改用 `/plan-close`
- 只是貼 log 給你看、不需要寫入 Notion → 情境是不需要更新 Notion 頁面，建議直接貼上即可，無需本 skill
- 建立新 bug → 情境是這是一個全新的 bug、尚未建立條目，建議改用 `/bug-start`

---

## Gotchas

- **update_content 語意是覆蓋不是附加**：`notion-update-page` 的 `update_content` 對同一區塊寫入時會覆蓋該區塊內容。多次寫同一區塊時，必須先 `notion-fetch` 取得現有內容，串接新內容後再寫回，否則會覆蓋之前的調查紀錄。
- **Reopen 勾選取消格式**：checkbox 是 Notion 的 `to_do` block，用 `update_content` 改 `checked` 狀態即可；用 `replace_content` 會意外刪除使用者手動新增的內容。
- **時間戳用本地時間**：`[HH:mm]` 標記要用 24 小時制本地時區。Claude 預設 UTC，需用 `date` 指令取本地時間（如 `date +%H:%M`）再填入。

---

## 邊界情況

- **設定檔不存在**：提示使用者先執行 `/bug-setup` 完成初始設定
- **頁面內容與標準模板不符**：嘗試模糊匹配區塊標題（如「關鍵 Log」或「Log」），找不到則附加在頁面最後
- **更新內容過長（> 200 行）**：自動截斷，保留前 50 行和後 20 行，中間以 `... (省略 N 行) ...` 替代
- **多次更新同一區塊**：新內容附加在既有內容之後，以時間戳區隔
- **Reopen 已完成的 Bug**：保留原有的根因分析與修復方案（不覆蓋），新增「復發紀錄」區塊記錄新一輪調查
- **多次復發**：每次 reopen 在「復發紀錄」區塊下新增一個子區塊，以日期區隔，完整保留所有歷程
- **Reopen 找不到目標**：顯示三種補救方式（Notion 連結 / 關鍵字 / 切換分支）
- **Reopen 互動清單為空**：該專案沒有已結案 Bug，提示確認專案是否正確或改用關鍵字/Notion 連結
- **Reopen 清單輸入 Notion URL**：直接切換為 URL 定位模式，不再搜尋
