// expect: forbidden-call tool/register
export const x = async ($: any) => {
  await $.tool.register({})
}
