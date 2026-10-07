// expect: alias
export const x = async ($: any) => {
  const k = 'write'
  await $.fs[k]('x', 'y')
}
