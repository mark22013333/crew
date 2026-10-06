// CREW Cockpit（Batch 1 Mod boot＋Batch 2 Read model）的自動測試：`claude plugin test plugins/feature-workflow`。
// 依規格 §22：fixture 以 fs hook 注入（tests/fixtures/world.ts），同時 spy 不得發生的呼叫。
// 涵蓋 T-1、T-2、T-3、T-6、T-11、T-14 的讀取模型層；HUD／Overview 的畫面斷言由 Batch 3／5 補上。

import type { RenderInput, SessionStartInput } from 'claude-code'
import { describe, expect, test } from 'claude-code/testing'

import { resolveRepoRoot, toIrSummary } from '../hooks/cockpit/loader'
import { TEXT, asInt, isFillableSlug, parseIsoMs, sanitizeText } from '../hooks/cockpit/model'
import type { CockpitSnapshot, CockpitTaskView } from '../hooks/cockpit/model'
import { fillCommandFor, hudText, otherActiveCount, progressOf, resolveSelection, visibleGates } from '../hooks/cockpit/selectors'
import {
  HOSTILE,
  IR_MALFORMED,
  MALFORMED,
  NOT_OBJECT,
  V1_BUG_9STEPS,
  V1_FEATURE_LEGACY,
  V2_BUG_MINIMAL,
  V2_FEATURE_CLOSED,
  V2_FEATURE_PARKED,
  V2_FEATURE_VERIFY_PASS,
  V2_FEATURE_VERIFY_WARN_BLOCKED,
  V3_FUTURE,
  VERIFICATION_IR,
} from './fixtures/states'
import { ROOT, specFiles, textOf, type World, worldOf } from './fixtures/world'

const SESSION: SessionStartInput = { surface: 'terminal', isInteractive: true, cwd: ROOT }

const PANE: RenderInput<'Pane'> = {
  component: 'Pane',
  surface: 'terminal',
  requestId: 'crew-cockpit',
  viewport: { columns: 180, rows: 48, isFullscreen: true },
  props: {
    title: 'CREW',
    isFocused: true,
    bodyColumns: 72,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 44 },
    view: {},
  },
}

const BAND: RenderInput<'AbovePrompt'> = {
  component: 'AbovePrompt',
  surface: 'terminal',
  requestId: 'band',
  viewport: { columns: 180, rows: 48, isFullscreen: true },
  props: { hasSurvey: false, isWorking: false, maxRows: 20, bodyColumns: 100, scroll: { offset: 0, bodyRows: 19 }, view: {} },
}

const COMMAND = (args = '') => ({
  command: 'crew-cockpit',
  args,
  origin: { kind: 'composer' as const },
  presentation: { isFullscreen: true, columns: 180 },
})

const TURN = (agentId?: string) => ({
  answer: 'ok',
  durationMs: 10,
  isAborted: false,
  turnId: 'turn-1',
  reason: 'answer' as const,
  ...(agentId !== undefined && { agentId }),
})

/** 讀 plugin 存在 $.state 的 snapshot（經 world 的記憶體 state）。 */
function snapshotOf(world: World): CockpitSnapshot {
  const value = world.stateOf('feature-workflow', 'snapshot')
  if (value === null || value === undefined) {
    throw new Error('snapshot 尚未載入')
  }
  return value as CockpitSnapshot
}

const taskOf = (snapshot: CockpitSnapshot, id: string): CockpitTaskView => {
  const task = snapshot.tasks.find(item => item.id === id)
  if (task === undefined) {
    throw new Error(`找不到 task ${id}`)
  }
  return task
}

/** 收集物件內所有字串值（含 key）。 */
const allStrings = (value: unknown): string[] => {
  if (typeof value === 'string') {
    return [value]
  }
  if (Array.isArray(value)) {
    return value.flatMap(allStrings)
  }
  if (typeof value === 'object' && value !== null) {
    return Object.entries(value).flatMap(([key, inner]) => [key, ...allStrings(inner)])
  }
  return []
}

const CONTROL_CHARS = /[\x00-\x1f\x7f-\x9f]/

