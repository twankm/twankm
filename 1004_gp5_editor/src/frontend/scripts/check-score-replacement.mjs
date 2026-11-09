import assert from 'node:assert/strict'
import fs from 'node:fs'
import { importer, Settings } from '@coderline/alphatab'
import { loadScoreSafely } from '../src/scoreLoading.ts'

const before = new Uint8Array(fs.readFileSync(process.argv[2]))
const after = new Uint8Array(fs.readFileSync(process.argv[3]))
const settings = new Settings()
settings.core.useWorkers = true
let staleResultPending = true
const events = []
const api = {
  settings,
  score: importer.ScoreLoader.loadScoreFromBytes(before),
  updateSettings() {
    events.push(settings.core.useWorkers ? 'new-worker' : 'terminate-worker')
    if (!settings.core.useWorkers) staleResultPending = false
  },
  load(score, tracks) {
    // Emulate the old worker's delayed bounds result referencing the last track.
    const oldIndex = this.score.tracks.length - 1
    this.score = score
    if (staleResultPending) void score.tracks[oldIndex].staves
    assert.ok(score.tracks[tracks[0]]?.staves.length)
    events.push('load')
    return true
  }
}
const oldLast = api.score.tracks.length - 1
const selected = loadScoreSafely(api, after, oldLast)
assert.equal(selected, api.score.tracks.length - 1)
assert.deepEqual(events, ['terminate-worker', 'new-worker', 'load'])
assert.equal(settings.core.useWorkers, true)
// Undo restores the larger score; redo reduces it again without stale indexes.
loadScoreSafely(api, before, selected)
loadScoreSafely(api, after, oldLast)
assert.equal(api.score.tracks.length, oldLast)
// Reject corrupt data before disrupting the current renderer/score.
const previous = api.score
const count = events.length
assert.throws(() => loadScoreSafely(api, new Uint8Array([0]), 0))
assert.equal(api.score, previous)
assert.equal(events.length, count)
