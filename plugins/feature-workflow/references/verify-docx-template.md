# verify-docx-template — python-docx 報告規格

python-docx fallback 引擎的 Word 報告產出規格。當 minimax-docx 不可用時使用。

## 報告結構（七段式，與 minimax-docx 一致）

| 段落 | 內容 | 排版 |
|------|------|------|
| 1. 封面 | 專案名稱、功能名稱、驗證日期、版本號、承辦單位 | 置中標題 + 資訊表格 |
| 2. 簽核 | 製作人、審核人、客戶確認 | 四欄表格（角色/姓名/簽章/日期） |
| 3. 測試環境 | URL、瀏覽器、模式 | 二欄表格 |
| 4. 驗收摘要 | PASS/FAIL/WARN/BLOCKED/SKIP/MANUAL 統計 + 結論 | 統計表格 + 粗體結論 |
| 5. 驗收明細 | 每條驗收項目的操作步驟、預期/實際結果、測試紀錄、截圖 | H2 標題 + 內文 |
| 6. 待處理事項 | FAIL/BLOCKED/MANUAL 項目清單 | 四欄表格 |
| 7. 附錄 | 版本紀錄、參考文件 | 表格 + 清單 |

## 字體設定

| 元素 | 西文字體 | 中文字體 | 大小 |
|------|---------|---------|------|
| 封面標題 | Calibri | 微軟正黑體 | 24pt |
| 封面副標題 | Calibri | 微軟正黑體 | 16pt |
| H1 | Calibri | 微軟正黑體 | 14pt |
| H2 | Calibri | 微軟正黑體 | 12pt |
| 內文 | Calibri | 微軟正黑體 | 10pt |
| 測試紀錄（code） | Consolas | — | 8pt |

## 表格樣式

- 表頭：深藍底（#1F4E79）白字、粗體、置中
- 資料列：左對齊、10pt
- 寬度：自動調整

## 狀態色彩

| 狀態 | 圖示 | 文字色彩 |
|------|------|---------|
| PASS | ✅ | #228B22（深綠） |
| FAIL | ❌ | #CC0000（深紅） |
| WARN | ⚠️ | #FF8C00（橘） |
| BLOCKED | 🚧 | #7030A0（紫） |
| SKIP | ⏭️ | #808080（灰） |
| MANUAL | 👤 | #1F4E79（深藍） |

## 截圖嵌入

- 寬度：5.5 inches（適合 A4 頁面留邊）
- 位置：驗收明細每條項目末尾
- 找不到檔案時：顯示「（截圖不可用：{path}）」文字，不中斷

## 敏感資訊遮蔽

與 SKILL.md 10.3 段落規則一致：
- Cookie：保留前 4 字元 + `****` + 後 4 字元
- Authorization：保留 scheme + 前 4 字元 + `****`
- API Key / Token：前 4 字元 + `****`

## 與 minimax-docx 的差異

| 功能 | minimax-docx | python-docx |
|------|-------------|-------------|
| XSD 驗證 | ✅ | ❌ |
| 精確頁面控制 | ✅ | ❌ |
| 自訂 header/footer | ✅ | ❌（使用預設） |
| 浮水印 | ✅ | ❌ |
| CJK locale 偵測 | ✅ | ❌（使用微軟正黑體） |
| 圖片尺寸自適應 | ✅ | ❌（固定 5.5in 寬） |
| 安裝成本 | .NET SDK ~500MB | python-docx ~1MB |

## CLI 介面

```bash
python3 verify-docx-generator.py \
  --verify .spec/{slug}/verify.md \
  --screenshots .spec/{slug}/screenshots/ \
  --evidence .spec/{slug}/evidence/ \
  --output .spec/{slug}/verify-report.docx \
  --cover '{"project":"...","feature":"...","author":"...","date":"...","company":"...","version":"..."}'
```

與 verify-excel-generator.js 的 --cover 參數格式一致，多了 `company` 和 `version` 欄位。
