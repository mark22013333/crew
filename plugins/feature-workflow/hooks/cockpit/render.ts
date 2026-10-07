// CREW Cockpit render：Pane（總覽／任務／驗收）與 AbovePrompt HUD 的 element tree。
// 規則（§3 D-3）：純函式，只把 snapshot 轉成 element tree；不做 I/O、不碰引擎介面、不寫 state。
// 呼叫端（crew-cockpit.ts 的 ui.render hook）負責解析元素表、讀 state，
// 並把「按下按鈕要做的事」以 callback 傳進來（Mods 規定引擎介面只能出現在入口檔）。
// 所有顯示字串都取自 snapshot（loader 已依 §18.1 清理並截到 200 字）；HUD 欄位再截到 60 字。

import type { Elements, RenderElement } from 'claude-code'

import { type CockpitInvalidTask, type CockpitSnapshot, type CockpitTab, type CockpitTaskView, TEXT } from './model'
import {
  TONE_COLOR,
  type Tone,
  fillCommandFor,
  formatClock,
  gateColor,
  gateDisplay,
  healthColor,
  metricLayout,
  hudText,
  otherActiveCount,
  phaseColor,
  progressGlyphs,
  progressOf,
  resolveSelection,
  shortTime,
  showsStale,
  staleColor,
  taskGroups,
  toneOf,
  typeColor,
  verifyColor,
  verifyDisplay,
  visibleGates,
} from './selectors'

/** render 需要的元素（terminal 與 desktop 都有的 baseline，§17.1）。 */
export type CockpitKit = Pick<Elements['terminal'], 'Box' | 'Text' | 'Button'>

/** Pane 按鈕要做的事：由入口檔綁定（只改 UI state、或填入固定模板），render 只負責接線。 */
export type PaneCallbacks = {
  selectTab: (tab: CockpitTab) => void | Promise<void>
  selectTask: (id: string) => void | Promise<void>
  refresh: () => void | Promise<void>
  /** 以 task id 觸發 Fill；入口檔自行以 fillCommandFor 重算內容，不吃 render 給的字串。 */
  fill: (id: string) => void | Promise<void>
  /** 任務 tab「已結案」分組展開／收合（只改 UI state）。 */
  toggleClosed: () => void | Promise<void>
}

export type PaneData = {
  snapshot: CockpitSnapshot | null
  /** state 的 selectedSlug（使用者本 session 的選擇）。 */
  selectedSlug: string | null
  tab: CockpitTab
  /** e.props.bodyColumns（§17.2，不假設固定寬度）。 */
  bodyColumns: number
  /** 任務 tab「已結案」分組是否展開（runtime.isClosedExpanded）。 */
  isClosedExpanded: boolean
}

export type HudData = {
  snapshot: CockpitSnapshot | null
  selectedSlug: string | null
  /** e.props.bodyColumns；< 60 退成 1 行（§9.1）。 */
  bodyColumns: number
}

/** Tasks tab 最多顯示幾筆（§12）。 */
export const TASK_ROW_LIMIT = 50

/** HUD 窄畫面門檻（§9.1）。 */
export const HUD_COMPACT_COLUMNS = 60

/** Pane 窄畫面門檻：低於此寬度，Tasks 列改成上下兩行。 */
export const PANE_COMPACT_COLUMNS = 60

/** resume_hint 陣列最多顯示幾項（§11）。 */
const HINT_ITEMS = 3

/** IR 的 AC 清單最多列幾筆，避免 pane 過長（§13）。 */
const IR_AC_LIMIT = 20

/** 總覽「另有 N 個進行中」最多列幾個 slug。 */
const OTHER_ACTIVE_LIMIT = 5

/** 已結案分組收合時顯示幾筆（依 loader 既有排序，最近更新在前）。 */
export const CLOSED_PREVIEW = 5

const STEP_GLYPH: Record<string, string> = {
  done: '✓',
  skipped: '–',
  in_progress: '●',
  pending: '○',
  failed: '✗',
}

type Child = RenderElement | string | null | undefined | false

/** h 的薄包裝：濾掉 null／false 子節點（JSX 的條件渲染語意）。 */
function el(tag: unknown, props: Record<string, unknown>, ...children: Child[]): RenderElement {
  const kept = children.filter((child): child is RenderElement | string => child !== null && child !== undefined && child !== false)
  return h(tag as never, props, ...kept) as RenderElement
}

/** 一行文字；tone 決定顏色（§11.3），neutral 不上色。 */
function line(kit: CockpitKit, text: string, tone: Tone = 'neutral', extra: Record<string, unknown> = {}): RenderElement {
  return colored(kit, text, TONE_COLOR[tone], extra)
}

