// expect: alias
declare function helper(m: unknown): void
export const x = ($: any) => helper($.model)
