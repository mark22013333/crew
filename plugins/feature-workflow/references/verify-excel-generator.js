#!/usr/bin/env node
'use strict';

/**
 * verify-excel-generator.js
 *
 * 將 verify.md 驗證報告轉換為格式化的 .xlsx 驗收報告。
 *
 * 使用方式：
 *   NPM_TMP=$(mktemp -d) && npm install --prefix "$NPM_TMP" exceljs --no-save --silent \
 *     && NODE_PATH="$NPM_TMP/node_modules" node verify-excel-generator.js \
 *     --verify .spec/{slug}/verify.md \
 *     --screenshots .spec/{slug}/screenshots/ \
 *     --evidence .spec/{slug}/evidence/ \
 *     --output .spec/{slug}/verify-report.xlsx \
 *     --cover '{"project":"SmartRobot","feature":"推播統計","author":"Cheng","date":"2026-05-15"}'
 *
 * 依賴：exceljs（exceljs 無 bin 欄位，不可用 npx 直接執行；需 npm install 後透過 NODE_PATH 注入，或全域安裝）
 */

let ExcelJS;
try {
  ExcelJS = require('exceljs');
} catch {
  console.error('請先執行: npm install --prefix <臨時目錄> exceljs --no-save，並設定 NODE_PATH 指向該目錄的 node_modules，或 npm install -g exceljs');
  process.exit(1);
}

const fs = require('fs');
const path = require('path');

// ============================================================
// 色彩定義
// ============================================================

const STATUS_COLORS = {
  PASS:   { bg: 'FFE2EFDA', text: '✅ 通過' },
  FAIL:   { bg: 'FFFCE4D6', text: '❌ 未通過' },
  WARN:   { bg: 'FFFFF2CC', text: '⚠️ 警告' },
  BLOCKED:{ bg: 'FFEADCF8', text: '🚧 前置阻擋' },
  SKIP:   { bg: 'FFF2F2F2', text: '⏭️ 略過' },
  MANUAL: { bg: 'FFDCE6F1', text: '👤 待人工確認' },
};

const BLUE_DARK  = 'FF1F4E79';
const BLUE_MID   = 'FF2E75B6';
const BLUE_LIGHT = 'FFD6E4F0';

// ============================================================
// CLI 參數解析
// ============================================================

function parseArgs() {
  const args = process.argv.slice(2);
  const parsed = {
    verify: null,
    screenshots: null,
    evidence: null,
    output: null,
    cover: {},
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--verify':
        parsed.verify = args[++i];
        break;
      case '--screenshots':
        parsed.screenshots = args[++i];
        break;
      case '--evidence':
        parsed.evidence = args[++i];
        break;
      case '--output':
        parsed.output = args[++i];
        break;
      case '--cover':
        try {
          parsed.cover = JSON.parse(args[++i]);
        } catch (e) {
          console.error('❌ --cover 參數 JSON 解析失敗:', e.message);
          process.exit(1);
        }
        break;
      default:
        console.error(`⚠️  未知參數: ${args[i]}`);
    }
  }

  if (!parsed.verify) {
    console.error('❌ 必須指定 --verify 參數（verify.md 路徑）');
    process.exit(1);
  }
  if (!parsed.output) {
    console.error('❌ 必須指定 --output 參數（輸出 .xlsx 路徑）');
    process.exit(1);
  }

  return parsed;
}

// ============================================================
// verify.md 解析
// ============================================================

/**
 * 從 emoji 推斷狀態代碼
 */
function emojiToStatus(emoji) {
  if (emoji.includes('✅')) return 'PASS';
  if (emoji.includes('❌')) return 'FAIL';
  if (emoji.includes('⚠️') || emoji.includes('⚠')) return 'WARN';
  if (emoji.includes('🚧')) return 'BLOCKED';
  if (emoji.includes('⏭️') || emoji.includes('⏭')) return 'SKIP';
  if (emoji.includes('👤')) return 'MANUAL';
  return 'SKIP';
}

/**
 * 解析 <!-- human_steps ... --> 註解區塊
 * 回傳 { action, expected, actual } 陣列
 */