/** 指定 ThemeKey 的文字；color 為 undefined 時不傳 color（不支援的 prop 不傳）。 */
function colored(kit: CockpitKit, text: string, color: string | undefined, extra: Record<string, unknown> = {}): RenderElement {
  return el(kit.Text, { ...(color !== undefined && { color }), ...extra }, text)
}

const dim = (kit: CockpitKit, text: string): RenderElement => el(kit.Text, { dimColor: true }, text)

const heading = (kit: CockpitKit, text: string): RenderElement => el(kit.Text, { bold: true }, text)

const column = (kit: CockpitKit, props: Record<string, unknown>, ...children: Child[]): RenderElement =>
  el(kit.Box, { flexDirection: 'column', ...props }, ...children)

const row = (kit: CockpitKit, ...children: Child[]): RenderElement => el(kit.Box, { flexDirection: 'row', flexWrap: 'wrap' }, ...children)

const section = (kit: CockpitKit, title: string, ...children: Child[]): RenderElement =>
  column(kit, { marginTop: 1 }, heading(kit, title), ...children)

/** 列表最多 n 項，其餘以「＋N」表示（§11 resume_hint）。 */
function limited(items: readonly string[], n: number): string {
  const shown = items.slice(0, n).join(', ')
  return items.length > n ? `${shown} ＋${items.length - n}` : shown
}

const schemaText = (task: CockpitTaskView): string =>
  task.schemaVersion === null ? TEXT.schemaUnknown : TEXT.schema(task.schemaVersion)

/** 結果狀態顏色：缺值（—）inactive，其餘依 §11.3 色調。 */
const statusColor = (status: string | null): string | undefined => (status === null ? 'inactive' : TONE_COLOR[toneOf(status)])

const staleText = (task: CockpitTaskView): string => TEXT.stale(task.staleDays) + (task.staleUnknown ? TEXT.staleUnknown : '')

/** 進度方塊（■ success、□ inactive）＋ done/total；超過格數上限只顯示計數。 */
function progressBar(kit: CockpitKit, task: CockpitTaskView, withCount: boolean): RenderElement[] {
  const glyphs = progressGlyphs(task)
  return [
    glyphs.filled !== '' ? colored(kit, glyphs.filled, 'success') : null,
    glyphs.empty !== '' ? colored(kit, glyphs.empty, 'inactive') : null,
    withCount || (glyphs.filled === '' && glyphs.empty === '') ? el(kit.Text, { dimColor: true }, `${glyphs.filled !== '' || glyphs.empty !== '' ? ' ' : ''}${glyphs.count}`) : null,
  ].filter((part): part is RenderElement => part !== null)
}

// ---------------------------------------------------------------------------
// Pane
// ---------------------------------------------------------------------------

/** Pane 主體（§10）：tab 列＋目前 tab 的內容＋載入時間。 */
export function paneView(kit: CockpitKit, data: PaneData, cb: PaneCallbacks): RenderElement {
  const { snapshot } = data
  if (
    snapshot === null ||
    snapshot.repoRoot === null ||
    (snapshot.tasks.length === 0 && snapshot.invalidTasks.length === 0 && snapshot.untrackedDirCount === 0)
  ) {
    // §16：載入錯誤（例如 .spec 列不出來）必須看得到，不能被「沒有任務」蓋掉
    const errors = snapshot?.errors ?? []
    return column(
      kit,
      {},
      errors.length > 0 ? heading(kit, TEXT.loadErrors) : el(kit.Text, {}, TEXT.noTasks),
      errors.length > 0 ? errorRows(kit, errors) : dim(kit, TEXT.noTasksHint),
      el(kit.Box, { marginTop: 1 }, el(kit.Button, { key: 'refresh', label: TEXT.refresh, hotkey: 'r', onPress: () => cb.refresh() })),
    )
  }

  const tabs: readonly { tab: CockpitTab; label: string; hotkey: string }[] = [
    { tab: 'overview', label: TEXT.tabOverview, hotkey: '1' },
    { tab: 'tasks', label: TEXT.tabTasks, hotkey: '2' },
    { tab: 'verify', label: TEXT.tabVerify, hotkey: '3' },
  ]
  const tabBar = el(
    kit.Box,
    { flexDirection: 'row', flexWrap: 'wrap', gap: 1 },
    ...tabs.map(item =>
      el(kit.Button, {
        key: `tab-${item.tab}`,
        label: item.label,
        hotkey: item.hotkey,
        ...(item.tab === data.tab && { variant: 'primary' }),
        onPress: () => cb.selectTab(item.tab),
      }),
    ),
    el(kit.Button, { key: 'refresh', label: TEXT.refresh, hotkey: 'r', onPress: () => cb.refresh() }),
  )

  const selection = resolveSelection(snapshot, data.selectedSlug)
  const body =
    data.tab === 'tasks'
      ? tasksView(kit, snapshot, selection.task, data.bodyColumns, data.isClosedExpanded, cb)
      : data.tab === 'verify'
        ? verifyView(kit, selection.task)
        : overviewView(kit, snapshot, selection, data.bodyColumns, cb)

  return column(
    kit,
    {},
    tabBar,
    body,
    snapshot.errors.length > 0 && section(kit, TEXT.loadErrors, errorRows(kit, snapshot.errors)),
    el(kit.Box, { marginTop: 1 }, dim(kit, TEXT.loadedAt(formatClock(snapshot.loadedAt)))),
  )
}

