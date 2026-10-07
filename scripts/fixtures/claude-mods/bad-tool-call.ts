// expect: forbidden-call tool/call
export const x = async ($: any) => { await $.tool.call('Bash', {}) }
