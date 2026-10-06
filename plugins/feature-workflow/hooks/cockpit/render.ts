// CREW Cockpit render：Pane（總覽／任務／驗收）與 AbovePrompt HUD 的 element tree。
// 規則（§3 D-3）：純函式，只把 snapshot 轉成 element tree；不做 I/O、不碰引擎介面、不寫 state。
// 呼叫端（crew-cockpit.ts 的 ui.render hook）負責解析元素表、讀 state，
// 並把「按下按鈕要做的事」以 callback 傳進來（Mods 規定引擎介面只能出現在入口檔）。
// 所有顯示字串都取自 snapshot（loader 已依 §18.1 清理並截到 200 字）；HUD 欄位再截到 60 字。

import type { Elements, RenderElement } from 'claude-code'

import { type CockpitInvalidTask, type CockpitSnapshot, type CockpitTab, type CockpitTaskView, TEXT } from './model'
import {
  type Tone,
  fillCommandFor,
  formatClock,
  hudText,
  otherActiveCount,
  progressOf,
  resolveSelection,
  toneOf,
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
}

export type PaneData = {
  snapshot: CockpitSnapshot | null
  /** state 的 selectedSlug（使用者本 session 的選擇）。 */
  selectedSlug: string | null
  tab: CockpitTab
  /** e.props.bodyColumns（§17.2，不假設固定寬度）。 */
  bodyColumns: number
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

const TONE_COLOR: Record<Tone, string | undefined> = {
  positive: 'success',
  warning: 'warning',
  negative: 'error',
  neutral: undefined,
}

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
  const color = TONE_COLOR[tone]
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

const staleText = (task: CockpitTaskView): string => TEXT.stale(task.staleDays) + (task.staleUnknown ? TEXT.staleUnknown : '')

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
      ? tasksView(kit, snapshot, selection.task, data.bodyColumns, cb)
      : data.tab === 'verify'
        ? verifyView(kit, selection.task)
        : overviewView(kit, snapshot, selection, cb)

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

/** §11 Overview：目前任務的 phase／進度／核准閘／結果／工作單元／上次建議／Fill。 */
function overviewView(
  kit: CockpitKit,
  snapshot: CockpitSnapshot,
  selection: ReturnType<typeof resolveSelection>,
  cb: PaneCallbacks,
): RenderElement {
  const task = selection.task
  if (task === null) {
    return column(kit, { marginTop: 1 }, el(kit.Text, {}, TEXT.noSelection))
  }

  const others = otherActiveCount(snapshot, task)
  const headNotes = [selection.autoSelected ? TEXT.autoSelected : null, others > 0 ? `另有 ${others} 個進行中` : null].filter(
    (note): note is string => note !== null,
  )

  const progress = progressOf(task)
  const stepsText = task.steps.map(step => `${step.key} ${STEP_GLYPH[step.status ?? ''] ?? '?'}`).join('  ')

  const gates = visibleGates(task)
  const gateRows =
    gates === null
      ? [dim(kit, TEXT.v1NoGates)]
      : gates.map(gate => line(kit, `${gate.key.padEnd(13)} ${gate.status ?? '—'}`, toneOf(gate.status)))

  const verify = verifyDisplay(task.results.verify)
  const resultRows = [
    line(kit, `security  ${task.results.security.status ?? '—'}`, toneOf(task.results.security.status)),
    row(kit, line(kit, `verify    ${verify.label}`, verify.tone), verify.note !== null && line(kit, ` · ${verify.note}`, 'warning')),
    line(kit, `review    ${task.results.review.status ?? '—'}`, toneOf(task.results.review.status)),
  ]

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
  const unitSuffix = unit !== null && unit.label !== '' ? ` · ${unit.label}` : ''

  const fill = fillCommandFor(task)

  return column(
    kit,
    { marginTop: 1 },
    row(kit, heading(kit, `CREW / ${TEXT.currentTask}`), headNotes.length > 0 && dim(kit, `  （${headNotes.join(' · ')}）`)),
    el(kit.Box, { marginTop: 1 }, el(kit.Text, { bold: true }, task.slug)),
    task.name !== task.slug && dim(kit, task.name),
    el(kit.Text, {}, `${task.type} · ${task.phase ?? '—'} · ${schemaText(task)} · ${staleText(task)}`),
    task.parked !== null && el(kit.Text, {}, `${TEXT.parked}${task.parked.reason !== null ? `：${task.parked.reason}` : ''}`),
    task.closed && dim(kit, TEXT.closedTask),
    task.inferred && line(kit, TEXT.inferred, 'warning'),
    task.isSchemaNewer && task.schemaVersion !== null && line(kit, TEXT.schemaNewer(task.schemaVersion), 'warning'),
    task.branch !== null && dim(kit, `branch: ${task.branch} ${TEXT.branchNote}`),
    section(kit, `${TEXT.progress}（${progress.done} / ${progress.total}）`, el(kit.Text, {}, stepsText)),
    section(kit, TEXT.approval, ...gateRows),
    section(kit, TEXT.results, ...resultRows),
    // 空的 work_unit（total 為 0，例如 new_state 的預設值）不顯示；未完成的才醒目（§11、A8）
    unit !== null &&
      unit.total > 0 &&
      el(
        kit.Box,
        { marginTop: 1 },
        unit.isInterrupted
          ? line(kit, `${TEXT.workUnit}   ⚠ ${TEXT.interrupted(unit.done, unit.total)}${unitSuffix}`, 'warning')
          : el(kit.Text, {}, `${TEXT.workUnit}   ${unit.done} / ${unit.total}${unitSuffix}`),
      ),
    hintParts.length > 0 && el(kit.Text, {}, `${TEXT.resumeHint}   ${hintParts.join(' · ')}`),
    task.recordedNext !== null &&
      section(
        kit,
        TEXT.recordedNext,
        task.recordedNext.command !== null && dim(kit, task.recordedNext.command),
        task.recordedNext.reason !== '' && dim(kit, task.recordedNext.reason),
      ),
    el(
      kit.Box,
      { marginTop: 1, flexDirection: 'row', flexWrap: 'wrap', gap: 1 },
      fill !== null
        ? el(kit.Button, { key: 'fill', label: TEXT.fill(task.slug), variant: 'primary', hotkey: 'f', onPress: () => cb.fill(task.id) })
        : line(kit, TEXT.slugNotFillable, 'warning'),
    ),
  )
}

/** §12 Tasks：active → parked → closed（loader 已排序），最多 50 筆；壞檔列 invalid row；底部列缺 state.json 的目錄數。 */
function tasksView(
  kit: CockpitKit,
  snapshot: CockpitSnapshot,
  selected: CockpitTaskView | null,
  bodyColumns: number,
  cb: PaneCallbacks,
): RenderElement {
  const isCompact = bodyColumns < PANE_COMPACT_COLUMNS
  const rows = snapshot.tasks.slice(0, TASK_ROW_LIMIT).map((task, index) => {
    const verify = verifyDisplay(task.results.verify)
    const state = task.closed ? ` · ${TEXT.closedTask}` : task.parked !== null ? ` · ${TEXT.parked}` : ''
    const meta = `${task.type} · ${task.phase ?? '—'}${state} · ${TEXT.verifyLabel} `
    const tail = ` · ${staleText(task)} · ${task.updated ?? '—'}`
    const isSelected = selected !== null && selected.id === task.id
    const button = el(kit.Button, {
      // key 用序號，不用目錄名（目錄名是不可信的 repo 字串）
      key: `task-${index}`,
      label: `${isSelected ? `${TEXT.selected} ` : ''}${task.slug}`,
      ...(isSelected && { variant: 'primary' }),
      onPress: () => cb.selectTask(task.id),
    })
    const info = row(kit, el(kit.Text, {}, isCompact ? meta : ` ${meta}`), line(kit, verify.label, verify.tone), el(kit.Text, {}, tail))
    return isCompact ? column(kit, {}, button, info) : row(kit, button, info)
  })

  return column(
    kit,
    { marginTop: 1 },
    ...rows,
    snapshot.tasks.length > TASK_ROW_LIMIT && dim(kit, TEXT.tasksTruncated(TASK_ROW_LIMIT)),
    ...snapshot.invalidTasks.map(invalid => invalidRow(kit, invalid)),
    snapshot.untrackedDirCount > 0 && el(kit.Box, { marginTop: 1 }, dim(kit, TEXT.untracked(snapshot.untrackedDirCount))),
  )
}

function invalidRow(kit: CockpitKit, invalid: CockpitInvalidTask): RenderElement {
  return column(
    kit,
    {},
    line(kit, `${invalid.slug} · ${TEXT.invalidState}`, 'warning'),
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
        row(kit, el(kit.Text, {}, 'status  '), line(kit, verify.label, verify.tone), verify.note !== null && line(kit, ` · ${verify.note}`, 'warning')),
        ...task.results.verify.entries.map(entry => el(kit.Text, {}, `${entry.key}  ${entry.value}`)),
        verify.isBlocked && line(kit, TEXT.blockedNote(verify.blocked), 'warning'),
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

/** HUD 一行的片段：text 與色調（只有驗收狀態等少數片段上色）。 */
export type HudSegment = { text: string; tone: Tone }

/**
 * HUD 的內容（純資料）：沒有 active task 或沒有選取時回 null（§9.1：不佔空間）。
 * 寬畫面最多 2 行；bodyColumns < 60 退成 1 行。state.next 一律標「上次建議」，不是現況（§6.3）。
 * 不顯示 ci-ready（§9.3、AC-11）。
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
  const seg = (text: string, tone: Tone = 'neutral'): HudSegment => ({ text, tone })
  const slug = hudText(task.slug)
  const phase = hudText(task.phase ?? '—')

  if (data.bodyColumns < HUD_COMPACT_COLUMNS) {
    return [
      [
        seg(`CREW · ${slug} · ${phase}`),
        ...(hasVerify ? [seg(' · '), seg(hudText(verify.short), verify.tone)] : []),
        ...(others > 0 ? [seg(` · ＋${others}`)] : []),
      ],
    ]
  }

  const unit = task.workUnit
  const first: HudSegment[] = [
    seg(`CREW · ${slug} · ${hudText(task.type)} / ${phase}`),
    ...(unit !== null && unit.isInterrupted ? [seg(` · ${TEXT.interrupted(unit.done, unit.total)}`, 'warning')] : []),
    ...(hasVerify ? [seg(` · ${TEXT.verifyLabel} `), seg(hudText(verify.label), verify.tone)] : []),
    ...(verify.note !== null ? [seg(` · ${verify.note}`, 'warning')] : []),
    seg(` · ${TEXT.stale(task.staleDays)}`),
    ...(others > 0 ? [seg(` · ${TEXT.otherActive(others)}`)] : []),
    ...(task.inferred ? [seg(` · ${TEXT.inferredShort}`, 'warning')] : []),
  ]

  const uat = (visibleGates(task) ?? []).find(gate => gate.key === 'uat')
  const recorded = task.recordedNext?.command ?? null
  const second = [
    uat !== undefined ? (uat.status === 'pending' ? TEXT.uatPendingShort : `UAT ${hudText(uat.status ?? '—')}`) : null,
    recorded !== null ? `${TEXT.recordedNextShort} ${hudText(recorded)}` : null,
    TEXT.loadedAt(formatClock(snapshot.loadedAt)),
    fillCommandFor(task),
  ].filter((part): part is string => part !== null)

  return [first, [seg(second.join(' · '))]]
}

/** HUD 片段轉成 element（每行一個 row Box，單行截斷）。 */
export function hudView(kit: CockpitKit, lines: readonly HudSegment[][]): RenderElement {
  return column(
    kit,
    {},
    ...lines.map(segments =>
      el(kit.Box, { flexDirection: 'row' }, ...segments.map(segment => line(kit, segment.text, segment.tone, { wrap: 'truncate-end' }))),
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