/** 載入錯誤列（path 與 message 已由 loader 依 §18.1 清理），警示色。 */
function errorRows(kit: CockpitKit, errors: CockpitSnapshot['errors']): RenderElement {
  return column(kit, {}, ...errors.map(error => line(kit, `${error.path ?? error.scope} · ${error.message}`, 'warning')))
}

/** 膠囊：底色＋對比文字（ThemeKey），文字本身說明內容。 */
function capsule(kit: CockpitKit, text: string, backgroundColor: string): RenderElement {
  return el(kit.Text, { backgroundColor, color: 'inverseText', bold: true }, ` ${text} `)
}

/** 圓角框：框色依語意（ThemeKey）。 */
function card(kit: CockpitKit, props: Record<string, unknown>, ...children: Child[]): RenderElement {
  return el(kit.Box, { flexDirection: 'column', borderStyle: 'round', paddingX: 1, ...props }, ...children)
}

/** 指標方塊內的大字（terminal 沒有字級，以粗體表示）。 */
const big = (kit: CockpitKit, text: string, color: string | undefined): RenderElement => colored(kit, text, color, { bold: true })

/** step 膠囊：done／skipped success、目前 phase 或 in_progress suggestion、failed error、其他（pending）低調無底色。 */
function stepCapsule(kit: CockpitKit, task: CockpitTaskView, step: CockpitTaskView['steps'][number]): RenderElement {
  const status = step.status ?? ''
  if (status === 'done' || status === 'skipped') {
    return capsule(kit, `${STEP_GLYPH[status]} ${step.key}`, 'success')
  }
  if (status === 'failed') {
    return capsule(kit, `${STEP_GLYPH.failed} ${step.key}`, 'error')
  }
  if (step.key === task.phase || status === 'in_progress') {
    return capsule(kit, `${STEP_GLYPH.in_progress} ${step.key}`, 'suggestion')
  }
  return el(kit.Text, { dimColor: true }, ` ${STEP_GLYPH[status] ?? '?'} ${step.key} `)
}

/** 指標方塊：進度。 */
function progressMetric(kit: CockpitKit, task: CockpitTaskView): Child[] {
  const progress = progressOf(task)
  const state = task.closed ? TEXT.closedTask : task.parked !== null ? `${task.phase ?? '—'} · ${TEXT.parked}` : TEXT.phaseInProgress(task.phase ?? '—')
  return [
    big(kit, `${progress.done} / ${progress.total}`, undefined),
    row(kit, ...progressBar(kit, task, false)),
    colored(kit, state, phaseColor(task.phase)),
  ]
}

/** 指標方塊：驗收（verify／review／security，BLOCKED 衍生規則沿用 verifyDisplay）。 */
function verifyMetric(kit: CockpitKit, task: CockpitTaskView): Child[] {
  const verify = verifyDisplay(task.results.verify)
  return [
    row(kit, colored(kit, `verify    ${verify.label}`, verifyColor(verify)), verify.note !== null && line(kit, ` · ${verify.note}`, 'blocked')),
    colored(kit, `review    ${task.results.review.status ?? '—'}`, statusColor(task.results.review.status)),
    colored(kit, `security  ${task.results.security.status ?? '—'}`, statusColor(task.results.security.status)),
  ]
}

/** 指標方塊：核准閘（依 type 篩選；v1 無 gates 只顯示「—」，不顯示 pending，規格 A2）。 */
function gateMetric(kit: CockpitKit, task: CockpitTaskView): Child[] {
  const gates = visibleGates(task)
  if (gates === null) {
    return [big(kit, TEXT.gatesNone, 'inactive'), dim(kit, TEXT.v1NoGates)]
  }
  if (gates.length === 0) {
    return [big(kit, TEXT.gatesNone, 'inactive')]
  }
  return gates.map(gate => {
    const shown = gateDisplay(gate)
    return colored(kit, shown.text, shown.color)
  })
}

/** 指標方塊：停滯（只對進行中）；已結案／已擱置改顯示狀態文字。 */
function staleMetric(kit: CockpitKit, task: CockpitTaskView): Child[] {
  const updated = dim(kit, TEXT.lastUpdated(shortTime(task.updated)))
  if (task.closed) {
    return [colored(kit, `○ ${TEXT.closedTask}`, 'inactive', { bold: true }), updated]
  }
  if (task.parked !== null) {
    return [colored(kit, `◐ ${TEXT.parked}`, 'merged', { bold: true }), updated]
  }
  return [
    big(kit, TEXT.staleDaysBig(task.staleDays), staleColor(task.staleDays)),
    task.staleUnknown && dim(kit, TEXT.staleUnknown),
    updated,
  ]
}

