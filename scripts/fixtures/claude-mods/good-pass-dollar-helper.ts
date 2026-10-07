// 正對照：把 $ 當參數傳給入口檔內 helper、hook 簽章、解構 ui.resolve 結果，都不可被擋。
import { read, update } from "claude-code"
const portsOf = ($: any) => ({ list: (p: string) => $.fs.list(p) })
const checkVersion = async ($: any) => (await read($, 1 as never)) === true
export const register = (on: any) => {
  on("session.start", async ($: any, e: any, next: any) => {
    await update($, 1 as never, () => 1)
    void portsOf($); void checkVersion($)
    // 註解裡提到 $.fs.* 之類的說明文字不算呼叫
    const { Box, Text } = $.ui.resolve(e)
    return [Box, Text, next(e)]
  })
  on("turn.complete", async ($) => {
    await $.prompt.fill("x")
  })
}
