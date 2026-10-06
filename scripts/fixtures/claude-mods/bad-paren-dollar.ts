// expect: alias
export const x = async ($: any) => {
  const k = "tool"
  return ($)[k]
}
