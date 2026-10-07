// CREW Cockpit 讀取模型：型別 re-export、常數與「純函式」工具。
// 本檔不做任何 I/O，也不呼叫 $。型別本體定義在 types/index.d.ts（$.state 契約）。

export type {
  CockpitError,
  CockpitField,
  CockpitGateView,
  CockpitInvalidTask,
  CockpitIrAcView,
  CockpitIrRouteCount,
  CockpitIrSummary,
  CockpitResultView,
  CockpitResumeHintView,
  CockpitRuntime,
  CockpitSelectionReason,
  CockpitSnapshot,
  CockpitStepView,
  CockpitTab,
  CockpitTaskView,
  CockpitVerifyView,
  CockpitWorkUnitView,
} from '../../types'

/** 讀取模型版本；改動 snapshot 形狀時遞增，loader 會丟棄舊版快取。 */
export const MODEL_VERSION = 2

/** Pane id（§10）。 */
export const PANE_ID = 'crew-cockpit'

/** 指令名（§10）。 */
export const COMMAND_NAME = 'crew-cockpit'

/** 最低支援的 Claude Code 版本（§19）。 */
export const MIN_CLAUDE_CODE_VERSION = '2.1.289'

/** 測試過的最高 state schema（§16）。 */
export const MAX_KNOWN_SCHEMA = 2

/** $.fs.read 單檔上限 4 MiB（§6.2）。 */
export const MAX_FILE_BYTES = 4 * 1024 * 1024

/** HUD 單一欄位上限（§18.1）。 */
export const HUD_FIELD_MAX = 60

/** Pane 欄位上限（§18.1）；snapshot 內所有顯示字串都已截到這個長度。 */
export const PANE_FIELD_MAX = 200

/** Fill 代入 slug 的白名單（§14）。 */
export const SLUG_PATTERN = /^[a-z0-9][a-z0-9._-]{0,79}$/

/** 結案判定用（CS DONE_LIKE）。 */
export const DONE_LIKE: readonly string[] = ['done', 'skipped']

const DAY_MS = 24 * 60 * 60 * 1000

