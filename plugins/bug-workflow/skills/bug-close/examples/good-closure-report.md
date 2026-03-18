# 結案報告範例 — 理想的品質標準

以下是一個高品質的 bug-close 產出範例，展示每個區塊應有的深度和格式。

---

## 🧠 根因分析

- **問題根因**：`PushBySchedule.aggregateMessageStatistics()` 在統計訂閱推播的開封數時，使用了 `clickCount` 欄位而非 `uniqueImpressionCount`，導致開封數實際上是點擊數。LINE Messaging API 的 `getNumberOfMessageDeliveries` 回傳的 JSON 中，`click` 和 `uniqueImpression` 是獨立欄位，但程式碼在 mapping 時對調了。
- **問題檔案**：`src/main/java/com/xtremeapp/linebc/schedule/AggregationMessageStatisticsSchedule.java:127`
- **問題程式碼**：
```java
// 錯誤：用了 clickCount 作為開封數
stats.setOpenCount(response.getClickCount());
```

> **重點**：根因分析要精確到行號和具體欄位，不能只寫「mapping 錯誤」。要讓第二個人讀了就知道哪裡錯、為什麼錯。

---

## ✅ 修復方案

- **修改檔案清單**：
  - `AggregationMessageStatisticsSchedule.java` — 修正開封數欄位 mapping
  - `AnalysisService.java` — 調整點擊率公式使用正確分母

- **修改說明**：
  - **排程層**：將 `setOpenCount()` 的參數從 `getClickCount()` 改為 `getUniqueImpressionCount()`
  - **Service 層**：點擊率公式從 `clickCount / openCount` 改為 `clickCount / uniqueImpressionCount`，避免分母為零時 ArithmeticException

- **修改後程式碼**：
```java
// 修正：使用 uniqueImpressionCount 作為開封數
stats.setOpenCount(response.getUniqueImpressionCount());
```

- **修復 Commit**：`3698ca66 fix(analysis): 修正訂閱推播開封數欄位與點擊率公式不一致`
- **修復分支**：`feature/push-tag-query`

> **重點**：修改說明要按架構分層描述（Controller / Service / DAO），不要只列檔名。關鍵程式碼只貼核心修改（≤ 50 行），不貼 import 或格式變更。

---

## 知識庫同步範例

對應的 Bug 知識庫條目應該是精簡版：

```
**根因**：排程統計開封數時使用了 LINE API 回傳的 clickCount 而非 uniqueImpressionCount

**解法**：修正 AggregationMessageStatisticsSchedule 的欄位 mapping，同步修正 AnalysisService 的點擊率公式

**關鍵程式碼**：
- 開封數：`getUniqueImpressionCount()`（非 `getClickCount()`）
- 點擊率：`clickCount / uniqueImpressionCount`
```

> 知識庫條目的目標是讓未來搜尋到的人「30 秒內理解問題和解法」，不需要完整的 diff。