/** 方塊框色：進度依 phase、驗收依驗收結果、核准閘依最差的 gate、停滯依天數／狀態。 */
function gateBoxColor(task: CockpitTaskView): string {
  const gates = visibleGates(task) ?? []
  if (gates.some(gate => gate.status === 'rejected')) {
    return 'error'
  }
  if (gates.length > 0 && gates.every(gate => gate.status === 'approved')) {
    return 'success'
  }
  return 'inactive'
}

/** 四個等寬指標方塊；寬度不足時折成 2×2，再窄單欄堆疊（依 bodyColumns）。 */
function metricRows(kit: CockpitKit, task: CockpitTaskView, bodyColumns: number): RenderElement[] {
  const layout = metricLayout(bodyColumns)
  const verify = verifyDisplay(task.results.verify)
  const metrics: { key: string; title: string; color: string | undefined; body: Child[] }[] = [
    { key: 'progress', title: TEXT.progress, color: phaseColor(task.phase), body: progressMetric(kit, task) },
    { key: 'verify', title: TEXT.verifyBox, color: verifyColor(verify) ?? 'inactive', body: verifyMetric(kit, task) },
    { key: 'gates', title: TEXT.approval, color: gateBoxColor(task), body: gateMetric(kit, task) },
    {
      key: 'stale',
      title: task.active ? TEXT.staleBox : TEXT.statusBox,
      color: task.closed ? 'inactive' : task.parked !== null ? 'merged' : staleColor(task.staleDays),
      body: staleMetric(kit, task),
    },
  ]
  const rows: RenderElement[] = []
  for (let start = 0; start < metrics.length; start += layout.perRow) {
    rows.push(
      el(
        kit.Box,
        { key: `metric-row-${start / layout.perRow}`, flexDirection: 'row', gap: 1, marginTop: 1 },
        ...metrics
          .slice(start, start + layout.perRow)
          .map(metric =>
            card(kit, { key: `metric-${metric.key}`, width: layout.width, ...(metric.color !== undefined && { borderColor: metric.color }) }, dim(kit, metric.title), ...metric.body),
          ),
      ),
    )
  }
  return rows
}

