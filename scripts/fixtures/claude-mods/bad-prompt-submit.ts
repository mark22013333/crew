// expect: forbidden-call prompt/submit
export const x = async ($: any) => { await $.prompt.submit('hi', { asUser: true }) }
