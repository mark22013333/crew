// CREW Cockpit render（Batch 1/2 的最小 stub；Batch 3 起由 Pane/HUD 實作取代）。
// 規則（§3 D-3）：純函式，只把 snapshot 轉成 element tree；不做 I/O、不碰 $。
// 呼叫端（crew-cockpit.ts 的 ui.render hook）負責 $.ui.resolve(e) 與讀 $.state，再把結果傳進來。

import type { Elements, RenderElement } from 'claude-code'

import { type CockpitSnapshot, TEXT } from './model'

/** render 需要的元素（terminal 與 desktop 都有的 baseline，§17.1）。 */
export type CockpitKit = Pick<Elements['terminal'], 'Box' | 'Text'>

/** Pane 最小內容：無任務時顯示 §16 文案；有任務時只顯示筆數（完整版面留給 Batch 3）。 */
export function paneStubView(kit: CockpitKit, snapshot: CockpitSnapshot | null): RenderElement {
  const { Box, Text } = kit
  const isEmpty =
    snapshot === null ||
    snapshot.repoRoot === null ||
    (snapshot.tasks.length === 0 && snapshot.invalidTasks.length === 0)

  if (isEmpty) {
    return h(Box, { flexDirection: 'column' }, h(Text, {}, TEXT.noTasks), h(Text, { dimColor: true }, TEXT.noTasksHint)) as RenderElement
  }

  return h(
    Box,
    { flexDirection: 'column' },
    h(Text, { bold: true }, TEXT.paneTitle),
    h(Text, { dimColor: true }, `${snapshot.tasks.length} 個任務、${snapshot.invalidTasks.length} 筆無法解析（介面建置中）`),
  ) as RenderElement
}
