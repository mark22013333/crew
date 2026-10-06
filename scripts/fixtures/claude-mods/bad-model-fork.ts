// expect: forbidden-call model/fork
export const x = async ($: any) => {
  await $.model.fork({})
}
