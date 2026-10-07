// expect: forbidden-noun
export const x = async ($: any) => {
  return $.env.get("HOME")
}