function parseHumanSteps(block) {
  const steps = [];
  const lines = block.split('\n');

  let current = null;
  for (const line of lines) {
    const trimmed = line.trim();
    // 格式：- 操作：...  / - 預期：... / - 實際：...
    const opMatch = trimmed.match(/^-\s*操作[：:]\s*(.+)/);
    const expMatch = trimmed.match(/^-\s*預期[：:]\s*(.+)/);
    const actMatch = trimmed.match(/^-\s*實際[：:]\s*(.+)/);

    if (opMatch) {
      if (current) steps.push(current);
      current = { action: opMatch[1].trim(), expected: '', actual: '' };
    } else if (expMatch && current) {
      current.expected = expMatch[1].trim();
    } else if (actMatch && current) {
      current.actual = actMatch[1].trim();
    }
  }
  if (current) steps.push(current);

  return steps;
}

/**
 * 解析 <!-- evidence ... --> 註解區塊
 * 回傳 { request, responseStatus, responseFile, responseLines }
 */
function parseEvidence(block) {
  const evidence = {
    request: null,
    responseStatus: null,
    responseFile: null,
    responseLines: null,
  };

  // 解析簡易 YAML 風格
  const lines = block.split('\n');
  let inRequest = false;
  let requestLines = [];

  for (const line of lines) {
    const trimmed = line.trim();

    // request: | 多行模式
    if (/^request:\s*\|/.test(trimmed)) {
      inRequest = true;
      continue;
    }
    // request: 單行
    if (/^request:\s*(?!\|)(.+)/.test(trimmed)) {
      const m = trimmed.match(/^request:\s*(.+)/);
      evidence.request = m[1].trim();
      inRequest = false;
      continue;
    }

    if (inRequest) {
      // 多行結束條件：遇到非縮排行且包含已知 key
      if (/^(response_status|response_file|response_lines):/.test(trimmed)) {
        inRequest = false;
        evidence.request = requestLines.join('\n').trim();
        // 繼續解析這行（fall through）
      } else {
        requestLines.push(line.replace(/^\s{2}/, ''));
        continue;
      }
    }

    const statusMatch = trimmed.match(/^response_status:\s*(\d+)/);
    if (statusMatch) {
      evidence.responseStatus = parseInt(statusMatch[1], 10);
      continue;
    }

    const fileMatch = trimmed.match(/^response_file:\s*(.+)/);
    if (fileMatch) {
      evidence.responseFile = fileMatch[1].trim();
      continue;
    }

    const linesMatch = trimmed.match(/^response_lines:\s*(\d+)/);
    if (linesMatch) {
      evidence.responseLines = parseInt(linesMatch[1], 10);
      continue;
    }
  }

  // 如果還在收集 request 行
  if (inRequest && requestLines.length > 0) {
    evidence.request = requestLines.join('\n').trim();
  }

  // 若所有欄位都是 null，表示無有效 evidence
  if (!evidence.request && !evidence.responseStatus && !evidence.responseFile) {
    return null;
  }

  return evidence;
}

/**
 * 解析 verify.md 主函式
 */
