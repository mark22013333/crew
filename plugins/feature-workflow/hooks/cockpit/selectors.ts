// CREW Cockpit selectors：只做 UI 選取與格式化的純函式（不做 I/O、不呼叫 $）。
// render 可放心在繪製時呼叫。這些都是 presentation，不是 workflow 判定。

import { selectTask } from './loader'
import {
  type CockpitGateView,
  type CockpitSelectionReason,
  type CockpitSnapshot,
  type CockpitTaskView,
  type CockpitVerifyView,
  DONE_LIKE,
  HUD_FIELD_MAX,
  TEXT,
  clip,
} from './model'

/** 依 snapshot 與使用者選擇（$.state selectedSlug）即時算出目前選取（§8）。 */
export function resolveSelection(
  snapshot: CockpitSnapshot | null,
  userSelectedSlug: string | null,
): { task: CockpitTaskView | null; reason: CockpitSelectionReason; autoSelected: boolean } {
  if (snapshot === null) {
    return { task: null, reason: 'none', autoSelected: false }
  }
  const { slug, reason } = selectTask(snapshot.tasks, userSelectedSlug)
  const task = slug === null ? null : (snapshot.tasks.find(item => item.id === slug) ?? null)
  return { task, reason, autoSelected: reason === 'latest-active' }
}

/** 除了目前選取以外的 active task 數（HUD「＋N 個進行中」，§9.1）。 */
export function otherActiveCount(snapshot: CockpitSnapshot | null, selected: CockpitTaskView | null): number {
  if (snapshot === null) {
    return 0
  }
  const own = selected !== null && selected.active ? 1 : 0
  return Math.max(0, snapshot.activeCount - own)
}

/** §11.1 進度：(done + skipped) / 實際存在的 steps 數（不寫死 9 步）。 */
export function progressOf(task: CockpitTaskView): { done: number; total: number } {
  const done = task.steps.filter(step => step.status !== null && DONE_LIKE.includes(step.status)).length
  return { done, total: task.steps.length }
}

/**
 * §11.2 依 type 決定顯示哪些 gate：bug 只顯示 uat；其他顯示全部。
 * v1（gates === null）回 null：呼叫端改顯示「舊版格式（schema v1），無核准閘資料」，不得顯示 pending。
 */
export function visibleGates(task: CockpitTaskView): CockpitGateView[] | null {
  if (task.gates === null) {
    return null
  }
  return task.type === 'bug' ? task.gates.filter(gate => gate.key === 'uat') : task.gates
}

/** HUD 欄位截斷（§18.1：HUD 單一欄位 ≤ 60 字元）。輸入須是 snapshot 內已清理的字串。 */
export function hudText(text: string): string {
  return clip(text, HUD_FIELD_MAX)
}

