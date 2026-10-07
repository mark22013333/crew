// expect: forbidden-call model/classify
export const x = async ($: any) => {
  await $.model.classify({})
}
