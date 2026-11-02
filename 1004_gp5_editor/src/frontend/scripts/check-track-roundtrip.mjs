import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as alphaTab from '@coderline/alphatab'

const score = alphaTab.importer.ScoreLoader.loadScoreFromBytes(new Uint8Array(fs.readFileSync(process.argv[2])))
const expected = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'))
const info = score.tracks[0].playbackInfo
assert.equal(info.program, expected.instrument)
assert.equal(info.bank, expected.bank)
assert.equal(info.isSolo, expected.isSolo)
assert.equal(info.isMute, expected.isMute)

const midi = new alphaTab.midi.MidiFile()
const handler = new alphaTab.midi.AlphaSynthMidiFileHandler(midi)
new alphaTab.midi.MidiFileGenerator(score, new alphaTab.Settings(), handler).generate()
assert.ok(midi.tracks.flatMap(track => track.events).some(event =>
  event instanceof alphaTab.midi.ProgramChangeEvent && event.program === expected.instrument))
