// expect: forbidden-call prompt/edit
export const x = async ($: any) => {
  await $.prompt.edit("x")
}
