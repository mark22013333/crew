// CREW Cockpit：feature-workflow 在 Claude Code 上的唯讀視覺化層（Mods 模組入口）。
//
// Core owns truth. Cockpit owns presentation.
// - 不寫 .spec/{slug}/state.json、不跑 crew-state.py、不送出 prompt、不攔截 tool.call（規格 §0、§3 D-2）。
// - snapshot 只在 session.start／主 turn 結束／/crew-cockpit／重新整理時重讀，存進 $.state；render 只讀 $.state（§3 D-3、§15）。
// - 唯一的「動作」是 Fill：把固定模板 `/plan-next {slug}` 或 `/plan-close {slug}` 填進空的輸入框，絕不送出（§14）。
// - 任何 Cockpit 錯誤都只吞掉並放行，不阻擋 Claude Code 正常工作（§16）。

import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, RenderElement } from 'claude-code'

import { type LoaderPorts, loadCockpitSnapshot } from './cockpit/loader'
import { COMMAND_NAME, MIN_CLAUDE_CODE_VERSION, PANE_ID, TEXT, type CockpitTab, type CockpitTaskLayout, compareVersions } from './cockpit/model'
import { type PaneCallbacks, composeBand, hudModel, hudView, paneView } from './cockpit/render'
import { type FillKind, fillTemplateFor } from './cockpit/selectors'

// ---------------------------------------------------------------------------
// $.state 參照（契約在 types/index.d.ts）。
// Mods 規定：state 參照必須在「本檔」以字面值 plugin/key 宣告（atom 寫在本檔的 const），
// validate 才能列出模組讀寫哪些 state；不能從別的檔案 import。寫入只在 handler／事件 hook，ui.render 只讀。
// ---------------------------------------------------------------------------

/** 最新讀取模型；尚未載入為 null。 */
export const snapshotAtom = atom({ plugin: 'feature-workflow', key: 'snapshot' } as const, null)

/** 使用者本 session 選的 task id（UI state，不是 workflow state）。 */
export const selectedSlugAtom = atom({ plugin: 'feature-workflow', key: 'selectedSlug' } as const, null)

/** pane 目前的 tab。 */
export const tabAtom = atom({ plugin: 'feature-workflow', key: 'tab' } as const, 'overview')

/** HUD 開關鏡像（§9.4；預設開啟；持久化值在 $.store）。 */
export const hudEnabledAtom = atom({ plugin: 'feature-workflow', key: 'hudEnabled' } as const, true)

/** 版本檢查結果（§19）；尚未檢查為 null。 */
export const runtimeAtom = atom({ plugin: 'feature-workflow', key: 'runtime' } as const, null)

/**
 * 把 loader 需要的唯讀 I/O 綁到 $。Mods 規定 $ 只能在本檔以 `$.noun.event(...)` 的形式出現，
 * 不能跨 import 傳遞，validate 才能從原始碼讀出模組實際呼叫了什麼。這裡刻意沒有任何寫入能力。
 */
function portsOf($: EngineInterface): LoaderPorts {
  return {
    list: path => $.fs.list(path),
    stat: path => $.fs.stat(path),
    exists: path => $.fs.exists(path),
    read: path => $.fs.read(path),
    sessionRoot: () => $.session.root(),
    repo: () => $.session.repo(),
    now: () => $.clock.now(),
  }
}

/**
 * 重新載入 snapshot 並寫進 $.state（讀者自動重繪）。失敗不 throw。
 * 競態：多次 refresh 可能並行（turn.complete、重新整理按鈕、/crew-cockpit），較早開始的那次可能較晚讀完。
 * 每次先在 runtime 領一個遞增世代號，讀完時只有「仍是最新世代」的結果才寫入，舊結果直接丟棄。
 */
