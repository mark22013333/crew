// expect: forbidden-noun
export const x = async ($: any) => {
  await $.agent.list()
}
