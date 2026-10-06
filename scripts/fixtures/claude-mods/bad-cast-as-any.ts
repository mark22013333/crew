// expect: alias
export const x = async ($: unknown) => {
  const k = "fs"
  await ($ as any)[k].write("x", "y")
}
