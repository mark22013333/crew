---
type: feature
name: plan-verify 報告產出改版 — Word 驗收報告
slug: verify-word-report
status: 開發中
notion_url: https://www.notion.so/plan-verify-Word-34da401be0f58175a6c4fb447e468dd5
notion_page_id: 34da401b-e0f5-8175-a6c4-fb447e468dd5
branch:
tech_stack: spring-boot-mybatis
created: 2026-04-25
---

# plan-verify 報告產出改版 — Word 驗收報告

> **歷史 v1 規劃 artifact**：本檔保留 2026-04-25 當時的需求、status 與報告設計，不代表目前 `plan-verify` 的完整報告 contract。現行行為以 Feature Workflow README、`plan-verify` Skill 與相關 active references 為準。

## 需求描述

plan-verify 驗證完成後的報告產出改版：

1. **移除 PDF 選項**，改為只產 Word 驗證報告（使用者可自行從 Word 轉 PDF）
2. **報告需包含人話操作步驟敘述**，不是 Playwright 指令碼
3. **加入簽核欄位**（製作人 / 審核人 / 客戶確認）
4. **加入測試環境說明**（URL、瀏覽器、測試帳號、測試資料）
5. **verify.md 保留**作為技術紀錄（recheck 需要解析）
6. **詢問 Y/n** 是否產出 Word 報告，不預設直接產

### 報告定位

給客戶看的正式驗收報告，非技術人員可讀。

### 報告結構（探索階段結晶）

1. 封面（專案名稱、功能名稱、驗證日期、版本號、承辦單位）
2. 簽核欄位（製作人 / 審核人 / 客戶確認）
3. 測試環境說明（URL、瀏覽器、測試帳號角色、測試資料說明、前置條件）
4. 驗收摘要（統計表 + 一句話結論）
5. 驗收明細（每條：驗收條件 → 操作步驟 → 預期結果 → 實際結果 → 截圖）
6. 待處理事項（若有 FAIL / MANUAL）
7. 附錄（版本紀錄、工具版本、參考文件）

### 關鍵設計決策

- verify.md 是結構化技術紀錄（機器可解析），Word 是它的「人話翻譯」
- AI 在驗證時同步記錄操作敘述，不是事後從 verify.md 反推
- 封面資訊：有設定 → 自動帶入確認；沒設定 → 第一次問，存到設定檔
