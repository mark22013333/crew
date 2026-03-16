---
name: plan-stack
description: 自動偵測或互動式建立自訂技術棧，掃描專案分層結構產生範本掃描規則，寫入設定檔。當使用者提到「plan-stack」、「自訂技術棧」、「新增技術棧」、「設定技術棧」、「tech stack」時觸發此 Skill。
---

# plan-stack — 自訂技術棧設定

自動掃描專案的分層結構，偵測各層級的 package 與命名慣例，產生範本掃描規則並寫入設定檔。

---

## 設定檔

執行前依序檢查以下路徑，讀取第一個找到的設定檔：
1. `~/.claude-company/feature-workflow-config.md`（公司環境）
2. `~/.claude/feature-workflow-config.md`（個人環境）

若都不存在，提示使用者先執行 `/plan-setup`。

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

- 若已是內建技術棧 → 提示已有內建支援，詢問是否自訂覆蓋
- 若已有自訂技術棧 → 詢問是否更新
- 若為空 → 繼續

### 2. 偵測框架資訊

掃描建置檔（pom.xml / build.gradle），擷取框架、ORM、DB。

### 3. 決定技術棧 ID

驗證：不可與內建或已有 ID 重複，格式為小寫英文 + 數字 + 連字號。

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

### 6. 寫入設定檔

更新設定檔中的「自訂技術棧」區塊和專案對應表的技術棧欄位。

### 7. 回傳結果

```
自訂技術棧設定完成！

  技術棧 ID：{id}
  層級數：{N}

現在執行 /plan-build 時會自動使用此技術棧的掃描規則。
```

---

## 邊界情況

- **設定檔不存在**：提示先執行 `/plan-setup`
- **專案不在設定檔的專案對應中**：提示先執行 `/project-add`
- **掃描不到分層結構**：進入完全手動模式
- **非 Java 專案**：Pattern 改為對應語言
- **多模組專案**：詢問要掃描哪個模組
