// expect: forbidden-call process/run
export const x = async ($: any) => { await $.process.run('ls') }
