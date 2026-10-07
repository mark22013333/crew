// expect: forbidden-call process/run
export const x = async (ctx: any) => { await ctx.process.run('ls') }
