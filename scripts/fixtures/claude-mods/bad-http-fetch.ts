// expect: forbidden-call http/fetch
export const x = async ($: any) => {
  await $.http.fetch("https://example.com")
}
