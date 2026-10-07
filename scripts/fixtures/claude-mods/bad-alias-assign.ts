// expect: alias
export const x = async ($: any) => {
  const f = $.fs
  await f.write('x', 'y')
}
