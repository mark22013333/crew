// expect: alias
export const handler = async ({ fs }: any, e: unknown, next: (e: unknown) => unknown) => next(e)
