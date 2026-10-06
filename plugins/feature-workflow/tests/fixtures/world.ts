// 測試用的記憶體世界：以 fs／session／clock hook 注入 fixture（規格 §22「Fixture 注入方式」），
// 同時當 spy，記錄有沒有發生 fs.write、process、model、prompt.submit、http 呼叫。
// 結構參考官方 code-modernization plugin 的 tests/fixtures/world.ts。

import type { On, RenderElement, RenderNode } from 'claude-code'

export const ROOT = '/work/repo'

/** 固定的「現在」：2026-10-06T12:00:00+08:00。 */
export const NOW = Date.UTC(2026, 9, 6, 4, 0, 0)

export type World = {
  /** 絕對路徑 → 檔案文字。 */
  files: Map<string, string>
  mtimes: Map<string, number>
  /** 依序記錄每個 fs 呼叫（`read <path>`、`list <path>`、`stat <path>`、`exists <path>`）。 */
  asked: string[]
  /** 不得發生的呼叫（fs.write、process.run、model.complete、prompt.submit、http.fetch）。 */
  forbidden: string[]
  commands: { name: string; immediate: boolean }[]
  opened: { id: string; focus: boolean; closeOnEscape: boolean; holdToasts: boolean }[]
  toasts: string[]
  /** 輸入框目前的草稿（$.prompt.read 的回答）。 */
  draft: string
  /** prompt.fill 的回答（預設接受）；改成 { isFilled: false, refusal } 模擬被拒。 */
  fillAnswer: { isFilled: boolean; refusal?: 'no_composer' | 'dialog' }
  /** 每次 prompt.fill 的內容。 */
  filled: { text: string; mode: string }[]
  /** 依序記錄 prompt.read／ui.close／prompt.fill（驗 Fill 流程順序）。 */
  promptLog: string[]
  /** $.store 的記憶體實作。 */
  store: Map<string, unknown>
  /** 改檔：內容與 mtime 一起變（像外部工具寫檔）。 */
  put: (path: string, text: string) => void
  /** 測試的 $ 沒有 state noun：$.state 由這裡的記憶體實作回答（測試 hook 就是引擎底層）。 */
  stateOf: (plugin: string, key: string) => unknown
  /** 模擬「別處」寫入 plugin 的 state（例如使用者在 Tasks tab 點選）。 */
  setState: (plugin: string, key: string, value: unknown) => void
}

export type WorldOptions = {
  /** $.session.root() 的值；預設 ROOT。 */
  sessionRoot?: string
  /** $.session.repo() 的值；預設 { root: ROOT }。null 表示不在 git repo。 */
  gitRoot?: string | null
  /** Claude Code 版本；預設 2.1.291。 */
  version?: string
  /** 視為「存在的空目錄」的絕對路徑。 */
  dirs?: readonly string[]
}

/** 以 .spec 相對路徑描述 fixture：{ 'push-tag-query/state.json': '...' }。 */
export const specFiles = (entries: Readonly<Record<string, string>>, root: string = ROOT): Record<string, string> =>
  Object.fromEntries(Object.entries(entries).map(([rel, text]) => [`${root}/.spec/${rel}`, text]))

