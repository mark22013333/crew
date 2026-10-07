// 正對照：看起來像同名、其實都不是宣告，不可被擋。
const isSupported = async ($: any): Promise<boolean> => ($ ? true : false)
const obj = { isSupported: 1 }

type Runtime = { isSupported?: boolean }

export async function checkVersion($: any, current?: Runtime) {
  const supported = (current?.isSupported ?? false) && obj.isSupported > 0
  const text = 'const isSupported = 1' + `function isSupported($) ${supported}`
  // const isSupported = 2 （註解不算）
  const raw = await $.fs.read('.spec/x/state.json')
  return { isSupported: supported, raw, text, ok: await isSupported($) }
}

// 非 $-taking 的同名重複宣告不在 R6 範圍（只管接收 $ 的函式）
export const a = () => { const n = 1; return n }
export const b = () => { const n = 2; return n }
