// expect: forbidden-noun
export const x = async ($: any) => {
  await $.fs.remove("x")
}
