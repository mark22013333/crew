// expect: alias
export const x = async ($: any) => {
  const { fs, ui } = $
  await ui.open({})
}
