// expect: alias
export const x = async ($: any) => {
  await $['fs']['write']('x', 'y')
}
