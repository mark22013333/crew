// expect: alias
export const x = async ($: unknown) => {
  const k = "process"
  return (<any>$)[k]
}