/** UI 文字常數表（§17.5）：標籤繁中，識別字保留原文。 */
export const TEXT = {
  paneTitle: 'CREW',
  tabOverview: '總覽',
  tabTasks: '任務',
  tabVerify: '驗收',
  progress: '進度',
  approval: '核准閘',
  results: '結果',
  workUnit: '工作單元',
  resumeHint: '接續提示',
  recordedNext: '上次記錄的建議（快照）',
  recordedNextShort: '上次建議',
  refresh: '重新整理',
  fill: (slug: string) => `填入 /plan-next ${slug}`,
  stale: (days: number) => `停滯 ${days} 天`,
  staleUnknown: '（時間無法解析）',
  autoSelected: '自動選取',
  loadedAt: (hhmm: string) => `載入於 ${hhmm}`,
  irMissing: '尚未產生 E2E 候選',
  irReady: '已就緒',
  irInvalid: '無法解析',
  irInvalidHint: 'Verification IR：檔案無法解析\n重新執行 /plan-verify 可重新產生。',
  blockedNote: (n: number) => `BLOCKED ×${n}：驗收前置條件尚未就緒，不代表產品 FAIL`,
  truthSeparator: 'Runtime PASS ≠ E2E ci-ready ≠ 人工 UAT',
  /** §17.5／§9 HUD 範例：UAT gate 為 pending 時顯示「UAT 待核准」；其餘狀態值保留原文（識別字）。 */
  uatPendingShort: 'UAT 待核准',
  v1NoGates: '舊版格式（schema v1），無核准閘資料',
  noTasks: '此 repo 沒有 CREW 任務。',
  noTasksHint: '用 /plan-start 或 /bug-start 開始一個。',
  invalidState: 'state.json 無法解析',
  invalidStateNote: '/plan-status 不會列出此筆',
  fileTooLarge: '檔案過大（超過 4 MiB）',
  notObject: 'state.json 不是 JSON 物件',
  untracked: (n: number) => `另有 ${n} 個 .spec 目錄沒有 state.json（舊格式或未初始化），未列入。`,
  schemaNewer: (v: number) => `state schema v${v} 比 Cockpit 測試過的 v2 新，部分欄位可能未顯示`,
  slugNotFillable: 'slug 含不支援的字元，請手動執行 /plan-next',
  needVersion: (min: string) => `需要 Claude Code ≥ ${min}`,
  otherActive: (n: number) => `＋${n} 個進行中`,
  paneOpened: '已開啟 CREW Cockpit。',
  paneNotPlaced: 'Cockpit 將在畫面寬度足夠時顯示',
  usage: '用法：/crew-cockpit',
  // ---- 以下為 Batch 3–6 新增（只增不改）----
  currentTask: '目前任務',
  branchNote: '（取自 state.git，非即時 git 狀態）',
  interrupted: (done: number, total: number) => `中斷於 ${done}/${total}`,
  readFirst: '先讀',
  services: '服務',
  inferred: '⚠ phase 為推導值（inferred）',
  inferredShort: '⚠ inferred',
  // 對齊 crew-state.py 用語（park＝「擱置任務」、list 標記「已擱置」）
  parked: '已擱置',
  closedTask: '已結案',
  verifyLabel: '驗收',
  otherBlocked: (n: number) => `另有 BLOCKED ×${n}`,
  runtimeVerify: 'Runtime Verify',
  verificationIr: 'Verification IR',
  irUntyped: '（未標 verification_type）',
  tasksTruncated: (n: number) => `只顯示前 ${n} 筆`,
  noSelection: '目前沒有選取的任務；到「任務」分頁選一個。',
  noVerifyResult: '尚無驗收結果',
  hudOn: '已開啟 CREW HUD。',
  hudOff: '已關閉 CREW HUD（/crew-cockpit hud on 可重新開啟）。',
  usageFull: '用法：/crew-cockpit 開啟面板；/crew-cockpit hud on|off 開關 HUD',
  draftExists: (command: string) => `輸入框有未送出的內容；指令：${command}`,
  fillRefused: (command: string) => `無法填入輸入框，請自行輸入：${command}`,
  loadErrors: '載入問題',
  schemaUnknown: 'schema ?',
  schema: (v: number) => `schema v${v}`,
  selected: '▶',
  // ---- 以下為分組色帶樣式新增（只增不改）----
  groupActive: (n: number) => `● 進行中 ${n}`,
  groupParked: (n: number) => `◐ 已擱置 ${n}`,
  groupClosed: (n: number) => `○ 已結案 ${n}`,
  closedVerifyCount: (n: number, status: string) => `其中 ${n} 項驗收 ${status}`,
  closedRecent: (n: number) => `最近 ${n} 筆`,
  expandClosed: '展開全部',
  collapseClosed: '收合',
  invalidMark: '✕',
  gatePending: '（待核准）',
  // ---- 以下為儀表板總覽新增（只增不改）----
  statusBox: '狀態',
  staleBox: '停滯',
  verifyBox: '驗收',
  staleDaysBig: (days: number) => `${days} 天`,
  lastUpdated: (time: string) => `最後更新 ${time}`,
  phaseInProgress: (phase: string) => `${phase} 進行中`,
  gatePendingShort: '待核准',
  gatesNone: '—',
  workUnitInterrupted: (done: number, total: number) => `⚠ 工作單元中斷於 ${done}/${total}`,
  recordedNextSnapshot: '上次建議（快照）',
  otherActiveList: (n: number) => `另有 ${n} 個進行中：`,
  otherActiveItem: (slug: string, days: number) => `${slug}（停滯 ${days} 天）`,
  moreItems: (n: number) => `＋${n}`,
} as const

// ---------------------------------------------------------------------------
// §18.1 不可信字串清理
// ---------------------------------------------------------------------------

