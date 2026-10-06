// expect: alias
export const x = async ($: any) => {
  const { ui, tool: t } = $
  await t.check('Bash', {})
}
