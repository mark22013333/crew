// expect: forbidden-call process/spawn
export const x = async ($: any) => { await $.process.spawn('ls') }
