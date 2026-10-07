// expect: alias
export const x = async ($: unknown) => {
  await Reflect.get($ as object, "process").run("ls")
}