/** 把記憶體世界接到 plugin 底下。 */
export function worldOf(on: On, files: Readonly<Record<string, string>>, options: WorldOptions = {}): World {
  let tick = 10_000
  const extraDirs = new Set(options.dirs ?? [])

  const states = new Map<string, { value: unknown; version: number }>()
  const stateKey = (plugin: string, key: string, id?: string) => `${plugin}\u0000${key}\u0000${id ?? ''}`

  const world: World = {
    files: new Map(Object.entries(files)),
    mtimes: new Map(Object.keys(files).map(path => [path, 1_000])),
    asked: [],
    forbidden: [],
    commands: [],
    opened: [],
    toasts: [],
    draft: '',
    fillAnswer: { isFilled: true },
    filled: [],
    promptLog: [],
    store: new Map(),
    put: (path, text) => {
      tick += 1_000
      world.files.set(path, text)
      world.mtimes.set(path, tick)
    },
    stateOf: (plugin, key) => states.get(stateKey(plugin, key))?.value,
    setState: (plugin, key, value) => {
      const current = states.get(stateKey(plugin, key))
      states.set(stateKey(plugin, key), { value, version: (current?.version ?? 0) + 1 })
    },
  }

  on('state.get', ($, e) => {
    const current = states.get(stateKey(e.plugin, e.key, e.id))
    return { value: current ?? { value: undefined, version: 0 } } as never
  })

  on('state.set', ($, e) => {
    const k = stateKey(e.plugin, e.key, e.id)
    const version = states.get(k)?.version ?? 0
    if (e.ifVersion !== undefined && e.ifVersion !== version) {
      return { value: { isSet: false, version } } as never
    }
    states.set(k, { value: e.value, version: version + 1 })
    return { value: { isSet: true, version: version + 1 } } as never
  })

  const strip = (path: string) => path.replace(/\/+$/, '')
  const isDir = (path: string) => {
    const dir = strip(path)
    return extraDirs.has(dir) || [...world.files.keys()].some(file => file.startsWith(`${dir}/`))
  }

  on('fs.read', ($, e) => {
    world.asked.push(`read ${e.path}`)
    const text = world.files.get(e.path)
    return text === undefined ? { deny: `ENOENT: ${e.path}` } : { value: text }
  })

  on('fs.exists', ($, e) => {
    world.asked.push(`exists ${e.path}`)
    return { value: world.files.has(e.path) || isDir(e.path) }
  })

  on('fs.stat', ($, e) => {
    world.asked.push(`stat ${e.path}`)
    const text = world.files.get(e.path)
    if (text !== undefined) {
      return { value: { kind: 'file' as const, size: text.length, mtimeMs: world.mtimes.get(e.path) ?? 0, isLink: false } }
    }
    return isDir(e.path)
      ? { value: { kind: 'dir' as const, size: 0, mtimeMs: 0, isLink: false } }
      : { deny: `ENOENT: ${e.path}` }
  })

  on('fs.list', ($, e) => {
    world.asked.push(`list ${e.path}`)
    const dir = strip(e.path)
    if (!isDir(dir)) {
      return { deny: `ENOENT: ${e.path}` }
    }
    const names = new Map<string, 'file' | 'dir'>()
    for (const file of world.files.keys()) {
      if (!file.startsWith(`${dir}/`)) {
        continue
      }
      const rest = file.slice(dir.length + 1)
      names.set(rest.split('/')[0] ?? '', rest.includes('/') ? 'dir' : 'file')
    }
    for (const extra of extraDirs) {
      if (extra.startsWith(`${dir}/`)) {
        names.set(extra.slice(dir.length + 1).split('/')[0] ?? '', 'dir')
      }
    }
    return {
      value: [...names.entries()].sort().map(([name, kind]) => ({
        name,
        kind,
        size: kind === 'file' ? (world.files.get(`${dir}/${name}`)?.length ?? 0) : 0,
        mtimeMs: kind === 'file' ? (world.mtimes.get(`${dir}/${name}`) ?? 0) : 0,
        isLink: false,
      })),
    }
  })

  // ---- 不得發生的呼叫：spy 後拒絕 ----
  on('fs.write', ($, e) => {
    world.forbidden.push(`fs.write ${e.path}`)
    return { deny: 'Cockpit 不得寫檔' }
  })
  on('process.run', () => {
    world.forbidden.push('process.run')
    return { deny: 'Cockpit 不得執行 process' }
  })
  on('model.complete', () => {
    world.forbidden.push('model.complete')
    return { deny: 'Cockpit 不得呼叫 model' }
  })
  on('http.fetch', () => {
    world.forbidden.push('http.fetch')
    return { deny: 'Cockpit 不得連網' }
  })
  on('prompt.submit', ($, e) => {
    world.forbidden.push('prompt.submit')
    return { text: e.text }
  })

  // ---- session／clock ----
  on('session.root', () => ({ value: options.sessionRoot ?? ROOT }))
  on('session.cwd', () => ({ value: options.sessionRoot ?? ROOT }))
  on('session.repo', () => ({
    value:
      options.gitRoot === null
        ? null
        : { root: options.gitRoot ?? ROOT, remote: null, internal: false, name: null },
  }))
  on('session.version', () => ({ value: { version: options.version ?? '2.1.291' } }))
  on('clock.now', () => ({ value: NOW }))

  // ---- ui／command ----
  on('command.register', ($, e) => {
    world.commands.push({ name: e.name, immediate: e.immediate === true })
    return { value: { command: e.name } }
  })
  on('ui.open', ($, e) => {
    world.opened.push({
      id: e.id,
      focus: e.focus === true,
      closeOnEscape: e.closeOnEscape === true,
      holdToasts: e.holdToasts === true,
    })
    return { value: { isPlaced: true } } as never
  })
  on('ui.toast', ($, e) => {
    world.toasts.push(e.text)
    return { value: undefined }
  })
  on('ui.close', ($, e) => {
    world.promptLog.push(`ui.close ${e.id}`)
    return { value: undefined }
  })
  on('prompt.read', () => {
    world.promptLog.push('prompt.read')
    return { value: { text: world.draft, cursor: world.draft.length } }
  })
  on('prompt.fill', ($, e) => {
    world.promptLog.push('prompt.fill')
    world.filled.push({ text: e.text, mode: e.mode })
    return world.fillAnswer
  })
  on('store.get', ($, e) => ({ value: world.store.get(e.key) }))
  on('store.set', ($, e) => {
    world.store.set(e.key, e.value)
    return { value: undefined }
  })
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('turn.complete', ($, e) => ({ text: e.answer }))

  return world
}

/** 繪製出的樹中所有字串（依序）。 */
export function stringsOf(node: RenderNode | RenderElement | null | undefined): string[] {
  if (node === null || node === undefined) {
    return []
  }
  if (typeof node === 'string') {
    return [node]
  }
  const own: string[] = []
  const props = (node as { props?: Record<string, unknown> }).props
  if (node.type === 'Button' && typeof props?.label === 'string') {
    own.push(props.label)
  }
  const children = (node as { children?: readonly RenderNode[] }).children ?? []
  return [...own, ...children.flatMap(child => stringsOf(child))]
}

/** 繪製出的樹合成一個字串。 */
export const textOf = (node: RenderNode | RenderElement | null | undefined): string => stringsOf(node).join('')