// ANSI：CSI（ESC [ …）、OSC（ESC ] … BEL 或 ESC \）、其他 2 字元 ESC 序列，以及 8-bit CSI（\x9b …）。
const ANSI_CSI = /\x1b\[[0-?]*[ -/]*[@-~]/g
const ANSI_OSC = /\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?/g
const ANSI_OTHER = /\x1b[@-Z\\-_]/g
const C1_CSI = /\x9b[0-?]*[ -/]*[@-~]/g
// 剩餘的 C0（含 ESC 殘渣）、DEL、C1 控制字元，以及零寬與方向控制字元（§18.1）：
// U+200B–U+200F（零寬空白／ZWNJ／ZWJ／LRM／RLM）、U+202A–U+202E（bidi 嵌入與覆寫）、
// U+2060–U+2069（word joiner、不可見運算子、bidi isolate）、U+FEFF（BOM／ZWNBSP）、U+061C（阿拉伯字母標記）。
const CONTROL = /[\x00-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff\u061c]/g
const LINE_BREAKS = /[\r\n\t\v\f\u0085\u2028\u2029]+/g

/**
 * 把任意值轉成可安全顯示的一行字串（§18.1）：
 * 去 ANSI escape 與 C0/C1 控制字元、換行壓成空白、連續空白收斂、截斷並以 … 結尾。
 * 非字串：number/boolean 轉字串；物件與陣列以 JSON 表示；null/undefined 為空字串。
 */
export function sanitizeText(value: unknown, max: number = PANE_FIELD_MAX): string {
  let text: string
  if (value === null || value === undefined) {
    text = ''
  } else if (typeof value === 'string') {
    text = value
  } else if (typeof value === 'number' || typeof value === 'boolean') {
    text = String(value)
  } else {
    try {
      text = JSON.stringify(value) ?? ''
    } catch {
      text = ''
    }
  }
  const cleaned = text
    .replace(ANSI_OSC, '')
    .replace(ANSI_CSI, '')
    .replace(C1_CSI, '')
    .replace(ANSI_OTHER, '')
    .replace(LINE_BREAKS, ' ')
    .replace(CONTROL, '')
    .replace(/ {2,}/g, ' ')
    .trim()
  return clip(cleaned, max)
}

/** 已清理的字串截到 max 個字元（以 code point 計），超過以 … 結尾。 */
export function clip(text: string, max: number): string {
  const chars = Array.from(text)
  if (chars.length <= max) {
    return text
  }
  if (max <= 1) {
    return '…'.slice(0, Math.max(0, max))
  }
  return chars.slice(0, max - 1).join('') + '…'
}

/** 清理後若為空字串則回 null；原值為 null/undefined 也回 null。 */
export function sanitizeOrNull(value: unknown, max: number = PANE_FIELD_MAX): string | null {
  if (value === null || value === undefined) {
    return null
  }
  const text = sanitizeText(value, max)
  return text === '' ? null : text
}

/** §14 slug 白名單。 */
export function isFillableSlug(id: string): boolean {
  return SLUG_PATTERN.test(id)
}

// ---------------------------------------------------------------------------
// 與 crew-state.py 對齊的判定（§8，不得自創）
// ---------------------------------------------------------------------------

/** Python truthiness（parked、inferred 用）。 */
export function isTruthy(value: unknown): boolean {
  if (value === null || value === undefined || value === false) {
    return false
  }
  if (typeof value === 'number') {
    return value !== 0 && !Number.isNaN(value)
  }
  if (typeof value === 'string') {
    return value.length > 0
  }
  if (Array.isArray(value)) {
    return value.length > 0
  }
  if (typeof value === 'object') {
    return Object.keys(value as object).length > 0
  }
  return true
}

/**
 * crew-state.py as_int 語意：int(value)，失敗回 default。
 * number 取整數部分（int(2.7) == 2）；boolean 為 1/0；字串允許前後空白、正負號與底線分隔的十進位整數。
 */
export function asInt(value: unknown, fallback: number = 0): number {
  if (typeof value === 'boolean') {
    return value ? 1 : 0
  }
  if (typeof value === 'number') {
    return Number.isFinite(value) ? Math.trunc(value) : fallback
  }
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (/^[+-]?\d+(?:_\d+)*$/.test(trimmed)) {
      const parsed = Number.parseInt(trimmed.replace(/_/g, ''), 10)
      return Number.isFinite(parsed) ? parsed : fallback
    }
  }
  return fallback
}

const ISO_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2})(?::(\d{2})(?::(\d{2})(?:[.,](\d{1,9}))?)?)?)?(Z|[+-]\d{2}(?::?\d{2})?)?$/

/**
 * crew-state.py parse_iso 的近似：datetime.fromisoformat；不帶時區的值視為本機時間。
 * 回傳 epoch ms；無法解析回 null。只接受 ISO 8601 的日期／日期時間形式，不用 Date.parse 猜格式。
 */
