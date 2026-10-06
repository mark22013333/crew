// expect: forbidden-call fs/write
export const x = async ($: any) => {
  await $
    .fs
    ?.write('a', 'b')
}