export async function refreshSnapshot($: EngineInterface): Promise<void> {
  try {
    const claimed = await update($, runtimeAtom, current => ({
      // 保留 runtime 上的 UI state（isClosedExpanded），refresh 不得把展開狀態重設
      ...current,
      isSupported: current?.isSupported ?? false,
      version: current?.version ?? null,
      minimum: current?.minimum ?? MIN_CLAUDE_CODE_VERSION,
      refreshGeneration: (current?.refreshGeneration ?? 0) + 1,
    }))
    const generation = claimed?.refreshGeneration ?? 0
    const previous = await read($, snapshotAtom)
    const userSelectedSlug = await read($, selectedSlugAtom)
    const snapshot = await loadCockpitSnapshot(portsOf($), { previous, userSelectedSlug })
    const latest = (await read($, runtimeAtom))?.refreshGeneration ?? 0
    if (latest !== generation) {
      // 已有較新的 refresh 開始（可能已寫入）：這份是舊的，不得覆蓋
      return
    }
    await update($, snapshotAtom, () => snapshot)
  } catch {
    // §16：Cockpit error → pass through
  }
}

const checkVersion = async ($: EngineInterface): Promise<boolean> => {
  try {
    const { version } = await $.session.version()
    // 區域變數不可與模組層的 isSupported() 同名：Claude Code 2.1.289 的載入檢查會判為重複宣告而拒載整個 Mod
    const supported = compareVersions(version, MIN_CLAUDE_CODE_VERSION) >= 0
    // 保留 refreshGeneration：重設會讓世代號倒退，與進行中的 refresh 比對失準
    await update($, runtimeAtom, current => ({ ...current, isSupported: supported, version, minimum: MIN_CLAUDE_CODE_VERSION }))
    return supported
  } catch {
    return false
  }
}

const isSupported = async ($: EngineInterface): Promise<boolean> => (await read($, runtimeAtom))?.isSupported === true

// ---------------------------------------------------------------------------
// §9.4 HUD 開關：$.store 持久化（key 含 repo identity），$.state hudEnabled 鏡像給 render 讀。
// ---------------------------------------------------------------------------

/** $.store 的偏好 key：`{prefix}:{repo.remote ?? repoRoot ?? session root}`（每個 repo 一份）。 */
async function prefStoreKey($: EngineInterface, prefix: 'hud' | 'layout'): Promise<string> {
  const repo = await $.session.repo().catch(() => null)
  if (repo?.remote) {
    return `${prefix}:${repo.remote}`
  }
  const snapshot = await read($, snapshotAtom).catch(() => null)
  if (snapshot?.repoRoot) {
    return `${prefix}:${snapshot.repoRoot}`
  }
  return `${prefix}:${repo?.root ?? (await $.session.root())}`
}

/** $.store 的 HUD 開關 key：`hud:{repo.remote ?? repoRoot ?? session root}`。 */
const hudStoreKey = ($: EngineInterface): Promise<string> => prefStoreKey($, 'hud')

/** session.start：把持久化的 HUD 開關鏡像到 $.state（缺值＝預設開啟）。 */
async function loadHudPreference($: EngineInterface): Promise<void> {
  try {
    const stored = await $.store.get(await hudStoreKey($))
    await update($, hudEnabledAtom, () => stored !== false)
  } catch {
    // §16：讀不到偏好就維持預設
  }
}

async function setHudPreference($: EngineInterface, isEnabled: boolean): Promise<void> {
  await update($, hudEnabledAtom, () => isEnabled)
  try {
    await $.store.set(await hudStoreKey($), isEnabled)
  } catch {
    // 持久化失敗只影響下個 session；本 session 已生效
  }
}

// ---------------------------------------------------------------------------
// 任務 tab 版面偏好：$.store 持久化（key `layout:{repo identity}`，比照 HUD），
// $.state runtime.taskLayout 鏡像給 render 讀（放 runtime 而非新 key，capability baseline 不變）。
// ---------------------------------------------------------------------------

const asLayout = (value: unknown): CockpitTaskLayout => (value === 'cards' ? 'cards' : 'list')

async function writeLayoutMirror($: EngineInterface, layout: CockpitTaskLayout): Promise<void> {
  await update($, runtimeAtom, current => (current === null ? current : { ...current, taskLayout: layout }))
}

/** session.start：把持久化的版面鏡像到 runtime（缺值＝列表）。 */
async function loadLayoutPreference($: EngineInterface): Promise<void> {
  try {
    const stored = await $.store.get(await prefStoreKey($, 'layout'))
    await writeLayoutMirror($, asLayout(stored))
  } catch {
    // §16：讀不到偏好就維持預設（列表）
  }
}

