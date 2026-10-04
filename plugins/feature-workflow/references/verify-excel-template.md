# Excel 驗收報告規格

定義 verify-excel-generator.js 的產出規格，從 verify.md + screenshots/ + evidence/ 產出 .xlsx 檔案。

---

## 總覽

| 項目 | 說明 |
|------|------|
| 輸入 | verify.md + screenshots/ + evidence/ |
| 輸出 | .xlsx（Excel 驗收報告） |
| 函式庫 | ExcelJS |
| 呼叫方式 | `node verify-excel-generator.js --verify {path} --screenshots {dir} --evidence {dir} --output {path} --cover '{"project":"...","feature":"...","author":"...","date":"..."}'` |

### Sheet 結構

| Sheet | 名稱 | 內容 |
|-------|------|------|
| 1 | 驗收總表 | 總覽 + 明細 + 簽核區 |
| 2~N | 項目 1, 項目 2, ... | 各驗收項目的步驟與截圖 |

---

## Sheet 1: 驗收總表

### 標題區

| 儲存格 | 格式 |
|--------|------|
| A1:F1（合併） | 深藍背景 `#FF1F4E79`，白字，16pt bold |
| 內容 | `{專案名稱} — {功能名稱} 驗收報告` |

### 資訊區（A3:B8）

| 列 | A 欄（項目） | B 欄（值） |
|----|------------|-----------|
| 3 | 驗證日期 | from verify.md 摘要 |
| 4 | 驗測人員 | from `--cover` 參數 |
| 5 | 測試環境 | from verify.md 摘要 |
| 6 | 測試語系 | 偵測或指定 |
| 7 | 驗測工具 | from verify.md 摘要 |
| 8 | Health Score | from verify.md 摘要 |

### 明細表（A10 起）

#### 欄位定義

| 欄位 | 寬度(char) | 對齊 |
|------|-----------|------|
| # | 6 | center |
| 驗收條件 | 40 | left |
| 結果 | 10 | center |
| 截圖 | 12 | center |
| 備註 | 30 | left |
| 測試日期 | 14 | center |

#### 結果欄背景色

| 結果 | 背景色 | 色碼 |
|------|--------|------|
| PASS | 淺綠 | `#FFE2EFDA` |
| FAIL | 淺紅 | `#FFFCE4D6` |
| WARN | 淺黃 | `#FFFFF2CC` |
| BLOCKED | 淺紫 | `#FFEADCF8` |
| SKIP | 淺灰 | `#FFF2F2F2` |
| MANUAL | 淺藍 | `#FFDCE6F1` |

#### 截圖欄

超連結到對應步驟 Sheet：

```
# 超連結格式
hyperlink: "#'項目 1'!A1"
text: "查看步驟"
style: { font: { color: { argb: 'FF0563C1' }, underline: true } }
```

### 簽核區

明細表下方空 2 行後，加入簽核表格：

| 角色 | 姓名 | 簽章 | 日期 |
|------|------|------|------|
| 製作人 | {author} | | |
| 審核人 | | | |
| 客戶確認 | | | |

### 凍結窗格

凍結明細表標題列（Row 10），捲動時標題列固定可見。

```javascript
worksheet.views = [{ state: 'frozen', ySplit: 10 }];
```

---

## Sheet 2~N: 各驗收項目步驟

每個驗收條件對應一個獨立 Sheet。

### Sheet 命名

格式：`項目 {N}`（如「項目 1」「項目 2」...）

> **注意**：Sheet 名稱不超過 31 字元（Excel 限制）。

### 佈局結構

| 列 | 內容 | 格式 |
|----|------|------|
| Row 1 | 驗收條件名稱 | bold, 14pt |
| Row 2 | 結果（PASS/FAIL/WARN/BLOCKED/SKIP/MANUAL） | 帶色彩（同明細表結果欄背景色） |
| Row 3 | 空行 | — |
| Row 4+ | 操作步驟 | 見下方 |

### 操作步驟區（Row 4+）

從 verify.md 的 `human_steps` 擷取，格式：

```
步驟 1: {操作描述}
  預期結果: {expected}
  實際結果: {actual}
  [截圖嵌入]

步驟 2: {操作描述}
  預期結果: {expected}
  實際結果: {actual}
  [截圖嵌入]
```

### 截圖嵌入規則

| 項目 | 規則 |
|------|------|
| 格式 | PNG |
| 尺寸偵測 | 讀取 PNG header bytes 16-23 取得原始 width/height |
| 縮放 | target width = 800px，保持原始比例 |
| 嵌入方式 | `worksheet.addImage({ imageId, tl, ext })` |

