// CREW Cockpit：feature-workflow 在 Claude Code 上的唯讀視覺化層（Mods 模組入口）。
//
// Core owns truth. Cockpit owns presentation.
// - 不寫 .spec/{slug}/state.json、不跑 crew-state.py、不 submit prompt、不攔截 tool.call（規格 §0、§3 D-2）。
// - snapshot 只在 session.start／主 turn 結束／/crew-cockpit 時重讀，存進 $.state；render 只讀 $.state（§3 D-3、§15）。
// - 任何 Cockpit 錯誤都只吞掉並放行，不阻擋 Claude Code 正常工作（§16）。

import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import { type LoaderPorts, loadCockpitSnapshot } from './cockpit/loader'
import { COMMAND_NAME, MIN_CLAUDE_CODE_VERSION, PANE_ID, TEXT, compareVersions } from './cockpit/model'
import { paneStubView } from './cockpit/render'

// ---------------------------------------------------------------------------
// $.state 參照（契約在 types/index.d.ts）。
// Mods 規定：state 參照必須在「本檔」以字面值 plugin/key 宣告（atom 寫在本檔的 const），
// validate 才能列出模組讀寫哪些 state；不能從別的檔案 import。寫入只在 handler／事件 hook，ui.render 只讀。
// ---------------------------------------------------------------------------

/** 最新讀取模型；尚未載入為 null。 */
export const snapshotAtom = atom({ plugin: 'feature-workflow', key: 'snapshot' } as const, null)

/** 使用者本 session 選的 task id（UI state，不是 workflow state）。 */
export const selectedSlugAtom = atom({ plugin: 'feature-workflow', key: 'selectedSlug' } as const, null)

/** pane 目前的 tab（Batch 3 使用）。 */
export const tabAtom = atom({ plugin: 'feature-workflow', key: 'tab' } as const, 'overview')

/** HUD 開關鏡像（§9.4；預設開啟，Batch 5 使用）。 */
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

/** 重新載入 snapshot 並寫進 $.state（讀者自動重繪）。失敗不 throw。 */
export async function refreshSnapshot($: EngineInterface): Promise<void> {
  try {
    const previous = await read($, snapshotAtom)
    const userSelectedSlug = await read($, selectedSlugAtom)
    const snapshot = await loadCockpitSnapshot(portsOf($), { previous, userSelectedSlug })
    await update($, snapshotAtom, () => snapshot)
  } catch {
    // §16：Cockpit error → pass through
  }
}

const checkVersion = async ($: EngineInterface): Promise<boolean> => {
  try {
    const { version } = await $.session.version()
    const isSupported = compareVersions(version, MIN_CLAUDE_CODE_VERSION) >= 0
    await update($, runtimeAtom, () => ({ isSupported, version, minimum: MIN_CLAUDE_CODE_VERSION }))
    return isSupported
  } catch {
    return false
  }
}

const isSupported = async ($: EngineInterface): Promise<boolean> => (await read($, runtimeAtom))?.isSupported === true

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    try {
      await $.command.register({
        name: COMMAND_NAME,
        description: '開啟 CREW Cockpit：唯讀檢視 .spec 任務、phase、核准閘與驗收狀態',
        immediate: true,
      })
      if (await checkVersion($)) {
        await refreshSnapshot($)
      }
    } catch {
      // §16：不阻擋 session
    }
    return next(e)
  })

  on('command.run', { command: 'crew-cockpit' }, async $ => {
    try {
      if (!(await isSupported($))) {
        return { text: TEXT.needVersion(MIN_CLAUDE_CODE_VERSION) }
      }
      await refreshSnapshot($)
      const opened = await $.ui.open({ id: PANE_ID, title: TEXT.paneTitle, focus: true, closeOnEscape: true })
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
      const { Box, Text } = $.ui.resolve(e)
      return paneStubView({ Box, Text }, await read($, snapshotAtom))
    } catch {
      return next(e)
    }
  })
}