async function setLayoutPreference($: EngineInterface, layout: CockpitTaskLayout): Promise<void> {
  await writeLayoutMirror($, layout).catch(() => undefined)
  try {
    await $.store.set(await prefStoreKey($, 'layout'), layout)
  } catch {
    // 持久化失敗只影響下個 session；本 session 已生效
  }
}

// ---------------------------------------------------------------------------
// §14 Fill：只填固定模板 `/plan-next {slug}`／`/plan-close {slug}`；先讀草稿（不覆蓋）→ 開著 pane 直接 fill →
// 被拒才關 pane 再 fill 一次 → 仍被拒就 toast。
// 依使用者指示調整規格 §14／B1 的保守預設（原本一律先關 pane）：使用者不希望按填入後 Cockpit 消失。
// 兩種模板共用同一條流程，差別只在 fillTemplateFor 選哪個固定模板。
// ---------------------------------------------------------------------------

async function fillOnce($: EngineInterface, command: string): Promise<boolean> {
  const filled = await $.prompt.fill({ text: command, mode: 'replace' })
  return filled.isFilled
}

async function fillTemplate($: EngineInterface, taskId: string, kind: FillKind): Promise<void> {
  const snapshot = await read($, snapshotAtom).catch(() => null)
  const task = snapshot?.tasks.find(item => item.id === taskId) ?? null
  // 內容只由固定模板＋白名單 slug 組成；不用 state.next.command 或任何 render 傳來的字串
  const command = fillTemplateFor(task, kind)
  if (command === null) {
    return
  }
  try {
    const box = await $.prompt.read()
    if (box.text !== '') {
      $.ui.toast(TEXT.draftExists(command))
      return
    }
    if (await fillOnce($, command)) {
      // 成功：pane 保持開啟。Mods API 沒有把鍵盤交還輸入框的呼叫（$.ui.focus 只能在本 plugin 的 site 內移動焦點），
      // 所以 pane 仍持有鍵盤時提示使用者按 Esc 回輸入框再 Enter 送出（pane 不設 closeOnEscape，Esc 只交還鍵盤、不關 pane）。
      const panes = await $.ui.panes().catch(() => [])
      if (panes.some(pane => pane.id === PANE_ID && pane.isFocused)) {
        $.ui.toast(TEXT.filledKeepPane(command))
      }
      return
    }
    // 被拒（refusal 為 dialog／no_composer／缺省＝被其他 hook 擋下）：退回原本的保守做法，關 pane 後再填一次
    await $.ui.close({ id: PANE_ID }).catch(() => undefined)
    if (!(await fillOnce($, command))) {
      $.ui.toast(TEXT.fillRefused(command))
    }
  } catch {
    $.ui.toast(TEXT.fillRefused(command))
  }
}

/** Pane 按鈕的處理：只改 UI state（tab／selection）、重讀 snapshot、或 Fill；不寫任何 project file。 */
function paneCallbacks($: EngineInterface): PaneCallbacks {
  return {
    selectTab: async (tab: CockpitTab) => {
      await update($, tabAtom, () => tab).catch(() => undefined)
    },
    selectTask: async (id: string) => {
      await update($, selectedSlugAtom, () => id).catch(() => undefined)
      await update($, tabAtom, () => 'overview' as const).catch(() => undefined)
    },
    refresh: () => refreshSnapshot($),
    fill: (id: string, kind: FillKind = 'next') => fillTemplate($, id, kind).catch(() => undefined),
    toggleClosed: async () => {
      // 展開狀態只存 UI state（runtime.isClosedExpanded），不寫任何 project file
      await update($, runtimeAtom, current => (current === null ? current : { ...current, isClosedExpanded: current.isClosedExpanded !== true })).catch(
        () => undefined,
      )
    },
    setLayout: (layout: CockpitTaskLayout) => setLayoutPreference($, layout),
  }
}

