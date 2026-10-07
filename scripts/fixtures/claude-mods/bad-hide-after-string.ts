// expect: forbidden-noun
export const x = async ($: any) => {
  const u = "//"; await $.http.get(u)
}
