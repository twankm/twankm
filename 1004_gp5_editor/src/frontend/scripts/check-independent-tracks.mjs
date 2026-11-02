import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as alphaTab from '@coderline/alphatab'

class Event {
  listeners = new Set()
  on(listener) { this.listeners.add(listener); return () => this.listeners.delete(listener) }
  emit(value) { for (const listener of [...this.listeners]) listener(value) }
}
const score = alphaTab.importer.ScoreLoader.loadScoreFromBytes(new Uint8Array(fs.readFileSync(process.argv[2])))
const [source, clone] = score.tracks.map(t => t.playbackInfo)
assert.ok(![source.primaryChannel, source.secondaryChannel].some(c => [clone.primaryChannel, clone.secondaryChannel].includes(c)))
const midi = new alphaTab.midi.MidiFile()
new alphaTab.midi.MidiFileGenerator(score, new alphaTab.Settings(), new alphaTab.midi.AlphaSynthMidiFileHandler(midi)).generate()
const ready = new Event(), sampleRequest = new Event(), samplesPlayed = new Event()
let audible = false
const output = { sampleRate: 44100, ready, sampleRequest, samplesPlayed,
  open() { ready.emit() }, play() {}, pause() {}, destroy() {}, resetSamples() {}, activate() {},
  addSamples(samples) { if (samples.some(value => Math.abs(value) > 1e-6)) audible = true } }
const synth = new alphaTab.synth.AlphaSynth(output, 500)
synth.loadMidiFile(midi)
synth.loadSoundFont(new Uint8Array(fs.readFileSync(new URL('../public/soundfont/sonivox.sf2', import.meta.url))), false)
assert.equal(synth.isReadyForPlayback, true)
for (const [sourceMuted, cloneMuted, expectedAudio] of [[false, true, true], [true, false, true], [true, true, false]]) {
  synth.stop()
  synth.loadMidiFile(midi)
  for (const channel of [source.primaryChannel, source.secondaryChannel]) synth.setChannelMute(channel, sourceMuted)
  for (const channel of [clone.primaryChannel, clone.secondaryChannel]) synth.setChannelMute(channel, cloneMuted)
  audible = false
  assert.equal(synth.play(), true)
  sampleRequest.emit()
  assert.equal(audible, expectedAudio, `source mute=${sourceMuted}, clone mute=${cloneMuted}`)
}
synth.destroy()
console.log('Independent duplicate channels and actual synth mute: passed')
