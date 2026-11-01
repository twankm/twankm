import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as alphaTab from '@coderline/alphatab'
import { findEditableNote } from '../src/noteEditing.ts'

const score = alphaTab.importer.ScoreLoader.loadScoreFromBytes(new Uint8Array(fs.readFileSync(process.argv[2])))
const editing = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'))
const mapped = []
for (const track of score.tracks) for (const staff of track.staves)
  for (const bar of staff.bars) for (const voice of bar.voices)
    for (const beat of voice.beats) for (const note of beat.notes) {
      const match = findEditableNote(note, editing)
      if (match) mapped.push(match.id)
    }
assert.deepEqual(mapped.sort(), editing.notes.filter(n => n.editable).map(n => n.id).sort())
// Stale and ambiguous DTOs must never produce an editable target.
const first = score.tracks[0].staves[0].bars[0].voices[0].beats[0].notes[0]
if (first) {
  assert.equal(findEditableNote(first, { revision: 0, notes: [], voices: {} }), null)
  assert.equal(findEditableNote(first, { ...editing, notes: [...editing.notes, ...editing.notes] }), null)
}