describe('Batch 1：Mod boot', () => {
  test('session.start 註冊 /crew-cockpit（immediate），不自動開 pane（§10、§17.3）', async ($, on) => {
    const world = worldOf(on, {})

    await $.session.start(SESSION)

    expect(world.commands).toEqual([{ name: 'crew-cockpit', immediate: true }])
    expect(world.opened, 'session.start 不得自動開 pane').toEqual([])
  })

  test('/crew-cockpit 開 pane：focus＋closeOnEscape、不設 holdToasts（§10）', async ($, on) => {
    const world = worldOf(on, specFiles({ 'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS }))

    await $.session.start(SESSION)
    const result = await $.command.run(COMMAND())

    expect(result).toEqual({ text: TEXT.paneOpened })
    expect(world.opened).toEqual([{ id: 'crew-cockpit', focus: true, closeOnEscape: true, holdToasts: false }])
  })

  test('Claude Code 版本過舊：不載入、/crew-cockpit 只回版本需求（§19）', async ($, on) => {
    const world = worldOf(on, specFiles({ 'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS }), { version: '2.1.200' })

    await $.session.start(SESSION)
    const result = await $.command.run(COMMAND())

    expect(result).toEqual({ text: TEXT.needVersion('2.1.289') })
    expect(world.opened).toEqual([])
    expect(world.asked.filter(line => line.startsWith('read ')), '版本過舊時不讀任何檔').toEqual([])
  })
})

describe('T-1 沒有 .spec', () => {
  test('session start 不 crash、AbovePrompt 原樣放行、pane 顯示沒有任務', async ($, on) => {
    const world = worldOf(on, { [`${ROOT}/README.md`]: 'hi' })
    on('ui.render', () => ({ type: 'Text', props: {}, children: ['OTHER-MOD'] }) as never)

    await $.session.start(SESSION)
    const snapshot = snapshotOf(world)

    expect(snapshot.repoRoot).toBe(null)
    expect(snapshot.tasks).toEqual([])
    expect(snapshot.errors).toEqual([])

    const band = await $.ui.render(BAND)
    expect(textOf(band as never), 'AbovePrompt 必須 pass-through').toBe('OTHER-MOD')

    await $.command.run(COMMAND())
    const pane = textOf((await $.ui.render(PANE)) as never)
    expect(pane).toContain(TEXT.noTasks)
    expect(pane).toContain(TEXT.noTasksHint)
    expect(world.forbidden).toEqual([])
  })
})

describe('T-2 一個 active feature task', () => {
  test('phase=verify、verify=PASS、next 快照=/plan-review；不產生任何寫入／process／model 呼叫', async ($, on) => {
    const world = worldOf(on, specFiles({ 'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS }))

    await $.session.start(SESSION)
    await $.command.run(COMMAND())
    await $.turn.complete(TURN() as never)
    const snapshot = snapshotOf(world)
    const task = taskOf(snapshot, 'order-export-csv')

    expect(snapshot.repoRoot).toBe(ROOT)
    expect(snapshot.selectedSlug).toBe('order-export-csv')
    expect(snapshot.selectionReason).toBe('only-active')
    expect(snapshot.autoSelected).toBe(false)
    expect(task.phase).toBe('verify')
    expect(task.schemaVersion).toBe(2)
    expect(task.results.verify.status).toBe('PASS')
    expect(task.results.verify.blocked).toBe(0)
    expect(task.recordedNext).toEqual({ command: '/plan-review', reason: '驗收 PASS，下一步審查' })
    expect(task.gates?.map(gate => `${gate.key}=${gate.status}`)).toEqual([
      'requirement=approved',
      'architecture=approved',
      'uat=pending',
    ])
    expect(visibleGates(task)?.length).toBe(3)
    expect(progressOf(task)).toEqual({ done: 7, total: 9 })
    expect(task.branch).toBe('feature/order-export-csv')
    expect(fillCommandFor(task), 'Fill 固定為 /plan-next {slug}，不是 state.next.command').toBe('/plan-next order-export-csv')
    expect(task.verificationIr).toEqual({ status: 'missing' })
    expect(world.forbidden).toEqual([])
  })
})

describe('T-3 多個 task', () => {
  const files = specFiles({
    'push-tag-query/state.json': V2_FEATURE_VERIFY_WARN_BLOCKED,
    'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS,
    'search-synonyms/state.json': V2_FEATURE_PARKED,
    'profile-avatar-upload/state.json': V2_FEATURE_CLOSED,
  })

  test('預設選 updated 最新的 active（略過更新的 parked）；排序 active → parked → closed', async ($, on) => {
    const world = worldOf(on, files)

    await $.session.start(SESSION)
    const snapshot = snapshotOf(world)

    expect(snapshot.tasks.map(task => task.id)).toEqual([
      'order-export-csv',
      'push-tag-query',
      'search-synonyms',
      'profile-avatar-upload',
    ])
    expect(snapshot.activeCount).toBe(2)
    expect(snapshot.selectedSlug).toBe('order-export-csv')
    expect(snapshot.selectionReason).toBe('latest-active')
    expect(snapshot.autoSelected).toBe(true)
    expect(taskOf(snapshot, 'search-synonyms').parked).toEqual({ at: '2026-09-20T10:00:00+08:00', reason: '等待需求方回覆' })
    expect(taskOf(snapshot, 'profile-avatar-upload').closed).toBe(true)

    const auto = resolveSelection(snapshot, null)
    expect(auto.task?.id).toBe('order-export-csv')
    expect(otherActiveCount(snapshot, auto.task)).toBe(1)
  })

  test('選另一個 task 後，選取跟著切換且只改 UI state', async ($, on) => {
    const world = worldOf(on, files)

    await $.session.start(SESSION)
    const snapshot = snapshotOf(world)
    const picked = resolveSelection(snapshot, 'push-tag-query')

    expect(picked.task?.id).toBe('push-tag-query')
    expect(picked.reason).toBe('user')
    expect(picked.autoSelected).toBe(false)
    expect(resolveSelection(snapshot, 'no-such-task').task?.id, '選的 task 不存在時回到自動選取').toBe('order-export-csv')

    world.setState('feature-workflow', 'selectedSlug', 'push-tag-query')
    await $.turn.complete(TURN() as never)
    const after = snapshotOf(world)
    expect(after.selectedSlug).toBe('push-tag-query')
    expect(after.selectionReason).toBe('user')
    expect(world.forbidden).toEqual([])
  })

  test('停滯天數對齊 crew-state.py stale_days', async ($, on) => {
    const world = worldOf(on, files)

    await $.session.start(SESSION)
    const snapshot = snapshotOf(world)

    // updated 2026-10-03T09:00+08:00 → now 2026-10-06T12:00+08:00
    expect(taskOf(snapshot, 'push-tag-query').staleDays).toBe(3)
    expect(taskOf(snapshot, 'push-tag-query').staleUnknown).toBe(false)
  })
})

describe('T-6 壞掉的 state', () => {
  test('JSON 壞掉／不是物件／過大 → invalid row，不 crash，其他 task 照常', async ($, on) => {
    const world = worldOf(
      on,
      specFiles({
        'broken-task/state.json': MALFORMED,
        'array-task/state.json': NOT_OBJECT,
        'huge-task/state.json': 'x'.repeat(4 * 1024 * 1024 + 1),
        'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS,
      }),
    )

    await $.session.start(SESSION)
    const snapshot = snapshotOf(world)

    expect(snapshot.tasks.map(task => task.id)).toEqual(['order-export-csv'])
    expect(snapshot.invalidTasks.map(row => `${row.id}:${row.kind}`).sort()).toEqual([
      'array-task:not-object',
      'broken-task:parse',
      'huge-task:too-large',
    ])
    const broken = snapshot.invalidTasks.find(row => row.id === 'broken-task')
    expect(broken?.message).toContain(TEXT.invalidState)
    expect(snapshot.invalidTasks.find(row => row.id === 'huge-task')?.message).toBe(TEXT.fileTooLarge)
    expect(world.asked, '過大的檔不讀').not.toContain(`read ${ROOT}/.spec/huge-task/state.json`)

    await $.command.run(COMMAND())
    expect(textOf((await $.ui.render(PANE)) as never)).toContain('3 筆無法解析')
  })

  test('IR：存在＝ready（route 依實際值統計）、壞掉＝invalid、不存在＝missing（常態）', async ($, on) => {
    const world = worldOf(
      on,
      specFiles({
        'push-tag-query/state.json': V2_FEATURE_VERIFY_WARN_BLOCKED,
        'push-tag-query/.cache/verification-ir.json': VERIFICATION_IR,
        'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS,
        'order-export-csv/.cache/verification-ir.json': IR_MALFORMED,
        'legacy-report-filter/state.json': V1_FEATURE_LEGACY,
      }),
    )

    await $.session.start(SESSION)
    const snapshot = snapshotOf(world)
    const ir = taskOf(snapshot, 'push-tag-query').verificationIr

    expect(ir.status).toBe('ready')
    if (ir.status === 'ready') {
      expect(ir.acCount).toBe(4)
      expect(ir.routes).toEqual([
        { verificationType: 'browser', count: 2 },
        { verificationType: 'api', count: 1 },
        { verificationType: 'custom-x', count: 1 },
      ])
      expect(ir.preconditionCount).toBe(2)
      expect(ir.safetyCount).toBe(1)
    }
    expect(taskOf(snapshot, 'order-export-csv').verificationIr.status).toBe('invalid')
    expect(taskOf(snapshot, 'legacy-report-filter').verificationIr).toEqual({ status: 'missing' })
    // verify 原料：WARN＋blocked=2（BLOCKED 是衍生顯示，§11.3；映射由 Batch 4 做）
    expect(taskOf(snapshot, 'push-tag-query').results.verify.status).toBe('WARN')
    expect(taskOf(snapshot, 'push-tag-query').results.verify.blocked).toBe(2)
    expect(taskOf(snapshot, 'push-tag-query').workUnit?.isInterrupted).toBe(true)
  })
})

describe('T-11 schema v1／bug', () => {
  test('v1 feature 沒有 gates → gates 為 null（不得補成 pending）、無升級提示', async ($, on) => {
    const world = worldOf(on, specFiles({ 'legacy-report-filter/state.json': V1_FEATURE_LEGACY }))

    await $.session.start(SESSION)
    const snapshot = snapshotOf(world)
    const task = taskOf(snapshot, 'legacy-report-filter')

    expect(task.schemaVersion).toBe(1)
    expect(task.gates).toBe(null)
    expect(visibleGates(task)).toBe(null)
    expect(task.isSchemaNewer).toBe(false)
    expect(snapshot.errors, 'v1 是常態，不列入錯誤').toEqual([])
    expect(allStrings(task).some(text => /pending/.test(text) && text !== 'pending'), '不得出現推導的 pending').toBe(false)
    expect(allStrings(snapshot).some(text => /升級|upgrade/i.test(text))).toBe(false)
  })

  test('v1 bug 照實列出 9 步；v2 bug 只有 4 步、核准閘只顯示 uat', async ($, on) => {
    const world = worldOf(
      on,
      specFiles({
        'cache-ttl-bug/state.json': V1_BUG_9STEPS,
        'login-timeout-fix/state.json': V2_BUG_MINIMAL,
      }),
    )

    await $.session.start(SESSION)
    const snapshot = snapshotOf(world)
    const v1 = taskOf(snapshot, 'cache-ttl-bug')
    const v2 = taskOf(snapshot, 'login-timeout-fix')

    expect(v1.type).toBe('bug')
    expect(v1.steps.map(step => step.key)).toEqual(['start', 'spec', 'db', 'arch', 'build', 'security', 'verify', 'review', 'close'])
    expect(progressOf(v1)).toEqual({ done: 1, total: 9 })
    expect(v2.steps.map(step => step.key)).toEqual(['start', 'investigate', 'fix', 'close'])
    expect(progressOf(v2)).toEqual({ done: 3, total: 4 })
    expect(visibleGates(v2)?.map(gate => gate.key)).toEqual(['uat'])
    expect(v2.gates?.length, '原始 gates 照存，篩選只在顯示層').toBe(3)
  })

  test('schema 比 v2 新 → 標示 isSchemaNewer，仍可讀共同欄位', async ($, on) => {
    const world = worldOf(on, specFiles({ 'future-schema-task/state.json': V3_FUTURE }))

    await $.session.start(SESSION)
    const task = taskOf(snapshotOf(world), 'future-schema-task')

    expect(task.isSchemaNewer).toBe(true)
    expect(task.phase).toBe('spec')
  })
})

describe('T-14 不可信內容清理', () => {
  test('name 含 escape／換行／500 字 → 單行、無控制字元、截斷；slug 含空白 → 沒有 Fill', async ($, on) => {
    const world = worldOf(on, specFiles({ 'evil task/state.json': HOSTILE }))

    await $.session.start(SESSION)
    const snapshot = snapshotOf(world)
    const task = taskOf(snapshot, 'evil task')

    expect(task.slug).toBe('evil task')
    expect(task.isSlugFillable).toBe(false)
    expect(fillCommandFor(task)).toBe(null)
    expect(task.name.startsWith('紅字第一行 第二行 長')).toBe(true)
    expect(Array.from(task.name).length).toBe(200)
    expect(task.name.endsWith('…')).toBe(true)
    expect(Array.from(hudText(task.name)).length).toBe(60)
    expect(task.phase).toBe('spec')
    expect(task.recordedNext?.command).toBe('/plan-close --force /plan-start injected')
    expect(task.recordedNext?.reason).toBe('點我')
    expect(task.results.verify.status).toBe('WARN')
    expect(task.results.verify.blocked, '字串計數 "2" 依 as_int 解析').toBe(2)
    expect(task.branch).toBe('feature/evil')
    expect(task.resumeHint?.branch).toBe('xy')
    expect(task.resumeHint?.readFirst).toEqual(['a b'])

    const leaked = allStrings(snapshot).filter(text => CONTROL_CHARS.test(text))
    expect(leaked, 'snapshot 內任何字串都不得含控制字元').toEqual([])
  })
})

describe('缺 state.json 的目錄、repo root 判定、增量重讀', () => {
  test('只有 .state.lock 或沒有 state.json 的目錄只計數；.spec 下的一般檔略過', async ($, on) => {
    const world = worldOf(
      on,
      specFiles({
        '_index.md': '# index',
        'old-task/.state.lock': '',
        'no-state/plan.md': '# plan',
        'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS,
      }),
    )

    await $.session.start(SESSION)
    const snapshot = snapshotOf(world)

    expect(snapshot.untrackedDirCount).toBe(2)
    expect(snapshot.tasks.map(task => task.id)).toEqual(['order-export-csv'])
    expect(snapshot.invalidTasks).toEqual([])
  })

  test('§6.1：session root → 往上到 git 根 → git 根；都沒有就是 null，不往下掃', async ($, on) => {
    const files = specFiles({ 'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS })
    const world = worldOf(on, files)
    const io = (sessionRoot: string, gitRoot: string | null) => ({
      list: async () => [],
      stat: async (path: string) => {
        const isFile = world.files.has(path)
        const isDir = [...world.files.keys()].some(file => file.startsWith(`${path}/`))
        if (!isFile && !isDir) {
          throw new Error(`ENOENT: ${path}`)
        }
        return { kind: isFile ? ('file' as const) : ('dir' as const), size: 0, mtimeMs: 0, isLink: false }
      },
      exists: async (path: string) => world.files.has(path) || [...world.files.keys()].some(file => file.startsWith(`${path}/`)),
      read: async () => '',
      sessionRoot: async () => sessionRoot,
      repo: async () => (gitRoot === null ? null : { root: gitRoot, remote: null, internal: false, name: null }),
      now: async () => 0,
    })

    expect(await resolveRepoRoot(io(ROOT, ROOT))).toEqual({ root: ROOT, source: 'session-root' })
    expect(await resolveRepoRoot(io(`${ROOT}/src/app`, ROOT))).toEqual({ root: ROOT, source: 'ancestor' })
    expect(await resolveRepoRoot(io('/work/worktree-a', ROOT))).toEqual({ root: ROOT, source: 'git-root' })
    expect(await resolveRepoRoot(io('/work', null)), '多 repo workspace 根目錄').toEqual({ root: null, source: null })
    expect(await resolveRepoRoot(io(`${ROOT}/src`, null)), '沒有 git 根時不往上走').toEqual({ root: null, source: null })
  })

  test('§15：主 turn 結束只重讀 mtime 變了的檔；子代理 turn.complete 不重掃', async ($, on) => {
    const world = worldOf(
      on,
      specFiles({
        'push-tag-query/state.json': V2_FEATURE_VERIFY_WARN_BLOCKED,
        'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS,
      }),
    )

    await $.session.start(SESSION)
    const reads = () => world.asked.filter(line => line.startsWith('read '))

    world.asked.length = 0
    const subagent = await $.turn.complete(TURN('agent-1') as never)
    expect(subagent).toEqual({ text: 'ok' })
    expect(world.asked, '子代理結束：0 次 fs 呼叫').toEqual([])

    world.put(`${ROOT}/.spec/order-export-csv/state.json`, V2_FEATURE_VERIFY_PASS.replace('"phase": "verify"', '"phase": "review"'))
    world.asked.length = 0
    await $.turn.complete(TURN() as never)

    expect(reads()).toEqual([`read ${ROOT}/.spec/order-export-csv/state.json`])
    const snapshot = snapshotOf(world)
    expect(taskOf(snapshot, 'order-export-csv').phase).toBe('review')
    expect(snapshot.stats).toEqual({ dirs: 2, reread: 1, reused: 1 })
  })
})

describe('純函式', () => {
  test('sanitizeText／asInt／parseIsoMs／slug 白名單', () => {
    expect(sanitizeText('\x1b[31mA\x1b[0m\nB\tC  D')).toBe('A B C D')
    expect(sanitizeText({ a: 1 })).toBe('{"a":1}')
    expect(sanitizeText(null)).toBe('')
    expect(asInt('2')).toBe(2)
    expect(asInt(' 3 ')).toBe(3)
    expect(asInt('2.5')).toBe(0)
    expect(asInt(2.7)).toBe(2)
    expect(asInt(null)).toBe(0)
    expect(asInt(true)).toBe(1)
    expect(parseIsoMs('2026-10-06T12:00:00+08:00')).toBe(Date.UTC(2026, 9, 6, 4, 0, 0))
    expect(parseIsoMs('2026-10-06T04:00:00Z')).toBe(Date.UTC(2026, 9, 6, 4, 0, 0))
    expect(parseIsoMs('not a date')).toBe(null)
    expect(parseIsoMs('2026-02-30T00:00:00Z')).toBe(null)
    expect(isFillableSlug('push-tag-query')).toBe(true)
    expect(isFillableSlug('8.3-city-sso')).toBe(true)
    expect(isFillableSlug('evil task')).toBe(false)
    expect(isFillableSlug('Upper')).toBe(false)
    expect(isFillableSlug('-lead')).toBe(false)
    expect(isFillableSlug('a'.repeat(81))).toBe(false)
  })

  test('toIrSummary：verification_type 缺漏歸 null 組並排最後，不歸「其他」', () => {
    const summary = toIrSummary({ acs: { 'AC-1': { verification_type: 'manual' }, 'AC-2': {}, 'AC-3': { verification_type: 'manual' } } })
    expect(summary.status).toBe('ready')
    if (summary.status === 'ready') {
      expect(summary.routes).toEqual([
        { verificationType: 'manual', count: 2 },
        { verificationType: null, count: 1 },
      ])
    }
    expect(toIrSummary([1, 2]).status).toBe('invalid')
  })

  test('停滯天數：updated 與 created 都無法解析 → 0 且 staleUnknown', async ($, on) => {
    const broken = V2_FEATURE_VERIFY_PASS.replace('"created": "2026-10-01T09:00:00+08:00"', '"created": "yesterday"').replace(
      '"updated": "2026-10-04T09:00:00+08:00"',
      '"updated": "soon"',
    )
    const world = worldOf(on, specFiles({ 'order-export-csv/state.json': broken }))

    await $.session.start(SESSION)
    const task = taskOf(snapshotOf(world), 'order-export-csv')

    expect(task.staleDays).toBe(0)
    expect(task.staleUnknown).toBe(true)
  })
})
