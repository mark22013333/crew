// expect: dup-decl refresh
// 解構宣告也算宣告：{ refresh } 與 $-taking 的 refresh 同名
export async function refresh($: any) {
  return $.clock.now()
}

export const pick = (obj: { refresh: number }) => {
  const { refresh } = obj
  return refresh
}
