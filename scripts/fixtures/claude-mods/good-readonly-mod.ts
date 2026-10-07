// 合法 Mod 正對照：只讀、只開 pane、只填 prompt，不可被擋。
import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

const calls = atom({ plugin: 'cockpit', key: 'tasks' } as const, [])

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const { ui, store } = $
    await $.command.register({ name: 'cockpit', description: '開啟 Cockpit' })
    const dir = await $.fs.list('.spec')
    const raw = await $.fs.read('.spec/x/state.json')
    const ok = await $.fs.exists('.spec')
    void ui.open({ id: 'cockpit', title: 'Cockpit' })
    await store.get('hud')
    await $.prompt.read()
    await $.prompt.fill('/plan-next x')
    return next(e)
  })

  on('tool.call', async ($, e, next) => {
    const names = [e.tool].map(tool => String(tool))
    const pick = ({ tool, id }: { tool: string; id: string }) => `${tool}:${id}`
    await update($, calls, list => list.map(one => ({ ...one, names, pick })))
    return next(e)
  })

  on('ui.render', { component: 'Pane', requestId: 'cockpit' }, async $ => {
    const { Box, Text } = $.ui.resolve({} as never)
    return [Box, Text, await read($, calls), dir0, raw0]
  })
}
const dir0 = 0
const raw0 = 1