/** /crew-cockpit 的參數：空白＝開 pane；`hud on|off`＝HUD 開關；其他＝用法。 */
function parseArgs(args: string): 'open' | 'hud-on' | 'hud-off' | 'usage' {
  const words = args.trim().toLowerCase().split(/\s+/).filter(word => word !== '')
  if (words.length === 0) {
    return 'open'
  }
  if (words.length === 2 && words[0] === 'hud' && (words[1] === 'on' || words[1] === 'off')) {
    return words[1] === 'on' ? 'hud-on' : 'hud-off'
  }
  return 'usage'
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    try {
      await $.command.register({
        name: COMMAND_NAME,
        description: '開啟 CREW Cockpit：唯讀檢視 .spec 任務、phase、核准閘與驗收狀態（hud on|off 開關 HUD）',
        argumentHint: '[hud on|off]',
        immediate: true,
      })
      if (await checkVersion($)) {
        await refreshSnapshot($)
        await loadHudPreference($)
        await loadLayoutPreference($)
      }
    } catch {
      // §16：不阻擋 session
    }
    return next(e)
  })

  on('command.run', { command: 'crew-cockpit' }, async ($, e) => {
    try {
      if (!(await isSupported($))) {
        return { text: TEXT.needVersion(MIN_CLAUDE_CODE_VERSION) }
      }
      const action = parseArgs(e.args ?? '')
      if (action === 'hud-on' || action === 'hud-off') {
        await setHudPreference($, action === 'hud-on')
        return { text: action === 'hud-on' ? TEXT.hudOn : TEXT.hudOff }
      }
      if (action === 'usage') {
        return { text: TEXT.usageFull }
      }
      await refreshSnapshot($)
      // §10：先問引擎 pane 是否已開著（熱重載後模組不記得，但引擎記得），已開就不重複開啟
      const panes = await $.ui.panes().catch(() => [])
      const existing = panes.find(pane => pane.id === PANE_ID)
      if (existing !== undefined) {
        if (!existing.isPlaced) {
          $.ui.toast(TEXT.paneNotPlaced)
        }
        return { text: TEXT.paneOpened }
      }
      // 不設 holdToasts：否則 pane 變成 dialog，所有 toast 都要等它關閉（§10）
      // 不設 closeOnEscape：Fill 後 pane 保持開啟，Esc 只把鍵盤交還輸入框、不關 pane；關閉用 pane 的關閉鈕或 ctrl+x x
      const opened = await $.ui.open({ id: PANE_ID, title: TEXT.paneTitle, focus: true })
      if (!opened.isPlaced) {
        $.ui.toast(TEXT.paneNotPlaced)
      }
      return { text: TEXT.paneOpened }
    } catch {
      return { text: TEXT.paneOpened }
    }
  })

  on('turn.complete', async ($, e, next) => {
    // §15：只在主 turn 結束時刷新；子代理（帶 agentId）不重掃
    if (e.agentId === undefined && (await isSupported($).catch(() => false))) {
      await refreshSnapshot($)
    }
    return next(e)
  })

  on('ui.render', { component: 'Pane', requestId: 'crew-cockpit' }, async ($, e, next) => {
    try {
      if (!(await isSupported($))) {
        return next(e)
      }
      const { Box, Text, Button } = $.ui.resolve(e)
      const runtime = await read($, runtimeAtom)
      const data = {
        snapshot: await read($, snapshotAtom),
        selectedSlug: await read($, selectedSlugAtom),
        tab: await read($, tabAtom),
        bodyColumns: e.props.bodyColumns,
        isClosedExpanded: runtime?.isClosedExpanded === true,
        taskLayout: asLayout(runtime?.taskLayout),
      }
      return paneView({ Box, Text, Button }, data, paneCallbacks($))
    } catch {
      return next(e)
    }
  })

  // §9 AbovePrompt HUD：一律 compose next(e)，不蓋掉其他 mod 的 band；survey、關閉、無 active task 時直接放行。
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    let lines: ReturnType<typeof hudModel> = null
    try {
      if (!e.props.hasSurvey && (await isSupported($)) && (await read($, hudEnabledAtom))) {
        lines = hudModel({
          snapshot: await read($, snapshotAtom),
          selectedSlug: await read($, selectedSlugAtom),
          bodyColumns: e.props.bodyColumns,
        })
      }
    } catch {
      lines = null
    }
    if (lines === null) {
      return next(e)
    }
    const other: RenderElement | null | undefined = await next(e)
    try {
      const { Box, Text, Button } = $.ui.resolve(e)
      const kit = { Box, Text, Button }
      return composeBand(kit, other, hudView(kit, lines, e.props.bodyColumns))
    } catch {
      return other
    }
  })
}
