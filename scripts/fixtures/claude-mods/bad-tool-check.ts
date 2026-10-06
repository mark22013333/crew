// expect: forbidden-call tool/check
export const x = async ($: any) => { await $.tool.check('Bash', {}) }