export function parseIsoMs(value: unknown): number | null {
  if (typeof value !== 'string' || value === '') {
    return null
  }
  const match = ISO_PATTERN.exec(value.trim())
  if (!match) {
    return null
  }
  const [, y, mo, d, h, mi, s, frac, zone] = match
  const year = Number(y)
  const month = Number(mo)
  const day = Number(d)
  const hour = h === undefined ? 0 : Number(h)
  const minute = mi === undefined ? 0 : Number(mi)
  const second = s === undefined ? 0 : Number(s)
  const ms = frac === undefined ? 0 : Math.floor(Number(`0.${frac}`) * 1000)
  if (month < 1 || month > 12 || day < 1 || day > 31 || hour > 23 || minute > 59 || second > 59) {
    return null
  }
  if (zone === undefined) {
    const local = new Date(year, month - 1, day, hour, minute, second, ms)
    if (local.getFullYear() !== year || local.getMonth() !== month - 1 || local.getDate() !== day) {
      return null
    }
    return local.getTime()
  }
  const utc = Date.UTC(year, month - 1, day, hour, minute, second, ms)
  const check = new Date(utc)
  if (check.getUTCFullYear() !== year || check.getUTCMonth() !== month - 1 || check.getUTCDate() !== day) {
    return null
  }
  if (zone === 'Z') {
    return utc
  }
  const sign = zone.startsWith('-') ? -1 : 1
  const digits = zone.slice(1).replace(':', '')
  const offH = Number(digits.slice(0, 2))
  const offM = digits.length > 2 ? Number(digits.slice(2, 4)) : 0
  if (offH > 23 || offM > 59) {
    return null
  }
  return utc - sign * (offH * 60 + offM) * 60 * 1000
}

/**
 * 停滯天數的參考時間，逐步重現 crew-state.py 的 normalize() ＋ stale_days()（CS:299-312、1364-1369）：
 * 1. normalize 只把「null 或缺漏」的 updated／created 補成現在（空字串、壞字串原樣保留）；
 * 2. stale_days 取 parse_iso(updated) or parse_iso(created)。
 * 因此 updated 為 null／缺漏 → 參考值是現在（0 天），不會退到 created；
 * updated 解析失敗才看 created，created 為 null／缺漏同樣是現在（0 天）；兩者都解析失敗 → 0 天且 isUnknown。
 * refMs 為 null 代表 crew-state.py 會算出 0 天（不論是「現在」還是無法解析），增量重讀時仍是 0。
 */
export function crewStaleRef(updated: unknown, created: unknown): { refMs: number | null; isUnknown: boolean } {
  const isFilledByNormalize = (value: unknown) => value === null || value === undefined
  if (isFilledByNormalize(updated)) {
    return { refMs: null, isUnknown: false }
  }
  const updatedMs = parseIsoMs(updated)
  if (updatedMs !== null) {
    return { refMs: updatedMs, isUnknown: false }
  }
  if (isFilledByNormalize(created)) {
    return { refMs: null, isUnknown: false }
  }
  const createdMs = parseIsoMs(created)
  return createdMs !== null ? { refMs: createdMs, isUnknown: false } : { refMs: null, isUnknown: true }
}

/** CS stale_days：max(0, floor((now − ref) / 1 day))；ref 為 null 時 0。 */
export function staleDaysOf(refMs: number | null, nowMs: number): number {
  if (refMs === null) {
    return 0
  }
  return Math.max(0, Math.floor((nowMs - refMs) / DAY_MS))
}

/** "2.1.291" 這類版本字串比較；無法解析的段視為 0。a<b 負、相等 0、a>b 正。 */
export function compareVersions(a: string, b: string): number {
  const parts = (v: string) =>
    v
      .split(/[^0-9]+/)
      .filter(p => p !== '')
      .slice(0, 3)
      .map(p => Number(p))
  const pa = parts(a)
  const pb = parts(b)
  for (let i = 0; i < 3; i += 1) {
    const diff = (pa[i] ?? 0) - (pb[i] ?? 0)
    if (diff !== 0) {
      return diff
    }
  }
  return 0
}
