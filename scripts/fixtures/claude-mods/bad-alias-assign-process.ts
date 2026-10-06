// expect: alias
export const x = async ($: any) => {
  let p = $.process;
  p = $.process
  return p
}
