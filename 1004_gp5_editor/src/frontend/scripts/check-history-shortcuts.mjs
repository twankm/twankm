import assert from 'node:assert/strict'
import { historyShortcut } from '../src/historyShortcut.ts'

const event = { ctrlKey: true, shiftKey: false, altKey: false, metaKey: false,
  code: 'KeyZ', key: 'z', isComposing: false }
assert.equal(historyShortcut(event), 'undo')
assert.equal(historyShortcut({ ...event, shiftKey: true }), 'redo')
assert.equal(historyShortcut({ ...event, key: '\u314b' }), 'undo')
for (const change of [{ ctrlKey: false }, { altKey: true }, { metaKey: true },
  { isComposing: true }, { code: 'KeyY', key: 'y' }]) {
  assert.equal(historyShortcut({ ...event, ...change }), null)
}
console.log('History shortcuts: passed')
