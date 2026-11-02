import assert from 'node:assert/strict'
import { measureShortcut } from '../src/measureShortcut.ts'
const copy = { ctrlKey: true, metaKey: false, altKey: false, shiftKey: false,
  isComposing: false, code: 'KeyC', key: 'c' }
assert.equal(measureShortcut(copy), 'copy')
assert.equal(measureShortcut({ ...copy, code: 'KeyV', key: 'v' }), 'paste')
assert.equal(measureShortcut({ ...copy, key: '\u314a' }), 'copy')
for (const change of [{ ctrlKey: false }, { metaKey: true }, { altKey: true },
  { shiftKey: true }, { isComposing: true }, { code: 'KeyA', key: 'a' }]) {
  assert.equal(measureShortcut({ ...copy, ...change }), null)
}
console.log('Measure copy/paste shortcuts: passed')
