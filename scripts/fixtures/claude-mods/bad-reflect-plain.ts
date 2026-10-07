// expect: alias
export const x = async ($: object) => {
  const p = Reflect.get($, "process")
  return p
}
