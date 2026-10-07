// expect: dup-decl isSupported
// 模組層 $-taking 函式 + 函式內區域 const 同名：2.1.289 會拒載（crew-cockpit 的真實事故）
const isSupported = async ($: any): Promise<boolean> => ($ ? true : false)

export async function checkVersion($: any, v: string) {
  const isSupported = v.length > 0
  return isSupported
}
export const use = (x: any) => isSupported(x)
