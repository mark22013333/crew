---
name: plan-stack
description: 自動偵測或互動式建立自訂技術棧 —— 掃描專案分層結構產生範本掃描規則，寫入設定檔。當使用者提到 /plan-stack、「自訂技術棧」、「新增掃描技術棧」時觸發此 Skill。
---

# plan-stack — 自訂技術棧設定

自動掃描專案的分層結構，偵測各層級的 package 與命名慣例，產生範本掃描規則並寫入設定檔。

---

## 設定目錄

依 plugin 根目錄 `references/config-resolver.md`（相對 SKILL.md 為 `../../references/`）的解析邏輯載入設定目錄。技術棧檔案寫入 `stacks/{id}.md`。

> **前置檢查**：參照 plugin 根目錄 `references/prerequisites.md`（相對 SKILL.md 為 `../../references/`）檢查專案指令是否存在。

---

## 參數

```
/plan-stack [技術棧 ID]
```

- 不帶參數：自動偵測後引導設定
- 帶 ID：直接使用指定 ID，跳過偵測步驟

---

## 流程

### 1. 檢查現有技術棧

- 讀取 `stacks/_builtin.md` 取得內建 ID 清單
- 檢查 `stacks/{id}.md` 是否已存在
- 若已是內建技術棧 ID → 提示已有內建支援，且**不可**用同一 ID 建立自訂檔案覆蓋（見下方「決定技術棧 ID」與 Gotchas 的一致規則）；引導改用不同的自訂 ID
- 若已有自訂技術棧檔案 → 詢問是否更新
- 若為空 → 繼續

### 2. 偵測框架資訊

> 目前範本以 Java（Maven/Gradle）專案為例；非 Java 專案請參照下方「邊界情況」改用對應語言的建置檔與 Pattern。

掃描建置檔（pom.xml / build.gradle），擷取框架、ORM、DB。

### 3. 決定技術棧 ID

驗證：**不可**與內建 ID（`spring-mvc-mybatis`、`spring-boot-mybatis`、`spring-boot-jpa`、`spring-boot-mybatis-plus`）或已有的自訂 ID 重複，格式為小寫英文 + 數字 + 連字號。此檢查為硬性擋下，不提供「覆蓋內建」的選項——原因見下方 Gotchas。

### 4. 掃描專案分層結構

掃描 `src/main/java` 下的 package 結構，辨識各層級並產生 Glob Pattern。

| 辨識規則 | 層級 |
|---------|------|
| `entity` / `model` / `pojo` / `domain` | Entity |
| `dao` / `mapper` / `repository` | Repository/Mapper |
| `mapping` + `.xml` | Mapper XML |
| `service` (無 impl) | Service |
| `service/impl` | ServiceImpl |
| `controller` / `rest` / `api` | Controller |
| `dto` / `vo` | DTO |

### 5. 展示結果並確認

展示層級表格，支援確認/編輯/取消。

### 6. 寫入技術棧檔案

建立或更新 `stacks/{id}.md`，格式參照 plugin 根目錄 `references/config.template.md`（相對 SKILL.md 為 `../../references/`）的自訂技術棧模板：

```markdown
---
id: {技術棧 ID}
framework: {框架}
orm: {ORM}
db: {DB}
scaffold: {scaffold 行為}
---

## 掃描規則

| 層級 | 說明 | Glob Pattern | 範例 Package |
|------|------|-------------|-------------|
| ... | ... | ... | ... |

## 特殊慣例

- ...
```

同時更新對應專案的 `projects/{repo-id}.md` 中的 `stack` 欄位。

### 7. 回傳結果

```
自訂技術棧設定完成！

  技術棧檔案：由 `crew-config.py resolve --key feature/stack --stack-id {id} --mode write --format path` 取得 canonical portable path（storage contract 見 `../../references/config-contract.md`）
  層級數：{N}

現在執行 /plan-build 時會自動使用此技術棧的掃描規則。
```

---

## 何時不用

- 首次整體設定 → 改用 `/plan-setup` 或 `/crew-init`
- 詢問專案用什麼技術 → 自行查看專案檔案，非本 skill 的職責
- 註冊專案 → 改用 `/project-add`

---

## Gotchas

- **自訂技術棧 ID 不可與內建 ID 重複**：內建 ID 包括 `spring-mvc-mybatis`、`spring-boot-mybatis`、`spring-boot-jpa`、`spring-boot-mybatis-plus`。依 `references/config-resolver.md` 的解析邏輯，凡專案 `stack` 欄位值屬於內建 ID，一律讀取 `stacks/_builtin.md` 中的對應區塊，**不會**去讀同名的 `stacks/{id}.md`；因此就算手動用內建 ID 建立自訂檔案，該檔案也不會被套用（不是「靜默覆蓋內建定義」，而是自訂檔案本身失效、不生效）。步驟 3 會擋下此重複，若要調整內建行為，須改用不同的自訂 ID，並更新對應專案的 `projects/{repo-id}.md` 之 `stack` 欄位指向新 ID。
- **掃描結果受 package 命名影響**：DAO 層叫 `repository` 而非 `dao` 時仍可辨識，但非標準命名（如 `persistence`、`store`）可能辨識失敗。掃描結果必須展示給使用者確認（見「展示結果並確認」一節），不可跳過。

---

## 邊界情況

- **設定目錄不存在**：提示先執行 `/plan-setup`
- **專案不在 projects/ 目錄中**：提示先執行 `/project-add`
- **掃描不到分層結構**：進入完全手動模式
- **非 Java 專案**：Pattern 改為對應語言
- **多模組專案**：詢問要掃描哪個模組