function parseVerifyMd(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  const lines = content.split('\n');

  const result = {
    summary: { date: '', environment: '', mode: '', tool: '', locale: '' },
    stats: { pass: 0, fail: 0, warn: 0, blocked: 0, skip: 0, manual: 0 },
    items: [],
  };

  // --- 1. 解析摘要表格 ---
  const summaryTableStart = lines.findIndex(l => /^##\s*摘要/.test(l.trim()));
  if (summaryTableStart !== -1) {
    for (let i = summaryTableStart + 1; i < lines.length && !lines[i].startsWith('## '); i++) {
      const row = lines[i].trim();
      if (!row.startsWith('|') || row.startsWith('|--') || row.startsWith('| 項目')) continue;
      const cells = row.split('|').map(c => c.trim()).filter(Boolean);
      if (cells.length >= 2) {
        const key = cells[0];
        const val = cells[1];
        if (/驗證日期/.test(key)) result.summary.date = val;
        if (/環境/.test(key)) result.summary.environment = val;
        if (/模式/.test(key)) result.summary.mode = val;
        if (/驗證工具|工具/.test(key)) result.summary.tool = val;
        if (/語系/.test(key)) result.summary.locale = val;
      }
    }
  }

  // --- 2. 解析統計表格 ---
  const statsTableStart = lines.findIndex(l => /^##\s*統計/.test(l.trim()));
  if (statsTableStart !== -1) {
    for (let i = statsTableStart + 1; i < lines.length && !lines[i].startsWith('## '); i++) {
      const row = lines[i].trim();
      if (!row.startsWith('|') || row.startsWith('|--') || row.startsWith('| 狀態')) continue;
      const cells = row.split('|').map(c => c.trim()).filter(Boolean);
      if (cells.length >= 2) {
        const label = cells[0];
        const count = parseInt(cells[1], 10) || 0;
        if (/PASS|通過/.test(label)) result.stats.pass = count;
        if (/FAIL|未通過/.test(label)) result.stats.fail = count;
        if (/WARN|警告/.test(label)) result.stats.warn = count;
        if (/BLOCKED|前置阻擋|阻擋/.test(label)) result.stats.blocked = count;
        if (/SKIP|略過/.test(label)) result.stats.skip = count;
        if (/MANUAL|人工/.test(label)) result.stats.manual = count;
      }
    }
  }

  // --- 3. 解析各驗收項目 ---
  // 找所有 ### [N] 開頭的段落
  const itemRegex = /^###\s*\[(\d+)\]\s*(.*)/;
  const itemIndices = [];
  for (let i = 0; i < lines.length; i++) {
    if (itemRegex.test(lines[i].trim())) {
      itemIndices.push(i);
    }
  }

  for (let idx = 0; idx < itemIndices.length; idx++) {
    const startLine = itemIndices[idx];
    const endLine = idx + 1 < itemIndices.length
      ? itemIndices[idx + 1]
      : lines.length;

    const headerMatch = lines[startLine].trim().match(itemRegex);
    const itemIndex = parseInt(headerMatch[1], 10);
    const headerRest = headerMatch[2];

    // 從 header 中提取狀態 emoji 和條件名稱
    const status = emojiToStatus(headerRest);
    const condition = headerRest
      .replace(/[✅❌⚠️⏭️👤⚠⏭]/g, '')
      .trim();

    const item = {
      index: itemIndex,
      condition: condition,
      status: status,
      type: '',
      verification: '',
      screenshot: '',
      failReason: '',
      humanSteps: [],
      evidence: null,
    };

    // 擷取此項目的所有行
    const block = lines.slice(startLine + 1, endLine).join('\n');

    // 解析 **類型** / **驗證** / **截圖** / **失敗原因** / **跳過原因** / **說明**
    const typeMatch = block.match(/\*\*類型\*\*[：:]\s*(.+)/);
    if (typeMatch) item.type = typeMatch[1].trim();

    const verifyMatch = block.match(/\*\*驗證\*\*[：:]\s*(.+)/);
    if (verifyMatch) item.verification = verifyMatch[1].trim();

    const screenshotMatch = block.match(/\*\*截圖\*\*[：:]\s*(.+)/);
    if (screenshotMatch) item.screenshot = screenshotMatch[1].trim();

    const failMatch = block.match(/\*\*失敗原因\*\*[：:]\s*(.+)/);
    if (failMatch) item.failReason = failMatch[1].trim();

    const blockedMatch = block.match(/\*\*(?:阻擋原因|前置阻擋原因)\*\*[：:]\s*(.+)/);
    if (blockedMatch && !item.failReason) item.failReason = blockedMatch[1].trim();

    const skipMatch = block.match(/\*\*跳過原因\*\*[：:]\s*(.+)/);
    if (skipMatch && !item.failReason) item.failReason = skipMatch[1].trim();

    const descMatch = block.match(/\*\*說明\*\*[：:]\s*(.+)/);
    if (descMatch && !item.verification) item.verification = descMatch[1].trim();

    // 解析 <!-- human_steps --> 註解區塊
    const humanStepsRegex = /<!--\s*human_steps\s*\n([\s\S]*?)-->/;
    const humanMatch = block.match(humanStepsRegex);
    if (humanMatch) {
      item.humanSteps = parseHumanSteps(humanMatch[1]);
    }

    // 解析 <!-- evidence --> 註解區塊
    const evidenceRegex = /<!--\s*evidence\s*\n([\s\S]*?)-->/;
    const evidenceMatch = block.match(evidenceRegex);
    if (evidenceMatch) {
      item.evidence = parseEvidence(evidenceMatch[1]);
    }

    // 如果沒有 evidence 區塊，也檢查是否有「不適用」標記
    const evidenceNaRegex = /<!--\s*evidence\s+不適用/;
    if (!item.evidence && evidenceNaRegex.test(block)) {
      item.evidence = null;
    }

    result.items.push(item);
  }

  return result;
}

// ============================================================
// 敏感資訊遮罩
// ============================================================

function maskSensitive(text) {
  if (!text) return '';
  return text
    // Cookie: JSESSIONID=abc123def456 → Cookie: JSES****f456
    .replace(/Cookie:\s*(\S{4})\S+(\S{4})/gi, 'Cookie: $1****$2')
    // Authorization: Bearer eyJhbGc... → Authorization: Bearer eyJh****
    .replace(/(Authorization:\s*\w+\s+\S{4})\S+/gi, '$1****')
    // X-API-Key: sk-live-xxx → X-API-Key: sk-l****
    .replace(/(X-API-Key:\s*\S{4})\S+/gi, '$1****')
    // Token: xxx → Token: xxxx****
    .replace(/(Token:\s*\S{4})\S+/gi, '$1****');
}

// ============================================================
// 工具函式
// ============================================================

function thinBorder() {
  return {
    top:    { style: 'hair' },
    left:   { style: 'hair' },
    bottom: { style: 'hair' },
    right:  { style: 'hair' },
  };
}

/**
 * 設定儲存格預設字型（如果尚未設定）
 */
function ensureFont(cell) {
  if (!cell.font || !cell.font.name) {
    cell.font = { name: '微軟正黑體', size: 10 };
  }
}

// ============================================================
// Sheet 1: 驗收總表
// ============================================================

function createSummarySheet(workbook, data, cover) {
  const ws = workbook.addWorksheet('驗收總表');

  // 欄寬設定
  ws.columns = [
    { width: 6 },   // A: #
    { width: 40 },  // B: 驗收條件
    { width: 10 },  // C: 結果
    { width: 12 },  // D: 截圖
    { width: 30 },  // E: 備註
    { width: 14 },  // F: 測試日期
  ];

  // --- 標題區（合併 A1:F1）---
  ws.mergeCells('A1:F1');
  const titleCell = ws.getCell('A1');
  titleCell.value = `${cover.project || '專案'} — ${cover.feature || '功能'} 驗收報告`;
  titleCell.font = {
    name: '微軟正黑體', size: 16, bold: true,
    color: { argb: 'FFFFFFFF' },
  };
  titleCell.fill = {
    type: 'pattern', pattern: 'solid',
    fgColor: { argb: BLUE_DARK },
  };
  titleCell.alignment = { horizontal: 'center', vertical: 'middle' };
  ws.getRow(1).height = 40;

  // --- 資訊區（第 3~7 行）---
  const infoRows = [
    ['驗證日期', data.summary.date || cover.date || ''],
    ['驗測人員', cover.author || ''],
    ['測試環境', data.summary.environment || ''],
    ['測試語系', data.summary.locale || 'zh-TW'],
    ['驗測工具', data.summary.tool || ''],
  ];
  infoRows.forEach((row, i) => {
    const r = ws.getRow(i + 3);
    r.getCell(1).value = row[0];
    r.getCell(1).font = { name: '微軟正黑體', size: 10, bold: true };
    ws.mergeCells(i + 3, 2, i + 3, 3);
    r.getCell(2).value = row[1];
    r.getCell(2).font = { name: '微軟正黑體', size: 10 };
  });

  // --- 明細表標題列（第 9 行）---
  const headerRowNum = 9;
  const headerRow = ws.getRow(headerRowNum);
  const headers = ['#', '驗收條件', '結果', '截圖', '備註', '測試日期'];
  headers.forEach((h, i) => {
    const cell = headerRow.getCell(i + 1);
    cell.value = h;
    cell.font = {
      name: '微軟正黑體', size: 10, bold: true,
      color: { argb: 'FFFFFFFF' },
    };
    cell.fill = {
      type: 'pattern', pattern: 'solid',
      fgColor: { argb: BLUE_MID },
    };
    cell.alignment = { horizontal: 'center', vertical: 'middle' };
    cell.border = thinBorder();
  });
  headerRow.height = 24;

  // 凍結標題列
  ws.views = [{ state: 'frozen', ySplit: headerRowNum }];

  // --- 明細資料 ---
  const dataStartRow = headerRowNum + 1;
  data.items.forEach((item, idx) => {
    const row = ws.getRow(dataStartRow + idx);

    // A: 序號
    row.getCell(1).value = idx + 1;
    row.getCell(1).alignment = { horizontal: 'center', vertical: 'middle' };

    // B: 驗收條件
    row.getCell(2).value = item.condition;
    row.getCell(2).alignment = { wrapText: true, vertical: 'top' };

    // C: 結果（帶背景色）
    const statusInfo = STATUS_COLORS[item.status] || STATUS_COLORS.SKIP;
    const resultCell = row.getCell(3);
    resultCell.value = statusInfo.text;
    resultCell.fill = {
      type: 'pattern', pattern: 'solid',
      fgColor: { argb: statusInfo.bg },
    };
    resultCell.alignment = { horizontal: 'center', vertical: 'middle' };

    // D: 截圖超連結（連到對應的明細 Sheet）
    const linkCell = row.getCell(4);
    linkCell.value = { text: '查看', hyperlink: `#'項目 ${idx + 1}'!A1` };
    linkCell.font = {
      name: '微軟正黑體', size: 10,
      color: { argb: 'FF0563C1' }, underline: true,
    };
    linkCell.alignment = { horizontal: 'center' };

    // E: 備註
    row.getCell(5).value = ['FAIL', 'BLOCKED'].includes(item.status) ? (item.failReason || '') : '';
    row.getCell(5).alignment = { wrapText: true, vertical: 'top' };

    // F: 測試日期
    row.getCell(6).value = data.summary.date || cover.date || '';
    row.getCell(6).alignment = { horizontal: 'center', vertical: 'middle' };

    // 統一邊框與字型
    for (let c = 1; c <= 6; c++) {
      row.getCell(c).border = thinBorder();
      ensureFont(row.getCell(c));
    }

    // 行高
    row.height = Math.max(22, 22 + (item.condition.length > 30 ? 16 : 0));
  });

  // --- 簽核區 ---
  const signRowStart = dataStartRow + data.items.length + 2;

  // 簽核標題
  ws.mergeCells(`A${signRowStart}:F${signRowStart}`);
  ws.getCell(`A${signRowStart}`).value = '簽核';
  ws.getCell(`A${signRowStart}`).font = { name: '微軟正黑體', size: 12, bold: true };

  // 簽核表標題列
  const signHeaderRowNum = signRowStart + 1;
  const signHeaderRow = ws.getRow(signHeaderRowNum);
  const signHeaders = ['角色', '姓名', '簽章', '', '日期', ''];
  signHeaders.forEach((h, i) => {
    signHeaderRow.getCell(i + 1).value = h;
    signHeaderRow.getCell(i + 1).font = { name: '微軟正黑體', size: 10, bold: true };
    signHeaderRow.getCell(i + 1).border = thinBorder();
    signHeaderRow.getCell(i + 1).fill = {
      type: 'pattern', pattern: 'solid',
      fgColor: { argb: BLUE_LIGHT },
    };
  });
  // 合併簽章欄位（C+D）與日期欄位（E+F）
  ws.mergeCells(signHeaderRowNum, 3, signHeaderRowNum, 4);
  ws.mergeCells(signHeaderRowNum, 5, signHeaderRowNum, 6);

  // 簽核資料行
  const signData = [
    ['製作人', cover.author || ''],
    ['審核人', ''],
    ['客戶確認', ''],
  ];
  signData.forEach((s, i) => {
    const rNum = signHeaderRowNum + 1 + i;
    const r = ws.getRow(rNum);
    r.getCell(1).value = s[0];
    r.getCell(2).value = s[1];
    // 合併簽章欄位（C+D）與日期欄位（E+F）
    ws.mergeCells(rNum, 3, rNum, 4);
    ws.mergeCells(rNum, 5, rNum, 6);
    for (let c = 1; c <= 6; c++) {
      r.getCell(c).border = thinBorder();
      r.getCell(c).font = { name: '微軟正黑體', size: 10 };
    }
    r.height = 30;
  });

  return ws;
}

// ============================================================
// Sheet 2~N: 各驗收項目明細
// ============================================================

function createDetailSheet(workbook, item, index, screenshotsDir, evidenceDir) {
  const sheetName = `項目 ${index}`;
  const ws = workbook.addWorksheet(sheetName);

  ws.columns = [
    { width: 15 },  // A: 欄位名稱
    { width: 60 },  // B: 內容
    { width: 30 },  // C: 備用
  ];

  let currentRow = 1;

  // --- 標頭：驗收條件 ---
  ws.mergeCells(`A${currentRow}:C${currentRow}`);
  const titleCell = ws.getCell(`A${currentRow}`);
  titleCell.value = `驗收條件：${item.condition}`;
  titleCell.font = { name: '微軟正黑體', size: 14, bold: true };
  titleCell.alignment = { vertical: 'middle' };
  ws.getRow(currentRow).height = 30;

  currentRow++;

  // --- 結果狀態 ---
  const statusInfo = STATUS_COLORS[item.status] || STATUS_COLORS.SKIP;
  ws.mergeCells(`A${currentRow}:C${currentRow}`);
  const resultCell = ws.getCell(`A${currentRow}`);
  resultCell.value = `結果：${statusInfo.text}`;
  resultCell.font = { name: '微軟正黑體', size: 12, bold: true };
  resultCell.fill = {
    type: 'pattern', pattern: 'solid',
    fgColor: { argb: statusInfo.bg },
  };
  resultCell.alignment = { vertical: 'middle' };
  ws.getRow(currentRow).height = 26;

  currentRow++;

  // --- 類型 ---
  if (item.type) {
    currentRow++;
    ws.getCell(`A${currentRow}`).value = '類型';
    ws.getCell(`A${currentRow}`).font = { name: '微軟正黑體', size: 10, bold: true };
    ws.getCell(`B${currentRow}`).value = item.type;
    ws.getCell(`B${currentRow}`).font = { name: '微軟正黑體', size: 10 };
  }

  // --- 驗證方式 ---
  if (item.verification) {
    currentRow++;
    ws.getCell(`A${currentRow}`).value = '驗證方式';
    ws.getCell(`A${currentRow}`).font = { name: '微軟正黑體', size: 10, bold: true };
    ws.getCell(`B${currentRow}`).value = item.verification;
    ws.getCell(`B${currentRow}`).font = { name: 'Consolas', size: 9 };
    ws.getCell(`B${currentRow}`).alignment = { wrapText: true };
  }

  currentRow += 2;

  // --- 操作步驟 ---
  if (item.humanSteps && item.humanSteps.length > 0) {
    ws.getCell(`A${currentRow}`).value = '操作步驟';
    ws.getCell(`A${currentRow}`).font = { name: '微軟正黑體', size: 11, bold: true };
    ws.getCell(`A${currentRow}`).fill = {
      type: 'pattern', pattern: 'solid',
      fgColor: { argb: BLUE_LIGHT },
    };
    ws.mergeCells(`A${currentRow}:C${currentRow}`);
    currentRow++;

    item.humanSteps.forEach((step, i) => {
      if (step.action) {
        ws.getCell(`A${currentRow}`).value = `步驟 ${i + 1}`;
        ws.getCell(`A${currentRow}`).font = { name: '微軟正黑體', size: 10, bold: true };
        ws.getCell(`B${currentRow}`).value = step.action;
        ws.getCell(`B${currentRow}`).font = { name: '微軟正黑體', size: 10 };
        ws.getCell(`B${currentRow}`).alignment = { wrapText: true };
        currentRow++;
      }
    });

    currentRow++;

    // 取最後一個 step 的預期/實際（或逐條顯示所有有值的）
    const stepsWithExpected = item.humanSteps.filter(s => s.expected);
    const stepsWithActual = item.humanSteps.filter(s => s.actual);

    if (stepsWithExpected.length > 0) {
      ws.getCell(`A${currentRow}`).value = '預期結果';
      ws.getCell(`A${currentRow}`).font = { name: '微軟正黑體', size: 10, bold: true };
      const expectedText = stepsWithExpected.map(s => s.expected).join('\n');
      ws.getCell(`B${currentRow}`).value = expectedText;
      ws.getCell(`B${currentRow}`).font = { name: '微軟正黑體', size: 10 };
      ws.getCell(`B${currentRow}`).alignment = { wrapText: true, vertical: 'top' };
      ws.getRow(currentRow).height = Math.max(22, expectedText.split('\n').length * 16);
      currentRow++;
    }

    if (stepsWithActual.length > 0) {
      ws.getCell(`A${currentRow}`).value = '實際結果';
      ws.getCell(`A${currentRow}`).font = { name: '微軟正黑體', size: 10, bold: true };
      const actualText = stepsWithActual.map(s => s.actual).join('\n');
      ws.getCell(`B${currentRow}`).value = actualText;
      ws.getCell(`B${currentRow}`).font = { name: '微軟正黑體', size: 10 };
      ws.getCell(`B${currentRow}`).alignment = { wrapText: true, vertical: 'top' };
      ws.getRow(currentRow).height = Math.max(22, actualText.split('\n').length * 16);
      currentRow++;
    }
  }

  // --- 失敗原因 ---
  if (['FAIL', 'BLOCKED'].includes(item.status) && item.failReason) {
    currentRow++;
    ws.getCell(`A${currentRow}`).value = '失敗原因';
    ws.getCell(`A${currentRow}`).font = {
      name: '微軟正黑體', size: 10, bold: true,
      color: { argb: 'FFCC0000' },
    };
    ws.getCell(`B${currentRow}`).value = item.failReason;
    ws.getCell(`B${currentRow}`).font = { name: '微軟正黑體', size: 10 };
    ws.getCell(`B${currentRow}`).alignment = { wrapText: true };
    currentRow++;
  }

  currentRow++;

  // --- 截圖嵌入 ---
  if (item.screenshot && screenshotsDir) {
    const screenshotPath = path.resolve(screenshotsDir, path.basename(item.screenshot));
    if (fs.existsSync(screenshotPath)) {
      const imageBuffer = fs.readFileSync(screenshotPath);

      // 讀取 PNG 寬高（bytes 16-23）
      let imgW = 800;
      let imgH = 600;
      if (imageBuffer.length > 24 && imageBuffer[0] === 0x89 && imageBuffer[1] === 0x50) {
        imgW = imageBuffer.readUInt32BE(16);
        imgH = imageBuffer.readUInt32BE(20);
      }

      const targetWidth = 800;
      const scale = targetWidth / imgW;
      const targetHeight = Math.round(imgH * scale);

      const imageId = workbook.addImage({
        buffer: imageBuffer,
        extension: 'png',
      });

      ws.getCell(`A${currentRow}`).value = '截圖';
      ws.getCell(`A${currentRow}`).font = { name: '微軟正黑體', size: 11, bold: true };
      ws.getCell(`A${currentRow}`).fill = {
        type: 'pattern', pattern: 'solid',
        fgColor: { argb: BLUE_LIGHT },
      };
      ws.mergeCells(`A${currentRow}:C${currentRow}`);
      currentRow++;

      ws.addImage(imageId, {
        tl: { col: 0, row: currentRow - 1 },
        ext: { width: targetWidth, height: targetHeight },
      });

      // 預留足夠行高容納截圖
      const rowsNeeded = Math.ceil(targetHeight / 20);
      for (let r = 0; r < rowsNeeded; r++) {
        ws.getRow(currentRow + r).height = 20;
      }
      currentRow += rowsNeeded + 1;
    } else {
      ws.getCell(`A${currentRow}`).value = `（截圖不可用: ${item.screenshot}）`;
      ws.getCell(`A${currentRow}`).font = {
        name: '微軟正黑體', size: 10, italic: true,
        color: { argb: 'FF999999' },
      };
      currentRow++;
    }
  }

  // --- API 測試紀錄 ---
  if (item.evidence) {
    currentRow++;
    ws.getCell(`A${currentRow}`).value = 'API 測試紀錄';
    ws.getCell(`A${currentRow}`).font = { name: '微軟正黑體', size: 11, bold: true };
    ws.getCell(`A${currentRow}`).fill = {
      type: 'pattern', pattern: 'solid',
      fgColor: { argb: BLUE_LIGHT },
    };
    ws.mergeCells(`A${currentRow}:C${currentRow}`);
    currentRow++;

    // 請求
    if (item.evidence.request) {
      ws.getCell(`A${currentRow}`).value = '請求';
      ws.getCell(`A${currentRow}`).font = { name: '微軟正黑體', size: 10, bold: true };
      const maskedRequest = maskSensitive(item.evidence.request);
      ws.getCell(`B${currentRow}`).value = maskedRequest;
      ws.getCell(`B${currentRow}`).font = { name: 'Consolas', size: 9 };
      ws.getCell(`B${currentRow}`).alignment = { wrapText: true, vertical: 'top' };
      ws.getRow(currentRow).height = Math.max(22, maskedRequest.split('\n').length * 14);
      currentRow++;
    }

    // 回應
    if (item.evidence.responseStatus) {
      ws.getCell(`A${currentRow}`).value = '回應';
      ws.getCell(`A${currentRow}`).font = { name: '微軟正黑體', size: 10, bold: true };

      let responseText = `HTTP ${item.evidence.responseStatus}`;

      // 嘗試讀取 evidence 回應檔案
      if (item.evidence.responseFile && evidenceDir) {
        const respFileName = path.basename(item.evidence.responseFile);
        const respPath = path.resolve(evidenceDir, respFileName);
        if (fs.existsSync(respPath)) {
          const respContent = fs.readFileSync(respPath, 'utf-8');
          const respLines = respContent.split('\n');

          if (respLines.length <= 20) {
            // 20 行以下完整顯示
            responseText += '\n' + maskSensitive(respContent);
          } else {
            // 超過 20 行：前 10 行 + 省略 + 後 10 行
            const first10 = respLines.slice(0, 10).join('\n');
            const last10 = respLines.slice(-10).join('\n');
            const omitted = respLines.length - 20;
            responseText += '\n' + maskSensitive(first10) +
              `\n... （省略 ${omitted} 行，共 ${respLines.length} 行） ...\n` +
              maskSensitive(last10);
          }
          responseText += `\n\n> 完整回應請見：${item.evidence.responseFile}`;
        }
      }

      ws.getCell(`B${currentRow}`).value = responseText;
      ws.getCell(`B${currentRow}`).font = { name: 'Consolas', size: 9 };
      ws.getCell(`B${currentRow}`).alignment = { wrapText: true, vertical: 'top' };
      // 根據行數調整行高，最多 400
      ws.getRow(currentRow).height = Math.min(400, 20 + responseText.split('\n').length * 13);
      currentRow++;
    }
  }

  // --- 底部返回連結 ---
  currentRow += 2;
  const backCell = ws.getCell(`A${currentRow}`);
  backCell.value = { text: '⬅ 返回驗收總表', hyperlink: "#'驗收總表'!A1" };
  backCell.font = {
    name: '微軟正黑體', size: 10,
    color: { argb: 'FF0563C1' }, underline: true,
  };

  return ws;
}

// ============================================================
// 主程式
// ============================================================

async function main() {
  // 1. 解析 CLI 參數
  const args = parseArgs();

  // 2. 檢查 verify.md 是否存在
  const verifyPath = path.resolve(args.verify);
  if (!fs.existsSync(verifyPath)) {
    console.error(`❌ 找不到 verify.md: ${verifyPath}`);
    process.exit(1);
  }

  // 3. 解析目錄路徑
  const screenshotsDir = args.screenshots ? path.resolve(args.screenshots) : null;
  const evidenceDir = args.evidence ? path.resolve(args.evidence) : null;
  const outputPath = path.resolve(args.output);

  // 4. 讀取並解析 verify.md
  console.log(`📖 讀取 verify.md: ${verifyPath}`);
  const data = parseVerifyMd(verifyPath);
  console.log(`   找到 ${data.items.length} 項驗收條件`);

  if (data.items.length === 0) {
    console.error('❌ verify.md 中未找到任何驗收項目（格式：### [N] ...）');
    process.exit(1);
  }

  // 5. 準備封面資訊
  const cover = {
    project: args.cover.project || '專案',
    feature: args.cover.feature || '功能',
    author: args.cover.author || '',
    date: args.cover.date || data.summary.date || new Date().toISOString().slice(0, 10),
  };

  // 6. 建立 workbook
  const workbook = new ExcelJS.Workbook();
  workbook.creator = cover.author || 'verify-excel-generator';
  workbook.created = new Date();

  // 7. 建立驗收總表
  console.log('📊 建立驗收總表...');
  createSummarySheet(workbook, data, cover);

  // 8. 逐項建立明細 Sheet
  data.items.forEach((item, idx) => {
    const sheetIndex = idx + 1;
    console.log(`   📋 項目 ${sheetIndex}: ${item.condition} [${item.status}]`);
    createDetailSheet(workbook, item, sheetIndex, screenshotsDir, evidenceDir);
  });

  // 9. 確保輸出目錄存在
  const outputDir = path.dirname(outputPath);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  // 10. 寫入 .xlsx
  console.log(`💾 寫入 Excel: ${outputPath}`);
  await workbook.xlsx.writeFile(outputPath);

  // 11. 輸出完成訊息
  const stats = data.stats;
  console.log('');
  console.log('✅ Excel 驗收報告產出完成！');
  console.log(`   📄 檔案：${outputPath}`);
  console.log(`   📊 統計：✅ ${stats.pass} / ❌ ${stats.fail} / ⚠️ ${stats.warn} / ⏭️ ${stats.skip} / 👤 ${stats.manual}`);
  console.log(`   📋 Sheet 數：${1 + data.items.length}（總表 + ${data.items.length} 項明細）`);
}

main().catch(err => {
  console.error('❌ Excel 報告產出失敗:', err.message);
  if (err.stack) {
    console.error(err.stack);
  }
  process.exit(1);
});
