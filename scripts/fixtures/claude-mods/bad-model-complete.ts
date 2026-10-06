// expect: forbidden-call model/complete
export const x = async ($: any) => { await $.model.complete({ prompt: 'x' }) }
