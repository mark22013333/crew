// expect: alias
export const x = async ($: any) => {
  const { fs } = $
  await fs.write('x', 'y')
}
