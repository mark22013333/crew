# 範例：理想的 spec.md 產出

以下展示 `/plan-spec` 的理想產出格式，供 Agent 參考。

---

# 技術規格書：推播標籤查詢

## 功能範圍

### In Scope

- 依推播日期範圍查詢已發送的推播訊息
- 依標籤篩選推播對象
- 顯示推播統計（發送數、開封數、點擊數）
- 支援分頁與排序
- 匯出 Excel 報表

### Out of Scope

- 推播訊息的建立與編輯（已有現成功能）
- 即時推播狀態追蹤（需 WebSocket，本期不做）

## API 端點設計

| Method | Path | 說明 | 權限 |
|--------|------|------|------|
| GET | `/ap/pushTagQuery/list` | 查詢推播標籤統計列表 | 登入 |
| GET | `/ap/pushTagQuery/detail/{id}` | 查詢單筆推播詳情 | 登入 |
| GET | `/ap/pushTagQuery/export` | 匯出 Excel | 登入 |

### GET `/ap/pushTagQuery/list`

**Request Parameters:**

| 參數 | 型別 | 必填 | 說明 |
|------|------|------|------|
| startDate | String | 是 | 開始日期（yyyy-MM-dd） |
| endDate | String | 是 | 結束日期（yyyy-MM-dd） |
| tagName | String | 否 | 標籤名稱（模糊搜尋） |
| pageNum | int | 否 | 頁碼，預設 1 |
| pageSize | int | 否 | 每頁筆數，預設 20 |

**Response:**

```json
{
  "code": "0000",
  "message": "success",
  "data": {
    "list": [
      {
        "id": 123,
        "pushTitle": "水費繳納通知",
        "pushDate": "2026-03-15",
        "tagName": "水費通知",
        "totalSent": 15000,
        "totalOpened": 8500,
        "totalClicked": 3200,
        "openRate": 56.67,
        "clickRate": 21.33
      }
    ],
    "total": 45,
    "pageNum": 1,
    "pageSize": 20
  }
}
```

## 業務邏輯規則

1. **日期範圍限制**：最大查詢區間 90 天，超過回傳錯誤 `DATE_RANGE_EXCEEDED`
2. **統計計算公式**：
   - 開封率 = 開封數 / 發送數 × 100（保留兩位小數）
   - 點擊率 = 點擊數 / 發送數 × 100（保留兩位小數）
   - 發送數為 0 時，開封率和點擊率皆為 0
3. **標籤模糊搜尋**：使用 SQL `LIKE '%keyword%'`，不區分大小寫
4. **排序規則**：預設依推播日期降序；支援依發送數、開封率、點擊率排序

## 錯誤處理策略

| 錯誤碼 | HTTP Status | 說明 |
|--------|-------------|------|
| DATE_RANGE_EXCEEDED | 400 | 查詢區間超過 90 天 |
| INVALID_DATE_FORMAT | 400 | 日期格式錯誤 |
| DATA_NOT_FOUND | 200 | 查詢無資料（回傳空陣列，非錯誤） |

## 分層決策

| 層級 | 說明 |
|------|------|
| Controller | 參數接收、驗證、呼叫 Service |
| Service | 業務邏輯、統計計算、分頁處理 |
| DAO | MyBatis XML 查詢（JOIN msg_main + tag 表） |
| Entity/POJO | TagStatistics（對應查詢結果） |

## 效能需求

- 列表查詢回應時間 < 2 秒（10 萬筆推播記錄內）
- Excel 匯出支援最大 5000 筆
- 分頁使用 PageHelper

---

## 判斷

- FRONTEND_REQUIRED: false
- FRONTEND_TECH: 無
- DB_REQUIRED: true
- DB_TABLES: tag_statistics（新建）, msg_main（既有）, api_msg_main（既有）
