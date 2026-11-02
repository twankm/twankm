import assert from 'node:assert/strict'
import fs from 'node:fs'
import { soundFontPresets, trackPresets } from '../src/soundFontPresets.ts'
import { applyTrackMix } from '../src/trackMix.ts'

for (const extension of ['sf2', 'sf3']) {
  const bytes = new Uint8Array(fs.readFileSync(new URL(`../public/soundfont/sonivox.${extension}`, import.meta.url)))
  const presets = soundFontPresets(bytes)
  assert.ok(presets.length > 1)
  assert.ok(presets.some(p => p.bank === 0 && p.program === 25 && p.name.length > 0))
  assert.ok(trackPresets(presets, false).every(p => p.bank < 128))
  assert.ok(trackPresets(presets, true).every(p => p.bank >= 128 && p.bank <= 255))
  assert.ok(presets.every(p => p.name !== 'EOP'))
  assert.throws(() => soundFontPresets(bytes.subarray(0, 30)), /Truncated/)
}
assert.throws(() => soundFontPresets(new Uint8Array(12)), /Invalid/)
assert.deepEqual(trackPresets([{ name: 'Unsupported bank', bank: 256, program: 0 }], false), [])

const score = { tracks: [0, 1].map(index => ({ index, playbackInfo: {} })) }
const solo = new Set(), mute = new Set()
const api = { score,
  changeTrackSolo(tracks, enabled) { for (const t of tracks) enabled ? solo.add(t.index) : solo.delete(t.index) },
  changeTrackMute(tracks, enabled) { for (const t of tracks) enabled ? mute.add(t.index) : mute.delete(t.index) },
  renderTracks() { throw new Error('Mixer must not change track selection') } }
const settings = [{ index: 0, isSolo: true, isMute: false }, { index: 1, isSolo: false, isMute: true }]
applyTrackMix(api, settings)
assert.deepEqual([...solo], [0])
assert.deepEqual([...mute], [1])
assert.equal(score.tracks[0].playbackInfo.isSolo, true)
// Simulate reload/soundfont replacement; reapplying must restore both switches.
solo.clear(); mute.clear()
applyTrackMix(api, settings)
assert.deepEqual([...solo], [0])
assert.deepEqual([...mute], [1])
applyTrackMix(api, settings.map(t => ({ ...t, isSolo: false, isMute: false })))
assert.equal(solo.size, 0)
assert.equal(mute.size, 0)
console.log('SF2/SF3 preset lists, track mixing and restoration: passed')
