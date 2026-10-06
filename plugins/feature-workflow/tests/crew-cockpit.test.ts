// CREW Cockpit（Batch 1 Mod boot＋Batch 2 Read model）的自動測試：`claude plugin test plugins/feature-workflow`。
// 依規格 §22：fixture 以 fs hook 注入（tests/fixtures/world.ts），同時 spy 不得發生的呼叫。
// Batch 1/2 涵蓋 T-1、T-2、T-3、T-6、T-11、T-14 的讀取模型層；
// Batch 3–6 補上 Pane／HUD 畫面斷言與 T-4、T-5、T-7、T-8、T-9、T-10、T-12、T-13、T-15（見檔尾）。

import type { Engine } from 'claude-code/testing'
import type { RenderInput, SessionStartInput } from 'claude-code'
import { describe, expect, test } from 'claude-code/testing'

import { resolveRepoRoot, toIrSummary, toTaskView } from '../hooks/cockpit/loader'
import { HUD_FIELD_MAX, TEXT, asInt, isFillableSlug, parseIsoMs, sanitizeText } from '../hooks/cockpit/model'
import type { CockpitSnapshot, CockpitTaskView } from '../hooks/cockpit/model'
import {
  fillCommandFor,
  formatClock,
  hudText,
  otherActiveCount,
  progressOf,
  resolveSelection,
  verifyDisplay,
  visibleGates,
} from '../hooks/cockpit/selectors'
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
import { NOW, ROOT, sleep, specFiles, textOf, type World, worldOf } from './fixtures/world'

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

  test('§10：pane 已開著（$.ui.panes）→ 再次 /crew-cockpit 不重複開啟；關閉後可再開', async ($, on) => {
    const world = worldOf(on, specFiles({ 'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS }))

    await $.session.start(SESSION)
    await $.command.run(COMMAND())
    expect(world.opened.length, '正對照：第一次確實開啟').toBe(1)
    expect(await $.command.run(COMMAND())).toEqual({ text: TEXT.paneOpened })
    expect(world.opened.length, '已開著就不再呼叫 ui.open').toBe(1)
    expect(world.toasts).toEqual([])

    world.panes = []
    await $.command.run(COMMAND())
    expect(world.opened.length, '關閉後再下指令會重新開啟').toBe(2)
  })

  test('§10：熱重載前已開但尚未就位的 pane → 不重複開啟，只 toast 提示', async ($, on) => {
    const world = worldOf(on, specFiles({ 'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS }))
    world.panes = [{ id: 'crew-cockpit', title: 'CREW', isShown: false, isFocused: false, isPlaced: false }]

    await $.session.start(SESSION)
    expect(await $.command.run(COMMAND())).toEqual({ text: TEXT.paneOpened })
    expect(world.opened).toEqual([])
    expect(world.toasts).toEqual([TEXT.paneNotPlaced])
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

describe('I/O spy 正對照', () => {
  /**
   * 引擎有兩道關：(1) host 依 hooks 模組的原始碼掃描結果，拒絕模組沒有寫到的呼叫（"its hooks module does not call it"）；
   * (2) world 的 spy hook 攔下並記錄。測試端的 hook 與 Cockpit 屬同一個 plugin，所以這裡發出的呼叫會先撞上 (1)：
   * 目前 crew-cockpit.ts 沒有任何這類呼叫，host 全數拒絕。日後若有人在模組裡加了其中一種呼叫，掃描會列出它，
   * 這裡的同一個呼叫就會穿過 (1) 落到 (2) 被記進 forbidden，其他測試的 `forbidden === []` 便會變紅。
   */
  test('process.spawn／model.fork／model.classify／mcp.call／mcp.connect／http.fetch：每一個都被 host 掃描拒絕或被 spy 攔下，沒有一個成功', async ($, on) => {
    const world = worldOf(on, {})
    const outcomes: Record<string, string> = {}
    const attempt = async (name: string, call: () => Promise<unknown>) => {
      try {
        await call()
        outcomes[name] = 'succeeded'
      } catch (error) {
        const text = String(error)
        outcomes[name] = /does not call it/.test(text) ? 'host-refused' : world.forbidden.includes(name) ? 'spy-denied' : `other: ${text}`
      }
    }
    on('command.run', { command: 'spy-probe' }, async inner => {
      await attempt('process.spawn', async () => {
        for await (const _chunk of inner.process.spawn({ argv: ['echo', 'x'] })) {
          // 讀串流讓拒絕浮現
        }
      })
      await attempt('model.fork', () => inner.model.fork({ prompt: 'x' } as never))
      await attempt('model.classify', () => inner.model.classify('x', ['a']))
      await attempt('mcp.call', () => inner.mcp.call('s', 't', {}))
      await attempt('mcp.connect', () => inner.mcp.connect('s'))
      await attempt('http.fetch', () => inner.http.fetch('https://example.com'))
      return { text: 'probed' }
    })

    expect(await $.command.run({ ...COMMAND(), command: 'spy-probe' })).toEqual({ text: 'probed' })
    const names = ['process.spawn', 'model.fork', 'model.classify', 'mcp.call', 'mcp.connect', 'http.fetch']
    expect(Object.keys(outcomes).sort(), '正對照：六個呼叫都真的發出了').toEqual([...names].sort())
    for (const name of names) {
      expect(['host-refused', 'spy-denied'], `${name} → ${outcomes[name]}`).toContain(outcomes[name])
    }
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

describe('§16 載入錯誤可見', () => {
  test('.spec 列不出來 → pane 顯示「載入問題」與清理過的錯誤，不顯示「沒有任務」', async ($, on) => {
    const world = worldOf(on, specFiles({ 'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS }), {
      listDenied: { [`${ROOT}/.spec`]: 'EACCES: permission denied\x1b[31m紅\nX' },
    })

    await $.session.start(SESSION)
    const snapshot = snapshotOf(world)
    expect(snapshot.errors.length, '正對照：loader 確實記下錯誤').toBe(1)

    await $.command.run(COMMAND())
    const pane = await mountPane($, 'terminal')
    const drawn = textOf(await pane.drawn())
    expect(drawn).toContain(TEXT.loadErrors)
    // 引擎會在 deny 訊息前加上「feature-workflow: $.fs.list: 」；控制字元已清掉、換行壓成空白
    expect(drawn).toContain(`${ROOT}/.spec · `)
    expect(drawn).toContain('EACCES: permission denied紅 X')
    expect(drawn).not.toContain(TEXT.noTasks)
    expect(CONTROL_CHARS.test(drawn)).toBe(false)
    const [errorLine] = await textColors(pane, /EACCES/)
    expect(errorLine?.color).toBe('warning')
    expect(await pane.find({ key: 'refresh' }), '仍可重新整理').not.toBe(undefined)
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

    // 畫面：任務 tab 列出 invalid row（§16），其他 task 照常
    await $.command.run(COMMAND())
    const pane = await mountPane($, 'terminal')
    await pressAndRedraw(pane, 'tab-tasks')
    const drawn = textOf(await pane.drawn())
    for (const id of ['broken-task', 'array-task', 'huge-task']) {
      expect(drawn).toContain(`${id} · ${TEXT.invalidState}`)
    }
    expect(drawn).toContain('order-export-csv')
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

    // ---- git worktree：repo().root 是主工作樹（ROOT），邊界改由 `.git`（worktree 是檔案）判定 ----
    // 主工作樹外的 worktree：從子目錄啟動也要往上找到 worktree 自己的 .spec，不得 fallback 到主工作樹
    world.put('/work/wt-b/.git', 'gitdir: /work/repo/.git/worktrees/wt-b')
    world.put('/work/wt-b/.spec/wt-task/state.json', V2_FEATURE_VERIFY_PASS)
    expect(await resolveRepoRoot(io('/work/wt-b/src/app', ROOT))).toEqual({ root: '/work/wt-b', source: 'ancestor' })
    // worktree 根之外的 .spec（例如 /work/.spec）不得被撿到：越過 worktree 根就停，交給 git 根 fallback
    world.put('/work/wt-c/.git', 'gitdir: /work/repo/.git/worktrees/wt-c')
    world.put('/work/.spec/stray/state.json', '{}')
    expect(await resolveRepoRoot(io('/work/wt-c/src', ROOT))).toEqual({ root: ROOT, source: 'git-root' })
    // worktree 放在主工作樹底下（.claude/worktrees/w1）：往上不得越過 worktree 根撿到主工作樹的 .spec
    world.put(`${ROOT}/.claude/worktrees/w1/.git`, 'gitdir: /work/repo/.git/worktrees/w1')
    world.put(`${ROOT}/.claude/.spec/inner/state.json`, '{}')
    expect(await resolveRepoRoot(io(`${ROOT}/.claude/worktrees/w1/src`, ROOT))).toEqual({ root: ROOT, source: 'git-root' })
    world.put(`${ROOT}/.claude/worktrees/w1/.spec/w1-task/state.json`, V2_FEATURE_VERIFY_PASS)
    expect(await resolveRepoRoot(io(`${ROOT}/.claude/worktrees/w1/src`, ROOT))).toEqual({
      root: `${ROOT}/.claude/worktrees/w1`,
      source: 'ancestor',
    })
  })

  test('§6.1：在 worktree 子目錄啟動時，snapshot 讀的是 worktree 的 .spec 而非主工作樹', async ($, on) => {
    const world = worldOf(
      on,
      {
        ...specFiles({ 'main-task/state.json': V2_FEATURE_VERIFY_PASS }),
        '/work/wt-b/.git': 'gitdir: /work/repo/.git/worktrees/wt-b',
        ...specFiles({ 'wt-task/state.json': V2_FEATURE_VERIFY_WARN_BLOCKED }, '/work/wt-b'),
      },
      { sessionRoot: '/work/wt-b/src', gitRoot: ROOT },
    )

    await $.session.start(SESSION)
    const snapshot = snapshotOf(world)
    expect(snapshot.repoRoot).toBe('/work/wt-b')
    expect(snapshot.rootSource).toBe('ancestor')
    expect(snapshot.tasks.map(task => task.id)).toEqual(['wt-task'])
    expect(world.asked.filter(entry => entry.startsWith('read ')).some(entry => entry.includes(`${ROOT}/.spec`)), '不讀主工作樹的 .spec').toBe(false)
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
    // §18.1 零寬與方向控制字元：每一個區段的頭尾都要清掉
    const invisible = ['\u200b', '\u200c', '\u200d', '\u200e', '\u200f', '\u202a', '\u202c', '\u202e', '\u2060', '\u2064', '\u2066', '\u2069', '\ufeff', '\u061c']
    for (const char of invisible) {
      expect(sanitizeText(`a${char}b`), `U+${char.codePointAt(0)?.toString(16).toUpperCase()}`).toBe('ab')
    }
    expect(sanitizeText('feature/\u202eevil\u202c-\u200bfix\ufeff')).toBe('feature/evil-fix')
    // 反對照：一般中文、全形符號與 emoji 不受影響
    expect(sanitizeText('中文　全形（）✓ 🚀')).toBe('中文　全形（）✓ 🚀')
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

  /**
   * 標準答案取自 crew-state.py list --format json 實跑（2026-10-07，fixture 產生器與輸出在 scratchpad fix2/oracle/）：
   * normalize() 把 null／缺漏補成「現在」→ 0 天；空字串與壞字串不補，parse 失敗才退到 created。
   * updated 有效＝now−2天1小時 → 2；created 有效＝now−5天1小時 → 5。
   */
  test('停滯天數對齊 crew-state.py normalize＋stale_days：updated null／缺漏／空字串／壞字串 × created 五種', () => {
    const HOUR = 60 * 60 * 1000
    const iso = (ms: number) => new Date(ms).toISOString()
    const UPDATED = { null: null, missing: undefined, empty: '', bad: 'soon', valid: iso(NOW - (2 * 24 + 1) * HOUR) } as const
    const CREATED = { valid5: iso(NOW - (5 * 24 + 1) * HOUR), null: null, missing: undefined, empty: '', bad: 'yesterday' } as const
    // crew-state.py 實跑的 stale_days（u-{updated}--c-{created}）
    const ORACLE: Record<string, number> = {
      'u-bad--c-bad': 0, 'u-bad--c-empty': 0, 'u-bad--c-missing': 0, 'u-bad--c-null': 0, 'u-bad--c-valid5': 5,
      'u-empty--c-bad': 0, 'u-empty--c-empty': 0, 'u-empty--c-missing': 0, 'u-empty--c-null': 0, 'u-empty--c-valid5': 5,
      'u-missing--c-bad': 0, 'u-missing--c-empty': 0, 'u-missing--c-missing': 0, 'u-missing--c-null': 0, 'u-missing--c-valid5': 0,
      'u-null--c-bad': 0, 'u-null--c-empty': 0, 'u-null--c-missing': 0, 'u-null--c-null': 0, 'u-null--c-valid5': 0,
      'u-valid--c-bad': 2, 'u-valid--c-empty': 2, 'u-valid--c-missing': 2, 'u-valid--c-null': 2, 'u-valid--c-valid5': 2,
    }
    const unparseable = new Set(['empty', 'bad'])
    const got: Record<string, number> = {}
    for (const [un, uv] of Object.entries(UPDATED)) {
      for (const [cn, cv] of Object.entries(CREATED)) {
        const raw: Record<string, unknown> = { schema_version: 2, type: 'feature', phase: 'spec' }
        if (uv !== undefined) raw.updated = uv
        if (cv !== undefined) raw.created = cv
        const view = toTaskView(raw, 'x', '/s', { status: 'missing' }, NOW)
        got[`u-${un}--c-${cn}`] = view.staleDays
        // staleUnknown 只在「補值後兩者都無法解析」：updated 與 created 都是空字串／壞字串
        expect(view.staleUnknown, `staleUnknown u-${un}--c-${cn}`).toBe(unparseable.has(un) && unparseable.has(cn))
      }
    }
    expect(got).toEqual(ORACLE)
  })

  test('停滯天數：updated 為 null 時增量重讀沿用舊 view 仍是 0 天（不退回 created）', async ($, on) => {
    const raw = JSON.parse(V2_FEATURE_VERIFY_PASS) as Record<string, unknown>
    const world = worldOf(on, specFiles({ 'order-export-csv/state.json': JSON.stringify({ ...raw, updated: null }) }))

    await $.session.start(SESSION)
    expect(taskOf(snapshotOf(world), 'order-export-csv').staleDays).toBe(0)
    await $.turn.complete(TURN() as never)
    const again = snapshotOf(world)
    expect(again.stats.reused, '確實走沿用舊 view 的路徑').toBe(1)
    expect(taskOf(again, 'order-export-csv').staleDays).toBe(0)
    expect(taskOf(again, 'order-export-csv').staleUnknown).toBe(false)
  })
})

// ===========================================================================
// Batch 3–6：Pane／HUD 畫面、Verify、Fill
// ===========================================================================

const PLUGIN = 'feature-workflow'
const SURFACES = ['terminal', 'desktop'] as const
type Surface = (typeof SURFACES)[number]

/**
 * 按下按鈕後重繪。測試的 $.state 由 tests/fixtures/world.ts 的 state.get/state.set hook 以記憶體實作
 * （測試引擎沒有 state noun），引擎的「寫入即通知讀者重繪」不在這條路上，所以按完要明確 redraw。
 * 真實 session 由引擎自動重繪（§3 D-3）。
 */
async function pressAndRedraw(mounted: { press: (target: { key: string }) => Promise<unknown>; redraw: () => Promise<void> }, key: string): Promise<void> {
  await mounted.press({ key })
  await mounted.redraw()
}

/** AbovePrompt 下方沒有其他 mod 時，代表引擎的「什麼都不畫」。 */
function nothingBeneathBand(on: Parameters<typeof worldOf>[0]): void {
  on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'Box', props: {}, children: [] }) as never)
}

/** 以指定 surface 掛載 Cockpit pane（T-10：不假設 surface）。 */
async function mountPane($: Engine, surface: Surface, bodyColumns: number = PANE.props.bodyColumns) {
  return $.ui.mount({
    plugin: PLUGIN,
    surface,
    component: 'Pane',
    requestId: 'crew-cockpit',
    props: { ...PANE.props, bodyColumns },
    viewport: PANE.viewport,
  })
}

/** 以指定 surface 掛載 AbovePrompt band。 */
async function mountBand($: Engine, surface: Surface, props: Partial<RenderInput<'AbovePrompt'>['props']> = {}) {
  return $.ui.mount({
    plugin: PLUGIN,
    surface,
    component: 'AbovePrompt',
    requestId: 'band',
    props: { ...BAND.props, ...props },
    viewport: BAND.viewport,
  })
}

/** 其他 mod 畫在 AbovePrompt 的內容（測試 hook 位於 plugin 之下，代表 next(e) 的既有 drawing）。 */
const OTHER_MOD = 'OTHER-MOD-BAND'
/** 改寫 fixture 的 results.verify（T-4 用）。 */
const withVerify = (fixture: string, verify: Record<string, unknown>): string => {
  const raw = JSON.parse(fixture) as Record<string, unknown>
  const results = (raw.results ?? {}) as Record<string, unknown>
  return JSON.stringify({ ...raw, results: { ...results, verify } }, null, 2)
}

/** 畫面上所有文字元素（type=Text）與其顏色。 */
async function textColors(mounted: { findAll: (query: { type?: string; text?: string | RegExp }) => Promise<{ text: string; props: Record<string, unknown> }[]> }, text: RegExp) {
  return (await mounted.findAll({ type: 'Text', text })).map(found => ({ text: found.text, color: found.props.color }))
}

describe('Batch 3 Pane：Overview／Tasks／Refresh（含 T-2、T-3、T-11 畫面）', () => {
  test('T-2 畫面：Overview 顯示 phase、核准閘、結果、上次記錄的建議（快照）與 Fill；不寫檔', async ($, on) => {
    const world = worldOf(on, specFiles({ 'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS }))

    await $.session.start(SESSION)
    await $.command.run(COMMAND())
    const pane = await mountPane($, 'terminal')
    const drawn = textOf(await pane.drawn())

    expect(drawn).toContain('order-export-csv')
    expect(drawn).toContain('feature · verify · schema v2')
    expect(drawn).toContain(TEXT.approval)
    expect(drawn).toContain('requirement   approved')
    expect(drawn).toContain('uat           pending')
    expect(drawn).toContain('verify    PASS')
    expect(drawn).toContain(`${TEXT.progress}（7 / 9）`)
    expect(drawn).toContain(TEXT.recordedNext)
    expect(drawn).toContain('/plan-review')
    expect(drawn).toContain('branch: feature/order-export-csv')
    expect(drawn).toContain(TEXT.branchNote)
    expect(drawn).toContain(TEXT.loadedAt(formatClock(NOW)))
    expect((await pane.find({ key: 'fill' }))?.props.label).toBe(TEXT.fill('order-export-csv'))
    expect(world.forbidden).toEqual([])
  })

  test('T-3 畫面：自動選最新 active 並標「自動選取」；在任務 tab 點另一個 task 後 Overview 切換，只改 UI state', async ($, on) => {
    const world = worldOf(
      on,
      specFiles({
        'push-tag-query/state.json': V2_FEATURE_VERIFY_WARN_BLOCKED,
        'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS,
        'search-synonyms/state.json': V2_FEATURE_PARKED,
        'profile-avatar-upload/state.json': V2_FEATURE_CLOSED,
      }),
    )

    await $.session.start(SESSION)
    await $.command.run(COMMAND())
    const pane = await mountPane($, 'terminal')
    const before = textOf(await pane.drawn())
    expect(before).toContain(TEXT.autoSelected)
    expect(before).toContain('另有 1 個進行中')
    expect((await pane.find({ key: 'fill' }))?.props.label).toBe(TEXT.fill('order-export-csv'))

    await pressAndRedraw(pane, 'tab-tasks')
    const tasks = textOf(await pane.drawn())
    // 排序 active → parked → closed；選取列標 ▶
    const order = ['order-export-csv', 'push-tag-query', 'search-synonyms', 'profile-avatar-upload'].map(id => tasks.indexOf(id))
    expect(order.every(index => index >= 0)).toBe(true)
    expect([...order].sort((a, b) => a - b)).toEqual(order)
    expect((await pane.find({ key: 'task-0' }))?.props.label).toBe(`${TEXT.selected} order-export-csv`)

    await pressAndRedraw(pane, 'task-1')
    expect(world.stateOf('feature-workflow', 'selectedSlug')).toBe('push-tag-query')
    expect(world.stateOf('feature-workflow', 'tab')).toBe('overview')
    const after = textOf(await pane.drawn())
    expect((await pane.find({ key: 'fill' }))?.props.label).toBe(TEXT.fill('push-tag-query'))
    expect(after).not.toContain(TEXT.autoSelected)
    expect(after).toContain('verify    WARN（BLOCKED ×2）')
    expect(world.forbidden, '只改 UI state，不寫任何 project file').toEqual([])
  })

  test('工作單元：空的（total 0）不顯示；中斷的警示色「中斷於 x/y」；完成的一般顯示（§11、A8）', async ($, on) => {
    const done = JSON.parse(V2_FEATURE_VERIFY_WARN_BLOCKED) as Record<string, unknown>
    const world = worldOf(
      on,
      specFiles({
        'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS,
        'push-tag-query/state.json': V2_FEATURE_VERIFY_WARN_BLOCKED,
        'finished-unit/state.json': JSON.stringify({ ...done, slug: 'finished-unit', work_unit: { ...(done.work_unit as object), done: 5, total: 5 } }),
      }),
    )

    await $.session.start(SESSION)
    await $.command.run(COMMAND())
    world.setState('feature-workflow', 'selectedSlug', 'order-export-csv')
    const pane = await mountPane($, 'terminal')
    const empty = textOf(await pane.drawn())
    expect(empty, '正對照：確實畫出了 order-export-csv 的總覽').toContain('feature · verify · schema v2')
    expect(empty).not.toContain(TEXT.workUnit)
    expect(empty).not.toContain('0 / 0')

    world.setState('feature-workflow', 'selectedSlug', 'push-tag-query')
    await pane.redraw()
    const [interrupted] = await textColors(pane, new RegExp(`^${TEXT.workUnit}`))
    expect(interrupted?.text).toBe(`${TEXT.workUnit}   ⚠ ${TEXT.interrupted(3, 5)} · browser verification`)
    expect(interrupted?.color).toBe('warning')

    world.setState('feature-workflow', 'selectedSlug', 'finished-unit')
    await pane.redraw()
    const [finished] = await textColors(pane, new RegExp(`^${TEXT.workUnit}`))
    expect(finished?.text).toBe(`${TEXT.workUnit}   5 / 5 · browser verification`)
    expect(finished?.color).toBe(undefined)
  })

  test('parked 任務標「已擱置」（對齊 crew-state.py park／list 用語），總覽附原因、任務列附標記', async ($, on) => {
    const world = worldOf(
      on,
      specFiles({ 'search-synonyms/state.json': V2_FEATURE_PARKED, 'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS }),
    )

    await $.session.start(SESSION)
    await $.command.run(COMMAND())
    world.setState('feature-workflow', 'selectedSlug', 'search-synonyms')
    const pane = await mountPane($, 'terminal')
    const overview = textOf(await pane.drawn())
    expect(TEXT.parked).toBe('已擱置')
    expect(overview).toContain('已擱置：等待需求方回覆')
    await pressAndRedraw(pane, 'tab-tasks')
    const tasks = textOf(await pane.drawn())
    expect(tasks).toContain(' · 已擱置 · ')
    expect(`${overview}${tasks}`).not.toContain('暫停')
  })

  test('Refresh：重新整理按鈕重讀 snapshot，畫面反映外部變更', async ($, on) => {
    const world = worldOf(on, specFiles({ 'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS }))

    await $.session.start(SESSION)
    await $.command.run(COMMAND())
    const pane = await mountPane($, 'terminal')
    world.put(`${ROOT}/.spec/order-export-csv/state.json`, V2_FEATURE_VERIFY_PASS.replace('"phase": "verify"', '"phase": "review"'))
    expect(textOf(await pane.drawn())).toContain('feature · verify')

    await pressAndRedraw(pane, 'refresh')
    expect(textOf(await pane.drawn())).toContain('feature · review')
    expect(world.forbidden).toEqual([])
  })

  test('T-11 畫面：v1 feature 顯示「舊版格式」、無 pending、無升級提示；v1 bug 列出 9 步；v2 bug 只顯示 4 步與 uat', async ($, on) => {
    const world = worldOf(
      on,
      specFiles({
        'legacy-report-filter/state.json': V1_FEATURE_LEGACY,
        'cache-ttl-bug/state.json': V1_BUG_9STEPS,
        'login-timeout-fix/state.json': V2_BUG_MINIMAL,
      }),
    )

    await $.session.start(SESSION)
    await $.command.run(COMMAND())

    world.setState('feature-workflow', 'selectedSlug', 'legacy-report-filter')
    const pane = await mountPane($, 'terminal')
    const v1 = textOf(await pane.drawn())
    expect(v1).toContain(TEXT.v1NoGates)
    expect(v1).not.toContain('pending')
    expect(v1).not.toMatch(/升級|upgrade/i)
    expect(await pane.findAll({ type: 'Button', text: /升級|upgrade/i })).toEqual([])

    world.setState('feature-workflow', 'selectedSlug', 'cache-ttl-bug')
    await pane.redraw()
    const v1Bug = textOf(await pane.drawn())
    expect(v1Bug).toContain(`${TEXT.progress}（1 / 9）`)
    for (const key of ['start', 'spec', 'db', 'arch', 'build', 'security', 'verify', 'review', 'close']) {
      expect(v1Bug).toContain(`${key} `)
    }

    world.setState('feature-workflow', 'selectedSlug', 'login-timeout-fix')
    await pane.redraw()
    const v2Bug = textOf(await pane.drawn())
    expect(v2Bug).toContain(`${TEXT.progress}（3 / 4）`)
    expect(v2Bug).toContain('start ✓  investigate ✓  fix ✓  close ○')
    expect(v2Bug).toContain('uat ')
    expect(v2Bug).not.toContain('requirement')
    expect(v2Bug).not.toContain('architecture')
  })

  test('T-14 畫面：HUD 與 Pane 都沒有控制字元、單行截斷；slug 含空白 → 沒有 Fill 按鈕，改顯示說明', async ($, on) => {
    worldOf(on, specFiles({ 'evil task/state.json': HOSTILE }))
    nothingBeneathBand(on)

    await $.session.start(SESSION)
    await $.command.run(COMMAND())
    const pane = await mountPane($, 'terminal')
    const band = await mountBand($, 'terminal')
    const paneText = textOf(await pane.drawn())
    const bandText = textOf(await band.drawn())

    // 正對照：HUD 與 pane 確實畫出了這個 task（否則「沒有控制字元」是空洞的通過）
    expect(bandText).toContain('CREW · evil task · feature / spec')
    expect(paneText).toContain('紅字第一行 第二行 長')
    expect(CONTROL_CHARS.test(paneText)).toBe(false)
    expect(CONTROL_CHARS.test(bandText)).toBe(false)
    expect(await pane.find({ key: 'fill' })).toBe(undefined)
    expect(paneText).toContain(TEXT.slugNotFillable)
    expect(bandText).not.toContain('/plan-next')
    expect(bandText, 'HUD 不得出現 state.next 的惡意指令換行片段').not.toContain('injected\n')
    // §18.1：HUD 單一欄位 ≤ 60 字元（以 ' · ' 分隔的每個欄位）
    for (const found of await band.findAll({ type: 'Text' })) {
      for (const field of found.text.split(' · ')) {
        expect(Array.from(field).length <= HUD_FIELD_MAX, `HUD 欄位過長：${field}`).toBe(true)
      }
    }
  })

  test('§18.1 HUD 欄位上限 60：超長的 type／phase／上次建議各自截到 60 字並以 … 結尾（Pane 仍是 200）', async ($, on) => {
    const raw = JSON.parse(V2_FEATURE_VERIFY_WARN_BLOCKED) as Record<string, unknown>
    const long = JSON.stringify({ ...raw, type: 't'.repeat(300), phase: 'p'.repeat(300), next: { command: 'c'.repeat(300), reason: 'r' } })
    worldOf(on, specFiles({ 'push-tag-query/state.json': long }))
    nothingBeneathBand(on)

    await $.session.start(SESSION)
    const band = await mountBand($, 'terminal')
    const hud = textOf(await band.drawn())
    for (const char of ['t', 'p', 'c']) {
      const runs = hud.match(new RegExp(`${char}{10,}…?`, 'g')) ?? []
      expect(runs.length, `正對照：HUD 確實畫出了 ${char} 欄位`).toBeGreaterThan(0)
      for (const run of runs) {
        expect(Array.from(run).length, `${char} 欄位`).toBe(HUD_FIELD_MAX)
        expect(run.endsWith('…')).toBe(true)
      }
    }
    expect(HUD_FIELD_MAX).toBe(60)

    await $.command.run(COMMAND())
    const pane = textOf(await (await mountPane($, 'terminal')).drawn())
    const paneRun = pane.match(/p{10,}…?/)?.[0] ?? ''
    expect(Array.from(paneRun).length, 'Pane 欄位上限 200').toBe(200)
  })
})

describe('T-4 BLOCKED semantics（Batch 4）', () => {
  const cases = [
    { name: 'WARN＋blocked=2 → WARN（BLOCKED ×2）警示色', verify: { status: 'WARN', blocked: 2 }, label: 'WARN（BLOCKED ×2）', color: 'warning', hasBlocked: true },
    { name: 'WARN＋blocked=0 → 只有 WARN，不得出現 BLOCKED', verify: { status: 'WARN', blocked: 0 }, label: 'WARN', color: 'warning', hasBlocked: false },
    { name: 'WARN＋blocked="2"（字串計數）→ 同第一列', verify: { status: 'WARN', blocked: '2' }, label: 'WARN（BLOCKED ×2）', color: 'warning', hasBlocked: true },
    { name: 'FAIL＋blocked=1 → FAIL 附「另有 BLOCKED ×1」', verify: { status: 'FAIL', blocked: 1 }, label: 'FAIL', color: 'error', hasBlocked: true },
  ] as const

  for (const item of cases) {
    test(item.name, async ($, on) => {
      worldOf(on, specFiles({ 'push-tag-query/state.json': withVerify(V2_FEATURE_VERIFY_WARN_BLOCKED, item.verify) }))
      nothingBeneathBand(on)

      await $.session.start(SESSION)
      await $.command.run(COMMAND())
      const pane = await mountPane($, 'terminal')
      const band = await mountBand($, 'terminal')

      // Overview 結果列
      const overview = textOf(await pane.drawn())
      expect(overview).toContain(`verify    ${item.label}`)
      const [overviewLabel] = await textColors(pane, /^verify {4}/)
      expect(overviewLabel?.color).toBe(item.color)

      // Verify tab
      await pressAndRedraw(pane, 'tab-verify')
      const verifyTab = textOf(await pane.drawn())
      const [statusLabel] = await textColors(pane, new RegExp(`^${item.label.replace(/[()（）×]/g, '.')}$`))
      expect(statusLabel?.color).toBe(item.color)
      expect(verifyTab).toContain(TEXT.truthSeparator)

      // HUD
      const hud = textOf(await band.drawn())
      expect(hud).toContain(`${TEXT.verifyLabel} ${item.label}`)

      if (item.verify.status === 'WARN') {
        // 狀態標籤絕不是 FAIL，也不用 negative 色
        expect(overviewLabel?.color).not.toBe('error')
        expect(statusLabel?.text).not.toContain('FAIL')
      }
      if (item.hasBlocked && item.verify.status === 'WARN') {
        expect(verifyTab).toContain(TEXT.blockedNote(2))
      }
      if (!item.hasBlocked) {
        expect(overview).not.toContain('BLOCKED')
        expect(verifyTab).not.toContain('BLOCKED')
        expect(hud).not.toContain('BLOCKED')
      }
      if (item.verify.status === 'FAIL') {
        expect(overview).toContain(TEXT.otherBlocked(1))
        expect(verifyTab).toContain(TEXT.otherBlocked(1))
        expect(verifyTab, 'FAIL 不套用 BLOCKED 說明句').not.toContain(TEXT.blockedNote(1))
      }
    })
  }

  test('verifyDisplay 純函式：BLOCKED 只在 WARN＋blocked>0；status 原值 BLOCKED 照原值警示色；缺值為 —', () => {
    const base = { entries: [], isEmpty: false, hasBlockedKey: true }
    expect(verifyDisplay({ ...base, status: 'WARN', blocked: 0 }).label).toBe('WARN')
    expect(verifyDisplay({ ...base, status: 'WARN', blocked: 3 })).toMatchObject({ label: 'WARN（BLOCKED ×3）', short: 'BLOCKED ×3', tone: 'warning', isBlocked: true })
    expect(verifyDisplay({ ...base, status: 'WARN', blocked: -1 }).isBlocked).toBe(false)
    expect(verifyDisplay({ ...base, status: 'FAIL', blocked: 2 })).toMatchObject({ label: 'FAIL', tone: 'negative', isBlocked: false, note: TEXT.otherBlocked(2) })
    expect(verifyDisplay({ ...base, status: 'BLOCKED', blocked: 0 })).toMatchObject({ label: 'BLOCKED', tone: 'warning' })
    expect(verifyDisplay({ ...base, status: null, blocked: 0 })).toMatchObject({ label: '—', tone: 'neutral' })
    expect(verifyDisplay({ ...base, status: 'PASS', blocked: 5 })).toMatchObject({ label: 'PASS', tone: 'positive', isBlocked: false })
  })
})

describe('T-5 IR summary（Batch 4）', () => {
  test('Verify tab 依實際值統計 route（browser 2、api 1、custom-x 1），不出現 fixture 沒有的類別', async ($, on) => {
    worldOf(
      on,
      specFiles({
        'push-tag-query/state.json': V2_FEATURE_VERIFY_WARN_BLOCKED,
        'push-tag-query/.cache/verification-ir.json': VERIFICATION_IR,
      }),
    )

    await $.session.start(SESSION)
    await $.command.run(COMMAND())
    const pane = await mountPane($, 'terminal')
    await pressAndRedraw(pane, 'tab-verify')
    const drawn = textOf(await pane.drawn())

    expect(drawn).toContain(`IR  ${TEXT.irReady}`)
    expect(drawn).toContain('ACs  4')
    expect(drawn).toContain('Routes  browser 2 · api 1 · custom-x 1')
    expect(drawn).toContain('Preconditions  2')
    expect(drawn).toContain('Safety  1')
    expect(drawn).toContain('AC-4  custom-x')
    // Routes 一行只能有 fixture 實際出現的值，不得補出固定類別（manual／e2e／database…）或「未標 type」組
    const routes = await pane.findAll({ type: 'Text', text: /^Routes / })
    expect(routes.map(found => found.text)).toEqual(['Routes  browser 2 · api 1 · custom-x 1'])
    const acLines = (await pane.findAll({ type: 'Text', text: /^AC-\d+ / })).map(found => found.text)
    expect(acLines).toEqual(['AC-1  browser', 'AC-2  api', 'AC-3  browser', 'AC-4  custom-x'])
    expect(drawn).not.toContain(TEXT.irUntyped)
    expect(drawn).not.toMatch(/ci-ready(?! ≠)/)
    // results.verify 摘要 key 存在才顯示
    expect(drawn).toContain('health_score  82')
    expect(drawn).toContain('mode  full')
  })

  test('IR 不存在 → 「尚未產生 E2E 候選」中性色；IR 壞掉 → 無法解析提示', async ($, on) => {
    const world = worldOf(
      on,
      specFiles({
        'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS,
        'push-tag-query/state.json': V2_FEATURE_VERIFY_WARN_BLOCKED,
        'push-tag-query/.cache/verification-ir.json': IR_MALFORMED,
      }),
    )

    await $.session.start(SESSION)
    await $.command.run(COMMAND())
    world.setState('feature-workflow', 'selectedSlug', 'order-export-csv')
    world.setState('feature-workflow', 'tab', 'verify')
    const pane = await mountPane($, 'terminal')
    const missing = textOf(await pane.drawn())
    expect(missing).toContain(TEXT.irMissing)
    const [irLine] = await textColors(pane, new RegExp(TEXT.irMissing))
    expect(irLine?.color, '中性色：不上 warning／error').toBe(undefined)
    expect(missing).toContain(TEXT.truthSeparator)

    world.setState('feature-workflow', 'selectedSlug', 'push-tag-query')
    await pane.redraw()
    const invalid = textOf(await pane.drawn())
    expect(invalid).toContain('Verification IR：檔案無法解析')
    expect(invalid).toContain('重新執行 /plan-verify 可重新產生。')
  })
})

describe('Batch 5 HUD＋composition（T-7、T-15）', () => {
  test('T-7：其他 mod 的 band（next(e)）與 HUD 同時存在', async ($, on) => {
    worldOf(on, specFiles({ 'push-tag-query/state.json': V2_FEATURE_VERIFY_WARN_BLOCKED }))
    on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'Text', props: {}, children: [OTHER_MOD] }) as never)

    await $.session.start(SESSION)
    const band = await mountBand($, 'terminal')
    const drawn = textOf(await band.drawn())

    expect(drawn).toContain(OTHER_MOD)
    expect(drawn).toContain('CREW · push-tag-query · feature / verify')
    expect(drawn.indexOf(OTHER_MOD)).toBeLessThan(drawn.indexOf('CREW ·'))
  })

  test('AC-4：寬畫面 2 行（slug／phase／驗收／停滯／＋N／上次建議／載入時間／權威入口）；窄畫面退成 1 行', async ($, on) => {
    worldOf(
      on,
      specFiles({
        'push-tag-query/state.json': V2_FEATURE_VERIFY_WARN_BLOCKED,
        'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS.replace('"updated": "2026-10-04T09:00:00+08:00"', '"updated": "2026-10-02T09:00:00+08:00"'),
      }),
    )
    nothingBeneathBand(on)

    await $.session.start(SESSION)
    const wide = await mountBand($, 'terminal')
    const wideTree = await wide.drawn()
    const wideText = textOf(wideTree)
    expect(wideText).toContain('CREW · push-tag-query · feature / verify · 中斷於 3/5 · 驗收 WARN（BLOCKED ×2） · 停滯 3 天 · ＋1 個進行中')
    expect(wideText).toContain(`${TEXT.uatPendingShort} · ${TEXT.recordedNextShort} /plan-verify --recheck · ${TEXT.loadedAt(formatClock(NOW))} · /plan-next push-tag-query`)
    expect(wideText).not.toMatch(/ci-ready/i)
    expect((await wide.findAll({ type: 'Box' })).filter(box => box.props.flexDirection === 'row')).toHaveLength(2)

    await wide.unmount()
    const narrow = await mountBand($, 'terminal', { bodyColumns: 50 })
    const narrowText = textOf(await narrow.drawn())
    expect(narrowText).toBe('CREW · push-tag-query · verify · BLOCKED ×2 · ＋1')
    expect((await narrow.findAll({ type: 'Box' })).filter(box => box.props.flexDirection === 'row')).toHaveLength(1)
  })

  test('AC-3：沒有 active task（只有 closed／parked）→ HUD 不佔空間，原樣放行', async ($, on) => {
    worldOf(on, specFiles({ 'profile-avatar-upload/state.json': V2_FEATURE_CLOSED, 'search-synonyms/state.json': V2_FEATURE_PARKED }))
    on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'Text', props: {}, children: [OTHER_MOD] }) as never)

    await $.session.start(SESSION)
    expect(textOf((await $.ui.render(BAND)) as never)).toBe(OTHER_MOD)
  })

  test('T-15：2 個沒有 state.json 的目錄 → 任務 tab 底部「另有 2 個…」；hud off → 放行、hud on → 恢復；hasSurvey → 放行', async ($, on) => {
    const world = worldOf(
      on,
      specFiles({
        'old-task/.state.lock': '',
        'no-state/plan.md': '# plan',
        'push-tag-query/state.json': V2_FEATURE_VERIFY_WARN_BLOCKED,
      }),
    )
    on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'Text', props: {}, children: [OTHER_MOD] }) as never)

    await $.session.start(SESSION)
    await $.command.run(COMMAND())
    const pane = await mountPane($, 'terminal')
    await pressAndRedraw(pane, 'tab-tasks')
    const tasks = textOf(await pane.drawn())
    expect(tasks).toContain(TEXT.untracked(2))
    expect(tasks.indexOf(TEXT.untracked(2))).toBeGreaterThan(tasks.indexOf('push-tag-query'))

    expect(textOf((await $.ui.render(BAND)) as never)).toContain('CREW · push-tag-query')

    expect(await $.command.run(COMMAND('hud off'))).toEqual({ text: TEXT.hudOff })
    expect(textOf((await $.ui.render(BAND)) as never)).toBe(OTHER_MOD)
    expect([...world.store.values()]).toEqual([false])
    expect([...world.store.keys()][0]?.startsWith('hud:')).toBe(true)

    expect(await $.command.run(COMMAND('hud on'))).toEqual({ text: TEXT.hudOn })
    expect(textOf((await $.ui.render(BAND)) as never)).toContain('CREW · push-tag-query')

    const survey = await $.ui.render({ ...BAND, props: { ...BAND.props, hasSurvey: true } })
    expect(textOf(survey as never)).toBe(OTHER_MOD)

    expect(await $.command.run(COMMAND('nonsense'))).toEqual({ text: TEXT.usageFull })
    expect(world.opened.length, 'hud 子指令不開 pane').toBe(1)
    expect(world.forbidden).toEqual([])
  })

  test('T-15：HUD 關閉持久化在 $.store，下個 session 啟動仍維持關閉（key 含 repo identity）', async ($, on) => {
    const world = worldOf(on, specFiles({ 'push-tag-query/state.json': V2_FEATURE_VERIFY_WARN_BLOCKED }))
    on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'Text', props: {}, children: [OTHER_MOD] }) as never)
    world.store.set(`hud:${ROOT}`, false)

    await $.session.start(SESSION)

    expect(world.stateOf('feature-workflow', 'hudEnabled')).toBe(false)
    expect(textOf((await $.ui.render(BAND)) as never)).toBe(OTHER_MOD)
  })
})

describe('Batch 6 Safe action：Fill（T-8、T-12）', () => {
  test('T-8：輸入框空白 → 先讀草稿、關 pane、再 fill 固定的 /plan-next {slug}（不是 state.next.command），不送出', async ($, on) => {
    const world = worldOf(on, specFiles({ 'push-tag-query/state.json': V2_FEATURE_VERIFY_WARN_BLOCKED }))

    await $.session.start(SESSION)
    await $.command.run(COMMAND())
    const pane = await mountPane($, 'terminal')
    await pressAndRedraw(pane, 'fill')

    // 引擎在 $.prompt.fill 之後會經 prompt.read 取回輸入框內容，所以只比對前三步的順序
    expect(world.promptLog.slice(0, 3)).toEqual(['prompt.read', 'ui.close crew-cockpit', 'prompt.fill'])
    expect(world.promptLog.filter(entry => entry !== 'prompt.read')).toEqual(['ui.close crew-cockpit', 'prompt.fill'])
    expect(world.filled).toEqual([{ text: '/plan-next push-tag-query', mode: 'replace' }])
    expect(world.filled[0]?.text).not.toBe('/plan-verify --recheck')
    expect(world.toasts).toEqual([])
    expect(world.forbidden, '全程不得 prompt.submit／寫檔').toEqual([])
  })

  test('T-8：輸入框有草稿 → 不 fill、不關 pane，toast 顯示指令', async ($, on) => {
    const world = worldOf(on, specFiles({ 'push-tag-query/state.json': V2_FEATURE_VERIFY_WARN_BLOCKED }))
    world.draft = '我打到一半的訊息'

    await $.session.start(SESSION)
    await $.command.run(COMMAND())
    const pane = await mountPane($, 'terminal')
    await pressAndRedraw(pane, 'fill')

    expect(world.promptLog).toEqual(['prompt.read'])
    expect(world.filled).toEqual([])
    expect(world.toasts).toEqual([TEXT.draftExists('/plan-next push-tag-query')])
    expect(world.forbidden).toEqual([])
  })

  for (const answer of [{ isFilled: false, refusal: 'dialog' as const }, { isFilled: false }]) {
    test(`T-12：prompt.fill 被拒（${answer.refusal ?? '無 refusal'}）→ toast 完整指令，不 crash`, async ($, on) => {
      const world = worldOf(on, specFiles({ 'push-tag-query/state.json': V2_FEATURE_VERIFY_WARN_BLOCKED }))
      world.fillAnswer = answer

      await $.session.start(SESSION)
      await $.command.run(COMMAND())
      const pane = await mountPane($, 'terminal')
      await pressAndRedraw(pane, 'fill')

      expect(world.filled).toEqual([{ text: '/plan-next push-tag-query', mode: 'replace' }])
      expect(world.toasts).toEqual([TEXT.fillRefused('/plan-next push-tag-query')])
      expect(world.forbidden).toEqual([])
      // session 仍正常：之後的 turn 與 render 照常
      expect(await $.turn.complete(TURN() as never)).toEqual({ text: 'ok' })
    })
  }
})

describe('Lifecycle（T-9、T-13）', () => {
  test('T-9：改 fixture 後主 turn.complete → 畫面反映新 snapshot；只重讀 mtime 變了的那個檔', async ($, on) => {
    const world = worldOf(
      on,
      specFiles({
        'push-tag-query/state.json': V2_FEATURE_VERIFY_WARN_BLOCKED,
        'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS,
      }),
    )
    nothingBeneathBand(on)

    await $.session.start(SESSION)
    await $.command.run(COMMAND())
    world.setState('feature-workflow', 'selectedSlug', 'order-export-csv')
    const pane = await mountPane($, 'terminal')
    const band = await mountBand($, 'terminal')
    expect(textOf(await pane.drawn())).toContain('feature · verify')

    world.put(`${ROOT}/.spec/order-export-csv/state.json`, V2_FEATURE_VERIFY_PASS.replace('"phase": "verify"', '"phase": "review"'))
    world.asked.length = 0
    await $.turn.complete(TURN() as never)

    expect(world.asked.filter(entry => entry.startsWith('read '))).toEqual([`read ${ROOT}/.spec/order-export-csv/state.json`])
    await pane.redraw()
    await band.redraw()
    expect(textOf(await pane.drawn())).toContain('feature · review')
    expect(textOf(await band.drawn())).toContain('CREW · order-export-csv · feature / review')
  })

  test('refresh 競態：較早開始、較晚讀完的 refresh 不得覆蓋較新的 snapshot（世代號）', async ($, on) => {
    const statePath = `${ROOT}/.spec/order-export-csv/state.json`
    const world = worldOf(on, specFiles({ 'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS }))

    await $.session.start(SESSION)
    expect(taskOf(snapshotOf(world), 'order-export-csv').phase).toBe('verify')

    // A：讀到 review 後卡住（慢 I/O）
    world.put(statePath, V2_FEATURE_VERIFY_PASS.replace('"phase": "verify"', '"phase": "review"'))
    const release = world.holdNextRead(statePath)
    world.asked.length = 0
    const slow = $.turn.complete(TURN() as never)
    for (let i = 0; i < 50 && !world.asked.includes(`read ${statePath}`); i += 1) {
      await sleep(5)
    }
    expect(world.asked, '正對照：A 確實已在讀檔途中').toContain(`read ${statePath}`)

    // B：之後開始、先讀完（close）並寫入
    world.put(statePath, V2_FEATURE_VERIFY_PASS.replace('"phase": "verify"', '"phase": "close"'))
    await $.command.run(COMMAND())
    expect(taskOf(snapshotOf(world), 'order-export-csv').phase).toBe('close')

    // 放行 A：它的結果較舊，必須丟棄
    release()
    await slow
    expect(taskOf(snapshotOf(world), 'order-export-csv').phase, '舊世代的 refresh 不得覆蓋').toBe('close')
    expect(world.stateOf('feature-workflow', 'runtime')).toMatchObject({ isSupported: true, refreshGeneration: 3 })

    // 之後的 refresh 照常生效（世代號沒有卡死）
    world.put(statePath, V2_FEATURE_VERIFY_PASS.replace('"phase": "verify"', '"phase": "security"'))
    await $.turn.complete(TURN() as never)
    expect(taskOf(snapshotOf(world), 'order-export-csv').phase).toBe('security')
  })

  test('T-13：子代理 turn.complete → 0 次 fs.list／fs.read，回傳 next(e) 的結果', async ($, on) => {
    const world = worldOf(on, specFiles({ 'push-tag-query/state.json': V2_FEATURE_VERIFY_WARN_BLOCKED }))

    await $.session.start(SESSION)
    world.asked.length = 0
    const result = await $.turn.complete(TURN('agent-7') as never)

    expect(result).toEqual({ text: 'ok' })
    expect(world.asked.filter(entry => entry.startsWith('list ') || entry.startsWith('read '))).toEqual([])
  })
})

describe('T-10 Desktop＋Terminal', () => {
  for (const surface of SURFACES) {
    test(`${surface}：Pane 三個 tab 與 HUD 都能繪製（只用 baseline 元素）`, async ($, on) => {
      const world = worldOf(
        on,
        specFiles({
          'push-tag-query/state.json': V2_FEATURE_VERIFY_WARN_BLOCKED,
          'push-tag-query/.cache/verification-ir.json': VERIFICATION_IR,
          'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS,
        }),
      )
      nothingBeneathBand(on)

      await $.session.start(SESSION)
      await $.command.run(COMMAND())
      world.setState('feature-workflow', 'selectedSlug', 'push-tag-query')
      const pane = await mountPane($, surface)

      expect(textOf(await pane.drawn())).toContain('verify    WARN（BLOCKED ×2）')
      await pressAndRedraw(pane, 'tab-tasks')
      expect(textOf(await pane.drawn())).toContain('order-export-csv')
      await pressAndRedraw(pane, 'tab-verify')
      const verifyTab = textOf(await pane.drawn())
      expect(verifyTab).toContain('Routes  browser 2 · api 1 · custom-x 1')
      expect(verifyTab).toContain(TEXT.blockedNote(2))

      const types = new Set((await pane.findAll({})).map(found => found.type))
      expect([...types].every(type => ['Box', 'Text', 'Button'].includes(type))).toBe(true)

      const band = await mountBand($, surface)
      expect(textOf(await band.drawn())).toContain('CREW · push-tag-query')

      await pane.unmount()
      const narrow = await mountPane($, surface, 40)
      await pressAndRedraw(narrow, 'tab-tasks')
      expect(textOf(await narrow.drawn())).toContain('push-tag-query')
      expect(world.forbidden).toEqual([])
    })
  }
})

describe('D-3／AC-13 render 純度：ui.render 期間不做 I/O', () => {
  test('快照載入後，Pane 三個 tab 與 AbovePrompt 的 mount／redraw 不新增任何 fs 呼叫，也沒有被拒的 I/O', async ($, on) => {
    const world = worldOf(
      on,
      specFiles({
        'push-tag-query/state.json': V2_FEATURE_VERIFY_WARN_BLOCKED,
        'push-tag-query/.cache/verification-ir.json': VERIFICATION_IR,
        'order-export-csv/state.json': V2_FEATURE_VERIFY_PASS,
      }),
    )
    nothingBeneathBand(on)

    await $.session.start(SESSION)
    await $.command.run(COMMAND())
    // 正對照：載入階段一定讀過檔，證明 world.asked 看得見 fs 呼叫（下方「不變」不是空轉）
    expect(world.asked.some(entry => entry.startsWith('read ')), 'spy 必須看得到載入期的 fs.read').toBe(true)

    const askedBefore = [...world.asked]
    const forbiddenBefore = [...world.forbidden]

    const pane = await mountPane($, 'terminal')
    for (const tab of ['overview', 'tasks', 'verify']) {
      world.setState('feature-workflow', 'tab', tab)
      await pane.redraw()
      expect(textOf(await pane.drawn()).length, `${tab} tab 要真的畫出內容`).toBeGreaterThan(0)
    }
    const band = await mountBand($, 'terminal')
    await band.redraw()
    expect(textOf(await band.drawn())).toContain('CREW · ')

    // render 期間不得新增任何 fs 呼叫（read／list／stat／exists），也不得出現被拒的 I/O
    expect(world.asked).toEqual(askedBefore)
    expect(world.forbidden).toEqual(forbiddenBefore)
    expect(world.forbidden).toEqual([])
  })
})
