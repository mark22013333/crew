// expect: forbidden-noun
export const x = async ($: any) => {
  const { ui, telemetry } = $
  return [ui, telemetry]
}
