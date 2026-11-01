import assert from 'node:assert/strict'
import { barTimeAt, barSweep, createConstantBarCursor } from '../src/constantBarCursor.ts'

const bar = { start: 100, end: 3940, tempoChanges: [{ tick: 100, tempo: 120 }] }
assert.equal(barTimeAt(bar, bar.end), 2000)
const frames = [100, 1060, 2020, 2980].map(tick => barSweep(bar, tick, 50, 450, 1))
assert.deepEqual(frames.map(f => f.x), [50, 150, 250, 350])
assert.deepEqual(frames.map(f => (f.endX - f.x) / f.duration), [0.2, 0.2, 0.2, 0.2])
assert.equal(barSweep(bar, 2020, 50, 450, 2).duration, 500)
assert.equal(barSweep(bar, -1, 50, 450, 1).x, 50)
assert.equal(barSweep(bar, 9999, 50, 450, 1).x, 450)
const changingTempo = { ...bar, tempoChanges: [...bar.tempoChanges, { tick: 2020, tempo: 60 }] }
assert.equal(barTimeAt(changingTempo, bar.end), 3000)
for (const tick of [100, 1060, 2020, 2500]) {
  const f = barSweep(changingTempo, tick, 0, 300, 1)
  assert.ok(Math.abs((f.endX - f.x) / f.duration - 0.1) < 1e-9)
}

// Same written measure repeated: use the current occurrence's playback ticks.
const api = { tickPosition: 4900, playbackSpeed: 1, tickCache: { masterBars: [
  { ...bar, masterBar: { index: 0 } },
  { start: 3940, end: 7780, tempoChanges: [{ tick: 3940, tempo: 120 }], masterBar: { index: 0 } }
] } }
const bounds = { barBounds: { masterBarBounds: { index: 0, visualBounds: { x: 0, y: 20, w: 450, h: 100 },
  realBounds: { x: 0, w: 450 }, bars: [{ beats: [{ onNotesX: 50 }] }] } } }
const calls = []
const cursor = { transitionToX: (...args) => calls.push(['move', ...args]), setBounds: (...args) => calls.push(['bounds', ...args]) }
const handler = createConstantBarCursor(api)
handler.transitionBeatCursor(cursor, bounds, 999)
assert.deepEqual(calls[0], ['move', 0, 150])
assert.deepEqual(calls.at(-1), ['move', 1500, 450])
api.tickPosition = 3940
handler.placeBeatCursor(cursor, bounds, 999)
assert.deepEqual(calls.at(-2), ['move', 0, 50])
console.log('Constant bar cursor: passed')
