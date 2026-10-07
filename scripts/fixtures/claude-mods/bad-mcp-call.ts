// expect: forbidden-call mcp/call
export const x = async ($: any) => {
  await $.mcp.call({})
}