```javascript
// PNG 尺寸偵測
const buffer = fs.readFileSync(imagePath);
const width = buffer.readUInt32BE(16);
const height = buffer.readUInt32BE(20);

// 縮放計算
const targetWidth = 800;
const scale = targetWidth / width;
const targetHeight = Math.round(height * scale);

// 嵌入
const imageId = workbook.addImage({ filename: imagePath, extension: 'png' });
worksheet.addImage(imageId, {
  tl: { col: 0, row: currentRow },
  ext: { width: targetWidth, height: targetHeight }
});
```

### API 測試紀錄

若 verify.md 中有 evidence 區塊（API 呼叫紀錄），嵌入步驟區下方：

#### 請求區塊

```
請求: {HTTP_METHOD} {URL}
Headers:
  Content-Type: application/json
  Authorization: Bearer eyJh****        ← 已遮罩
  Cookie: JSES****f456                   ← 已遮罩
```

#### 回應區塊

```
回應: HTTP {status_code}
{回應摘要}
```

> **長回應處理**：超過 20 行時，顯示首 10 行 + `... (省略 {N} 行) ...` + 末 10 行。

### 底部導航

每個步驟 Sheet 底部加入超連結回 Sheet 1：

```
hyperlink: "#'驗收總表'!A1"
text: "← 回到驗收總表"
style: { font: { color: { argb: 'FF0563C1' }, underline: true } }
```

---

## 敏感資訊遮罩規則

API 測試紀錄中的 Header 值必須遮罩處理：

| Header | 遮罩方法 | 原始值範例 | 遮罩後 |
|--------|---------|-----------|--------|
| Cookie | 保留前 4 + `****` + 後 4 | JSESSIONID=abc123f456 | JSES****f456 |
| Authorization | Scheme + 前 4 + `****` | Bearer eyJhbGciOiJIUz... | Bearer eyJh**** |
| X-API-Key | 前 4 + `****` | sk-live-abcdef123456 | sk-l**** |
| X-Token | 前 4 + `****` | tok_abc123def456 | tok_**** |

### 遮罩邏輯

```javascript
function maskHeader(name, value) {
  const lower = name.toLowerCase();
  if (lower === 'authorization') {
    const parts = value.split(' ');
    if (parts.length === 2) {
      return `${parts[0]} ${parts[1].substring(0, 4)}****`;
    }
    return value.substring(0, 4) + '****';
  }
  if (['cookie', 'x-api-key', 'x-token', 'x-access-token'].includes(lower)) {
    if (value.length <= 8) return '****';
    return value.substring(0, 4) + '****' + value.substring(value.length - 4);
  }
  return value;
}
```

---

## 全域樣式定義

### 字型

| 項目 | 值 |
|------|-----|
| 字型家族 | 微軟正黑體（Microsoft JhengHei） |
| 標題字級 | 14-16pt |
| 內文字級 | 10-11pt |
| 標題粗體 | bold |

### 邊框

```javascript
const thinBorder = {
  top:    { style: 'hair' },
  left:   { style: 'hair' },
  bottom: { style: 'hair' },
  right:  { style: 'hair' }
};
```

### 對齊

| 區域 | 水平對齊 | 垂直對齊 | 自動換行 |
|------|---------|---------|---------|
| 表頭 | center | middle | false |
| 文字內容 | left | top | true |
| 數字/日期 | center | middle | false |
| 結果欄 | center | middle | false |

### 行高

| 區域 | 行高 |
|------|------|
| 最小行高 | 22px |
| 步驟區每行 | 基礎 22px + 16px |
| 截圖行 | 依圖片高度動態計算 |

### 色彩常數

```javascript
const COLORS = {
  HEADER_BG:   'FF1F4E79',  // 深藍（標題背景）
  HEADER_FG:   'FFFFFFFF',  // 白色（標題文字）
  PASS_BG:     'FFE2EFDA',  // 淺綠
  FAIL_BG:     'FFFCE4D6',  // 淺紅
  WARN_BG:     'FFFFF2CC',  // 淺黃
  BLOCKED_BG:  'FFEADCF8',  // 淺紫
  SKIP_BG:     'FFF2F2F2',  // 淺灰
  MANUAL_BG:   'FFDCE6F1',  // 淺藍
  LINK_COLOR:  'FF0563C1',  // 超連結藍
  INFO_LABEL:  'FFD6DCE4',  // 資訊區標籤背景
};
```
