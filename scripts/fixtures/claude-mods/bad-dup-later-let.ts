// expect: dup-decl load
// 後面才以 let 宣告同名（行號在函式之後）；箭頭函式以 EngineInterface 型別標註接收 $
const load = async (api: EngineInterface) => api.session.id

export const main = () => {
  let load = 0
  return load
}