/** 「載入於 HH:MM」的 HH:MM（本機時區）。 */
export function formatClock(ms: number): string {
  const date = new Date(ms)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/**
 * §14 Fill 的固定內容：只有 `/plan-next {slug}`，且 slug 必須通過白名單。
 * 不得改用 state.next.command 或任何 repo 字串。不通過白名單回 null（不提供 Fill 按鈕）。
 */
export function fillCommandFor(task: CockpitTaskView | null): string | null {
  if (task === null || !task.isSlugFillable) {
    return null
  }
  return `/plan-next ${task.id}`
}

// ---------------------------------------------------------------------------
// Batch 3–6 新增：顯示用的色調與驗收狀態映射（presentation，不是 workflow 判定）
// ---------------------------------------------------------------------------

/**
 * §11.3 顏色只是 presentation。blocked 是 BLOCKED（衍生或原值）專用的色調：
 * 刻意與 negative 分開，守住「BLOCKED 不得呈現成 FAIL」。
 */
export type Tone = 'positive' | 'warning' | 'negative' | 'neutral' | 'blocked'

/**
 * §11.3 一般狀態值的色調：PASS／approved／done → positive；WARN → warning；BLOCKED → blocked；
 * FAIL／rejected／failed → negative；其他（pending／waived／MANUAL／SKIP／未知）→ neutral。
 */
export function toneOf(status: string | null): Tone {
  switch (status) {
    case 'PASS':
    case 'approved':
    case 'done':
      return 'positive'
    case 'WARN':
      return 'warning'
    case 'BLOCKED':
      return 'blocked'
    case 'FAIL':
    case 'rejected':
    case 'failed':
      return 'negative'
    default:
      return 'neutral'
  }
}

/** results.verify 的顯示結果。 */
export type VerifyDisplay = {
  /** 狀態標籤，例如 `WARN（BLOCKED ×2）`；缺值為「—」。 */
  label: string
  /** 窄畫面用的短標籤（WARN＋blocked>0 時為 `BLOCKED ×n`）。 */
  short: string
  tone: Tone
  /** 衍生 BLOCKED：status == 'WARN' && blocked > 0（§11.3）。 */
  isBlocked: boolean
  blocked: number
  /** FAIL 且 blocked > 0 時的附註「另有 BLOCKED ×n」；其餘為 null。 */
  note: string | null
}

/**
 * §11.3 BLOCKED 衍生顯示：BLOCKED 不是 status 值，只在 WARN 且 blocked > 0 時顯示，且絕不呈現成 FAIL。
 * WARN 且 blocked == 0 不得出現 BLOCKED；status 真的寫成 "BLOCKED" 時照原值、警示色、不改判。
 */
export function verifyDisplay(verify: CockpitVerifyView): VerifyDisplay {
  const status = verify.status
  const blocked = verify.blocked > 0 ? verify.blocked : 0
  const plain = (label: string, tone: Tone): VerifyDisplay => ({ label, short: label, tone, isBlocked: false, blocked, note: null })
  if (status === 'PASS') {
    return plain('PASS', 'positive')
  }
  if (status === 'WARN') {
    if (blocked > 0) {
      return { label: `WARN（BLOCKED ×${blocked}）`, short: `BLOCKED ×${blocked}`, tone: 'blocked', isBlocked: true, blocked, note: null }
    }
    return plain('WARN', 'warning')
  }
  if (status === 'FAIL') {
    return { ...plain('FAIL', 'negative'), note: blocked > 0 ? TEXT.otherBlocked(blocked) : null }
  }
  if (status === 'BLOCKED') {
    return plain('BLOCKED', 'blocked')
  }
  if (status === null) {
    return plain('—', 'neutral')
  }
  return plain(status, 'neutral')
}

// ---------------------------------------------------------------------------
// 分組色帶樣式（方向 B＋C 的進度方塊）：顏色一律是 ThemeKey，深淺主題自動切換；
// 顏色永遠搭配文字，不單靠顏色傳達狀態。
// ---------------------------------------------------------------------------

/** 色調 → ThemeKey；neutral 不上色。 */
export const TONE_COLOR: Record<Tone, string | undefined> = {
  positive: 'success',
  warning: 'warning',
  negative: 'error',
  neutral: undefined,
  blocked: 'claude',
}

/** 驗收標籤顏色：沒有結果（—）用 inactive，其餘依色調。 */
export function verifyColor(display: VerifyDisplay): string | undefined {
  return display.label === '—' ? 'inactive' : TONE_COLOR[display.tone]
}

/** 核准閘顏色：approved success、rejected error、pending inactive，其他不上色。 */
export function gateColor(status: string | null): string | undefined {
  if (status === 'pending') {
    return 'inactive'
  }
  return TONE_COLOR[toneOf(status)]
}

/** Phase 顏色：規劃 planMode、實作 suggestion、驗證審查 warning、結案 success，其他 text。 */
export function phaseColor(phase: string | null): string {
  switch (phase) {
    case 'spec':
    case 'db':
    case 'arch':
      return 'planMode'
    case 'build':
    case 'fix':
      return 'suggestion'
    case 'verify':
    case 'review':
    case 'uat':
    case 'security':
      return 'warning'
    case 'close':
      return 'success'
    default:
      return 'text'
  }
}

/** type 顏色：bug error、feature planMode，其他不上色。 */
export function typeColor(type: string): string | undefined {
  return type === 'bug' ? 'error' : type === 'feature' ? 'planMode' : undefined
}

/** 停滯天數顏色：0–6 inactive、7–13 warning、≥14 error。 */
export function staleColor(days: number): string {
  return days >= 14 ? 'error' : days >= 7 ? 'warning' : 'inactive'
}

/** 停滯天數只對進行中的任務顯示；已結案、已擱置不顯示（避免「已結案卻停滯 N 天」的矛盾）。 */
export function showsStale(task: CockpitTaskView): boolean {
  return task.active
}

/** 進度方塊最多畫幾格；超過時只顯示 done/total（HUD 欄位 ≤ 60 字，§18.1）。 */
export const PROGRESS_GLYPH_MAX = 20

/** C 的進度方塊：■ 已完成（done＋skipped）、□ 未完成，格數＝實際存在的 steps（§11.1 A6）。 */
export function progressGlyphs(task: CockpitTaskView): { filled: string; empty: string; count: string } {
  const { done, total } = progressOf(task)
  const count = `${done}/${total}`
  if (total > PROGRESS_GLYPH_MAX) {
    return { filled: '', empty: '', count }
  }
  return { filled: '■'.repeat(done), empty: '□'.repeat(Math.max(0, total - done)), count }
}

const CLOCK_PATTERN = /^\d{4}-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/

/** 時間戳縮成 `MM-DD HH:mm`：直接取字串本身的欄位（不換時區）；解析不了就顯示原文前 16 字。 */
export function shortTime(value: string | null): string {
  if (value === null || value === '') {
    return '—'
  }
  const match = CLOCK_PATTERN.exec(value)
  if (match === null) {
    return clip(value, 16)
  }
  const [, month, day, hour, minute] = match
  return hour === undefined ? `${month}-${day}` : `${month}-${day} ${hour}:${minute}`
}

/** 任務 tab 的三段分組（保持 loader 的排序）。 */
export function taskGroups<T extends CockpitTaskView>(tasks: readonly T[]): { active: T[]; parked: T[]; closed: T[] } {
  return {
    active: tasks.filter(task => task.active),
    parked: tasks.filter(task => !task.closed && task.parked !== null),
    closed: tasks.filter(task => task.closed),
  }
}
