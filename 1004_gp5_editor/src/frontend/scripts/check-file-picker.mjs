import assert from 'node:assert/strict'
import { pickFile } from '../src/filePicker.ts'

const options = []
const handles = ['score.gp5', 'bank.sf2', 'next.gp5'].map(name => ({ getFile: async () => new File(['test'], name) }))
let index = 0, fallbacks = 0
const host = { async showOpenFilePicker(option) { options.push(option); return [handles[index++]] } }
const fallback = () => fallbacks++
assert.equal((await pickFile('score', fallback, host)).name, 'score.gp5')
assert.equal((await pickFile('soundfont', fallback, host)).name, 'bank.sf2')
assert.equal((await pickFile('score', fallback, host)).name, 'next.gp5')
assert.notEqual(options[0].id, options[1].id)
assert.equal(options[2].id, options[0].id)
assert.equal(options[2].startIn, handles[0])
assert.equal(options[1].startIn, undefined)
assert.deepEqual(options[0].types[0].accept['application/octet-stream'], ['.gp3', '.gp4', '.gp5'])
assert.deepEqual(options[1].types[0].accept['application/octet-stream'], ['.sf2', '.sf3'])
assert.equal(await pickFile('score', fallback, {}), null)
assert.equal(fallbacks, 1)
assert.equal(await pickFile('score', fallback, { showOpenFilePicker() { throw new DOMException('cancel', 'AbortError') } }), null)
assert.equal(fallbacks, 1)
await assert.rejects(pickFile('score', fallback, { showOpenFilePicker() { throw new Error('picker error') } }), /picker error/)
console.log('Separate remembered file picker locations and fallback: passed')
