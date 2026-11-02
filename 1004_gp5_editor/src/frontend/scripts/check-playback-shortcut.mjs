import assert from 'node:assert/strict'
import { isPlaybackShortcut } from '../src/playbackShortcut.ts'

const space = { code: 'Space', key: ' ', ctrlKey: false, shiftKey: false,
  altKey: false, metaKey: false, isComposing: false }
assert.equal(isPlaybackShortcut(space), true)
assert.equal(isPlaybackShortcut({ ...space, code: '', key: ' ' }), true)
for (const change of [{ ctrlKey: true }, { shiftKey: true }, { altKey: true },
  { metaKey: true }, { isComposing: true }, { code: 'KeyZ', key: 'z' }]) {
  assert.equal(isPlaybackShortcut({ ...space, ...change }), false)
}
console.log('Space playback shortcut: passed')
