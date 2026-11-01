import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as alphaTab from '@coderline/alphatab'
import { readSoundFont, replaceSoundFont } from '../src/soundFont.ts'

class Event {
  listeners = new Set()
  on(listener) { this.listeners.add(listener); return () => this.listeners.delete(listener) }
  emit(value) { for (const listener of [...this.listeners]) listener(value) }
}
function fakeApi(score = null) {
  return { score, soundFontLoaded: new Event(), playerReady: new Event(),
    player: { soundFontLoadFailed: new Event() }, loadSoundFont: () => true }
}
const controller = new AbortController()
const data = new Uint8Array([1])
const api = fakeApi({})
let resolved = false
const loading = replaceSoundFont(api, data, controller.signal).then(() => { resolved = true })
api.playerReady.emit() // Readiness for the previous bank must not finish this load.
api.soundFontLoaded.emit()
await Promise.resolve()
assert.equal(resolved, false)
api.playerReady.emit()
await loading
assert.equal(resolved, true)
assert.equal(api.soundFontLoaded.listeners.size, 0)
assert.equal(api.player.soundFontLoadFailed.listeners.size, 0)

const noScore = fakeApi()
const noScoreLoading = replaceSoundFont(noScore, data, controller.signal)
noScore.soundFontLoaded.emit()
await noScoreLoading

const failed = fakeApi()
const failing = replaceSoundFont(failed, data, controller.signal)
failed.player.soundFontLoadFailed.emit(new Error('Invalid bank'))
await assert.rejects(failing, /Invalid bank/)
assert.equal(failed.soundFontLoaded.listeners.size, 0)
const rejected = fakeApi()
rejected.loadSoundFont = () => false
await assert.rejects(replaceSoundFont(rejected, data, controller.signal), /could not start/)
const aborted = new AbortController()
const cancelled = fakeApi()
const cancelLoading = replaceSoundFont(cancelled, data, aborted.signal)
aborted.abort()
await assert.rejects(cancelLoading, /cancelled/)
assert.equal(cancelled.soundFontLoaded.listeners.size, 0)
await assert.rejects(readSoundFont(new File(['not a font'], 'wrong.sf2')), /not a SoundFont/)
await assert.rejects(readSoundFont(new File(['test'], 'wrong.wav')), /sf2 or .sf3/)

// Decode real SF2 and SF3 banks through the installed alphaTab synthesizer.
const ready = new Event(), sampleRequest = new Event(), samplesPlayed = new Event()
let producedAudio = false
const output = { sampleRate: 44100, ready, sampleRequest, samplesPlayed,
  open() { ready.emit() }, play() {}, pause() {}, destroy() {}, resetSamples() {}, activate() {},
  addSamples(samples) { if (samples.some(value => Math.abs(value) > 1e-6)) producedAudio = true } }
const synth = new alphaTab.synth.AlphaSynth(output, 500)
const midi = new alphaTab.midi.MidiFile()
midi.addEvent(new alphaTab.midi.ProgramChangeEvent(0, 0, 0, 25))
midi.addEvent(new alphaTab.midi.NoteOnEvent(0, 0, 0, 64, 100))
midi.addEvent(new alphaTab.midi.NoteOffEvent(0, 960, 0, 64, 0))
synth.loadMidiFile(midi)
const realApi = { score: {}, player: synth, soundFontLoaded: synth.soundFontLoaded,
  playerReady: synth.readyForPlayback,
  loadSoundFont(bytes, append) { assert.equal(append, false); synth.loadSoundFont(bytes, append); return true } }
for (const extension of ['sf2', 'sf3']) {
  const file = new File([fs.readFileSync(new URL(`../public/soundfont/sonivox.${extension}`, import.meta.url))], `external.${extension}`)
  const bytes = await readSoundFont(file)
  await replaceSoundFont(realApi, bytes, controller.signal)
  assert.equal(synth.isReadyForPlayback, true)
  producedAudio = false
  synth.tickPosition = 0
  assert.equal(synth.play(), true)
  sampleRequest.emit()
  assert.equal(producedAudio, true, `${extension} must synthesize audible samples`)
  synth.stop()
}
// A decoder failure must be reported; a subsequent valid bank restores readiness.
await assert.rejects(replaceSoundFont(realApi, new Uint8Array([0]), controller.signal))
const defaultBytes = fs.readFileSync(new URL('../public/soundfont/sonivox.sf2', import.meta.url))
await replaceSoundFont(realApi, new Uint8Array(defaultBytes), controller.signal)
assert.equal(synth.isReadyForPlayback, true)
synth.destroy()
console.log('SoundFont selection, completion, failure, recovery, SF2/SF3 decoding: passed')