/** §11 Overview（儀表板）：標題卡 → 指標方塊 → 步驟流程 → 工作單元警示 → 上次建議＋Fill → 其他進行中。 */
function overviewView(
  kit: CockpitKit,
  snapshot: CockpitSnapshot,
  selection: ReturnType<typeof resolveSelection>,
  bodyColumns: number,
  cb: PaneCallbacks,
): RenderElement {
  const task = selection.task
  if (task === null) {
    return column(kit, { marginTop: 1 }, el(kit.Text, {}, TEXT.noSelection))
  }

  // 1. 標題卡：slug＋右側膠囊（type、phase、停滯）；名稱；schema 與 branch（取自 state.git）
  const typeBg = typeColor(task.type) ?? 'inactive'
  const titleCard = card(
    kit,
    { key: 'title-card', marginTop: 1, borderColor: healthColor(task) },
    el(
      kit.Box,
      { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', gap: 1 },
      row(kit, el(kit.Text, { bold: true }, task.slug), selection.autoSelected && dim(kit, `  （${TEXT.autoSelected}）`)),
      el(
        kit.Box,
        { flexDirection: 'row', flexWrap: 'wrap', gap: 1 },
        capsule(kit, task.type, typeBg),
        capsule(kit, task.phase ?? '—', phaseColor(task.phase)),
        showsStale(task) && capsule(kit, staleText(task), staleColor(task.staleDays)),
      ),
    ),
    task.name !== task.slug && dim(kit, task.name),
    task.parked !== null && colored(kit, `◐ ${TEXT.parked}${task.parked.reason !== null ? `：${task.parked.reason}` : ''}`, 'merged'),
    task.inferred && line(kit, TEXT.inferred, 'warning'),
    task.isSchemaNewer && task.schemaVersion !== null && line(kit, TEXT.schemaNewer(task.schemaVersion), 'warning'),
    dim(kit, [schemaText(task), task.branch !== null ? `branch: ${task.branch} ${TEXT.branchNote}` : null].filter(part => part !== null).join(' · ')),
  )

  // 3. 步驟流程：每個實際存在的 step 一顆膠囊（不寫死步數）
  const steps = el(kit.Box, { key: 'steps', flexDirection: 'row', flexWrap: 'wrap', gap: 1, marginTop: 1 }, ...task.steps.map(step => stepCapsule(kit, task, step)))

  // 4. 工作單元警示：只在中斷（total > 0 且 done < total）時出現；完成或空的不顯示（§11、A8）
  const unit = task.workUnit
  const hint = task.resumeHint
  const hintParts =
    hint === null || hint.isEmpty
      ? []
      : [
          hint.branch !== null ? `branch: ${hint.branch}` : null,
          hint.services.length > 0 ? `${TEXT.services}: ${limited(hint.services, HINT_ITEMS)}` : null,
          hint.readFirst.length > 0 ? `${TEXT.readFirst}: ${limited(hint.readFirst, HINT_ITEMS)}` : null,
        ].filter((part): part is string => part !== null)
  const unitAlert =
    unit !== null &&
    unit.isInterrupted &&
    card(
      kit,
      { key: 'work-unit', marginTop: 1, borderColor: 'warning' },
      line(kit, `${TEXT.workUnitInterrupted(unit.done, unit.total)}${unit.label !== '' ? ` · ${unit.label}` : ''}`, 'warning'),
      hintParts.length > 0 && el(kit.Text, {}, `${TEXT.resumeHint}   ${hintParts.join(' · ')}`),
    )

  // 5. 上次建議（快照）＋Fill（行為不變：只填 /plan-next {slug}）
  const fill = fillCommandFor(task)
  const recorded = task.recordedNext
  const footer = column(
    kit,
    { marginTop: 1 },
    recorded !== null &&
      row(kit, dim(kit, `${TEXT.recordedNextSnapshot} `), recorded.command !== null && el(kit.Text, {}, recorded.command)),
    recorded !== null && recorded.reason !== '' && dim(kit, recorded.reason),
    el(
      kit.Box,
      { marginTop: recorded !== null ? 1 : 0, flexDirection: 'row', flexWrap: 'wrap', gap: 1 },
      fill !== null
        ? el(kit.Button, { key: 'fill', label: TEXT.fill(task.slug), variant: 'primary', hotkey: 'f', onPress: () => cb.fill(task.id) })
        : line(kit, TEXT.slugNotFillable, 'warning'),
    ),
  )

  // 6. 其他進行中任務：一行摘要，按 slug 只切換 selected（UI state）
  const others = snapshot.tasks.map((item, index) => ({ item, index })).filter(({ item }) => item.active && item.id !== task.id)
  const shownOthers = others.slice(0, OTHER_ACTIVE_LIMIT)
  const othersLine =
    others.length > 0 &&
    el(
      kit.Box,
      { key: 'others', flexDirection: 'row', flexWrap: 'wrap', gap: 1, marginTop: 1 },
      dim(kit, TEXT.otherActiveList(others.length)),
      ...shownOthers.map(({ item, index }) =>
        el(kit.Button, {
          // key 用序號，不用目錄名（目錄名是不可信的 repo 字串）
          key: `other-${index}`,
          label: TEXT.otherActiveItem(item.slug, item.staleDays),
          plain: true,
          onPress: () => cb.selectTask(item.id),
        }),
      ),
      others.length > OTHER_ACTIVE_LIMIT && dim(kit, TEXT.moreItems(others.length - OTHER_ACTIVE_LIMIT)),
    )

  return column(kit, {}, titleCard, ...metricRows(kit, task, bodyColumns), steps, unitAlert, footer, othersLine)
}

/** 任務列屬於哪一段：決定欄位與樣式。 */
type TaskGroup = 'active' | 'parked' | 'closed'

/** 分組色帶：整列底色＋對比文字（ThemeKey，深淺主題自動切換），文字本身就說明狀態。 */
function groupBand(kit: CockpitKit, text: string, backgroundColor: string, ...extra: Child[]): RenderElement {
  return el(
    kit.Box,
    { flexDirection: 'row', flexWrap: 'wrap', marginTop: 1, backgroundColor, gap: 1 },
    el(kit.Text, { color: 'inverseText', bold: true }, ` ${text} `),
    ...extra,
  )
}

/**
 * 一列任務。進行中：▶ slug、type、phase、進度方塊、驗收、停滯天數、時間；
 * 已擱置：同上但不顯示停滯天數、加「已擱置」標記；已結案：整列 dim（驗收結果仍上色）、不顯示停滯天數。
 */
function taskRow(
  kit: CockpitKit,
  task: CockpitTaskView,
  index: number,
  group: TaskGroup,
  isSelected: boolean,
  isCompact: boolean,
  cb: PaneCallbacks,
): RenderElement {
  const isClosed = group === 'closed'
  const verify = verifyDisplay(task.results.verify)
  // 已結案整列降成 dim；只有驗收結果維持語意色（WARN／FAIL 不漏看）
  const tint = (text: string, color: string | undefined): RenderElement =>
    isClosed ? el(kit.Text, { dimColor: true }, text) : colored(kit, text, color)
  const sep = (): RenderElement => el(kit.Text, { dimColor: true }, ' · ')
  const button = el(kit.Button, {
    // key 用序號，不用目錄名（目錄名是不可信的 repo 字串）
    key: `task-${index}`,
    label: `${isSelected ? `${TEXT.selected} ` : ''}${task.slug}`,
    ...(isSelected && { variant: 'primary' }),
    ...(isClosed && !isSelected && { dimColor: true }),
    onPress: () => cb.selectTask(task.id),
  })
  const info = row(
    kit,
    isCompact ? null : el(kit.Text, {}, ' '),
    tint(task.type, typeColor(task.type)),
    sep(),
    tint(task.phase ?? '—', phaseColor(task.phase)),
    group === 'parked' && sep(),
    group === 'parked' && colored(kit, TEXT.parked, 'merged'),
    isClosed && sep(),
    isClosed && el(kit.Text, { dimColor: true }, TEXT.closedTask),
    !isClosed && sep(),
    ...(isClosed ? [] : progressBar(kit, task, true)),
    sep(),
    el(kit.Text, { dimColor: isClosed }, `${TEXT.verifyLabel} `),
    colored(kit, verify.label, verifyColor(verify)),
    showsStale(task) && sep(),
    showsStale(task) && colored(kit, staleText(task), staleColor(task.staleDays), { bold: task.staleDays >= 14 }),
    sep(),
    el(kit.Text, { dimColor: true }, shortTime(task.updated)),
  )
  const props = isSelected ? { backgroundColor: 'subtle' } : {}
  return isCompact ? column(kit, props, button, info) : el(kit.Box, { flexDirection: 'row', flexWrap: 'wrap', ...props }, button, info)
}

/**
 * §12 Tasks（方向 B 分組色帶）：● 進行中 → ◐ 已擱置 → ○ 已結案（loader 已排序），最多 50 筆；
 * 已結案預設只顯示最近 5 筆，按 e 展開；壞檔列 invalid row；底部列缺 state.json 的目錄數。
 */
function tasksView(
  kit: CockpitKit,
  snapshot: CockpitSnapshot,
  selected: CockpitTaskView | null,
  bodyColumns: number,
  isClosedExpanded: boolean,
  cb: PaneCallbacks,
): RenderElement {
  const isCompact = bodyColumns < PANE_COMPACT_COLUMNS
  const shown = snapshot.tasks.slice(0, TASK_ROW_LIMIT).map((task, index) => ({ task, index }))
  const groups = taskGroups(snapshot.tasks)
  const isSelected = (task: CockpitTaskView) => selected !== null && selected.id === task.id
  const rowsOf = (group: TaskGroup, items: readonly { task: CockpitTaskView; index: number }[]) =>
    items.map(({ task, index }) => taskRow(kit, task, index, group, isSelected(task), isCompact, cb))

  const activeRows = shown.filter(({ task }) => task.active)
  const parkedRows = shown.filter(({ task }) => !task.closed && task.parked !== null)
  const closedRows = shown.filter(({ task }) => task.closed)
  const closedVisible = isClosedExpanded ? closedRows : closedRows.slice(0, CLOSED_PREVIEW)

  // 結案摘要（借 C）：WARN／FAIL 不漏看，也不會誤以為要處理
  const countBy = (status: string) => groups.closed.filter(task => task.results.verify.status === status).length
  const closedNotes = [
    countBy('WARN') > 0 ? TEXT.closedVerifyCount(countBy('WARN'), 'WARN') : null,
    countBy('FAIL') > 0 ? TEXT.closedVerifyCount(countBy('FAIL'), 'FAIL') : null,
    closedRows.length > CLOSED_PREVIEW && !isClosedExpanded ? TEXT.closedRecent(CLOSED_PREVIEW) : null,
  ].filter((note): note is string => note !== null)
  const closedToggle =
    closedRows.length > CLOSED_PREVIEW &&
    el(kit.Button, {
      key: 'toggle-closed',
      label: isClosedExpanded ? TEXT.collapseClosed : TEXT.expandClosed,
      hotkey: 'e',
      plain: true,
      onPress: () => cb.toggleClosed(),
    })

  return column(
    kit,
    {},
    groupBand(kit, TEXT.groupActive(groups.active.length), 'suggestion'),
    ...rowsOf('active', activeRows),
    // 已擱置為 0：只顯示色帶，不顯示空列
    groupBand(kit, TEXT.groupParked(groups.parked.length), 'merged'),
    ...rowsOf('parked', parkedRows),
    groupBand(kit, [TEXT.groupClosed(groups.closed.length), ...closedNotes].join(' · '), 'inactive', closedToggle),
    ...rowsOf('closed', closedVisible),
    snapshot.tasks.length > TASK_ROW_LIMIT && dim(kit, TEXT.tasksTruncated(TASK_ROW_LIMIT)),
    ...snapshot.invalidTasks.map(invalid => invalidRow(kit, invalid)),
    snapshot.untrackedDirCount > 0 && el(kit.Box, { marginTop: 1 }, dim(kit, TEXT.untracked(snapshot.untrackedDirCount))),
  )
}

function invalidRow(kit: CockpitKit, invalid: CockpitInvalidTask): RenderElement {
  return column(
    kit,
    { marginTop: 1 },
    colored(kit, `${TEXT.invalidMark} ${invalid.slug} · ${TEXT.invalidState}`, 'error', { bold: true }),
    dim(kit, `${invalid.statePath} · ${invalid.message}（${TEXT.invalidStateNote}）`),
  )
}

/** §13 Verify：Runtime Verify（含 BLOCKED 衍生顯示）＋Verification IR 摘要＋語意分隔。 */
function verifyView(kit: CockpitKit, task: CockpitTaskView | null): RenderElement {
  if (task === null) {
    return column(kit, { marginTop: 1 }, el(kit.Text, {}, TEXT.noSelection), el(kit.Text, { bold: true }, TEXT.truthSeparator))
  }

  const verify = verifyDisplay(task.results.verify)
  const runtime: Child[] = task.results.verify.isEmpty
    ? [dim(kit, TEXT.noVerifyResult)]
    : [
        row(kit, el(kit.Text, {}, 'status  '), colored(kit, verify.label, verifyColor(verify)), verify.note !== null && line(kit, ` · ${verify.note}`, 'blocked')),
        ...task.results.verify.entries.map(entry => el(kit.Text, {}, `${entry.key}  ${entry.value}`)),
        verify.isBlocked && line(kit, TEXT.blockedNote(verify.blocked), 'blocked'),
      ]

  const ir = task.verificationIr
  const irRows: Child[] =
    ir.status === 'missing'
      ? [dim(kit, `IR  ${TEXT.irMissing}`)]
      : ir.status === 'invalid'
        ? [...TEXT.irInvalidHint.split('\n').map(text => line(kit, text, 'warning')), dim(kit, ir.message)]
        : [
            line(kit, `IR  ${TEXT.irReady}`, 'positive'),
            el(kit.Text, {}, `ACs  ${ir.acCount}`),
            el(kit.Text, {}, `Routes  ${ir.routes.map(route => `${route.verificationType ?? TEXT.irUntyped} ${route.count}`).join(' · ') || '—'}`),
            el(kit.Text, {}, `Preconditions  ${ir.preconditionCount}`),
            el(kit.Text, {}, `Safety  ${ir.safetyCount}`),
            ...ir.acs.slice(0, IR_AC_LIMIT).map(ac => dim(kit, `${ac.id}  ${ac.verificationType ?? TEXT.irUntyped}`)),
            ir.acs.length > IR_AC_LIMIT && dim(kit, `＋${ir.acs.length - IR_AC_LIMIT}`),
          ]

  return column(
    kit,
    { marginTop: 1 },
    el(kit.Text, { bold: true }, task.slug),
    section(kit, TEXT.runtimeVerify, ...runtime),
    section(kit, TEXT.verificationIr, ...irRows),
    el(kit.Box, { marginTop: 1 }, el(kit.Text, { bold: true }, TEXT.truthSeparator)),
  )
}

// ---------------------------------------------------------------------------
// AbovePrompt HUD（§9）
// ---------------------------------------------------------------------------

/**
 * HUD 一行的片段：text 與樣式。color／backgroundColor 一律是 ThemeKey；
 * tone 是 §11.3 的語意色調（color 未指定時套用）。
 */
export type HudSegment = { text: string; tone: Tone; color?: string; backgroundColor?: string; bold?: boolean; dim?: boolean }

/**
 * HUD 的內容（純資料）：沒有 active task 或沒有選取時回 null（§9.1：不佔空間）。
 * 寬畫面最多 2 行：CREW 色塊 → slug → type／phase（上色）→ 進度方塊 → 中斷 → 驗收 → 停滯天數（上色，只對進行中）
 * → ＋N 個進行中；第二行 UAT、上次建議（dim）、載入時間、權威入口。bodyColumns < 60 退成 1 行。
 * state.next 一律標「上次建議」，不是現況（§6.3）。不顯示 ci-ready（§9.3、AC-11）。
 */
export function hudModel(data: HudData): HudSegment[][] | null {
  const { snapshot } = data
  if (snapshot === null || snapshot.activeCount === 0) {
    return null
  }
  const task = resolveSelection(snapshot, data.selectedSlug).task
  if (task === null) {
    return null
  }
  const others = otherActiveCount(snapshot, task)
  const verify = verifyDisplay(task.results.verify)
  const hasVerify = task.results.verify.status !== null
  const seg = (text: string, tone: Tone = 'neutral', style: Omit<HudSegment, 'text' | 'tone'> = {}): HudSegment => ({ text, tone, ...style })
  const sep = seg(' · ')
  const slug = hudText(task.slug)
  const phase = hudText(task.phase ?? '—')
  const chip = seg(TEXT.paneTitle, 'neutral', { backgroundColor: 'suggestion', color: 'inverseText', bold: true })
  const phaseSeg = seg(phase, 'neutral', { color: phaseColor(task.phase) })
  const verifySeg = seg(hudText(verify.short), verify.tone, { color: verifyColor(verify) })

  if (data.bodyColumns < HUD_COMPACT_COLUMNS) {
    return [
      [
        chip,
        sep,
        seg(slug, 'neutral', { bold: true }),
        sep,
        phaseSeg,
        ...(hasVerify ? [sep, verifySeg] : []),
        ...(others > 0 ? [seg(` · ＋${others}`, 'neutral', { color: 'suggestion' })] : []),
      ],
    ]
  }

  const unit = task.workUnit
  const glyphs = progressGlyphs(task)
  const hasGlyphs = glyphs.filled !== '' || glyphs.empty !== ''
  const typeTone = typeColor(task.type)
  const first: HudSegment[] = [
    chip,
    sep,
    seg(slug, 'neutral', { bold: true }),
    sep,
    seg(hudText(task.type), 'neutral', typeTone !== undefined ? { color: typeTone } : {}),
    seg(' / '),
    phaseSeg,
    sep,
    ...(hasGlyphs
      ? [
          ...(glyphs.filled !== '' ? [seg(glyphs.filled, 'neutral', { color: 'success' })] : []),
          ...(glyphs.empty !== '' ? [seg(glyphs.empty, 'neutral', { color: 'inactive' })] : []),
        ]
      : [seg(glyphs.count, 'neutral', { dim: true })]),
    ...(unit !== null && unit.isInterrupted ? [seg(` · ${TEXT.interrupted(unit.done, unit.total)}`, 'warning')] : []),
    ...(hasVerify ? [seg(` · ${TEXT.verifyLabel} `), seg(hudText(verify.label), verify.tone, { color: verifyColor(verify) })] : []),
    ...(verify.note !== null ? [seg(` · ${verify.note}`, 'blocked')] : []),
    ...(showsStale(task) ? [sep, seg(TEXT.stale(task.staleDays), 'neutral', { color: staleColor(task.staleDays) })] : []),
    ...(others > 0 ? [sep, seg(TEXT.otherActive(others), 'neutral', { color: 'suggestion' })] : []),
    ...(task.inferred ? [seg(` · ${TEXT.inferredShort}`, 'warning')] : []),
  ]

  const uat = (visibleGates(task) ?? []).find(gate => gate.key === 'uat')
  const recorded = task.recordedNext?.command ?? null
  const fill = fillCommandFor(task)
  const parts: HudSegment[] = [
    ...(uat !== undefined
      ? [seg(uat.status === 'pending' ? TEXT.uatPendingShort : `UAT ${hudText(uat.status ?? '—')}`, 'neutral', { color: gateColor(uat.status) ?? 'text' })]
      : []),
    ...(recorded !== null ? [seg(`${TEXT.recordedNextShort} ${hudText(recorded)}`, 'neutral', { dim: true })] : []),
    seg(TEXT.loadedAt(formatClock(snapshot.loadedAt)), 'neutral', { dim: true }),
    ...(fill !== null ? [seg(fill)] : []),
  ]
  const second = parts.flatMap((part, index) => (index === 0 ? [part] : [seg(' · ', 'neutral', { dim: true }), part]))

  return [first, second]
}

/** HUD 片段轉成 element（每行一個 row Box，單行截斷）。 */
export function hudView(kit: CockpitKit, lines: readonly HudSegment[][]): RenderElement {
  return column(
    kit,
    {},
    ...lines.map(segments =>
      el(
        kit.Box,
        { flexDirection: 'row' },
        ...segments.map(segment =>
          colored(kit, segment.text, segment.color ?? TONE_COLOR[segment.tone], {
            wrap: 'truncate-end',
            ...(segment.backgroundColor !== undefined && { backgroundColor: segment.backgroundColor }),
            ...(segment.bold === true && { bold: true }),
            ...(segment.dim === true && { dimColor: true }),
          }),
        ),
      ),
    ),
  )
}

/**
 * §9.2 Composition：AbovePrompt 是共享 band，保留其他 mod 經 next(e) 畫出的內容，再接上 HUD。
 * other 為 null／undefined（沒有其他內容）時只畫 HUD。
 */
export function composeBand(kit: CockpitKit, other: RenderElement | null | undefined, own: RenderElement): RenderElement {
  return other === null || other === undefined ? own : column(kit, {}, other, own)
}
