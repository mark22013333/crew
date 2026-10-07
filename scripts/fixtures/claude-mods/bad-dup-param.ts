// expect: dup-decl render
// $-taking 的 function 宣告，與另一個函式的參數同名
function render($: any) {
  return $.ui.resolve({} as never)
}

export function wrap(render: () => void) {
  return render
}
