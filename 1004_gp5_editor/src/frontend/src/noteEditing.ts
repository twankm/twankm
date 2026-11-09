import type { model } from '@coderline/alphatab'

export type EditableNote = {
  id: string; track: number; bar: number; voice: number; beat: number
  string: number; fret: number; maxFret: number; editable: boolean
  kind?: 'note' | 'grace'; beatId?: string
}
export type Rhythm = { value: number; dotted: boolean; tuplet: number }
export type EditableBeat = { id: string; track: number; bar: number; voice: number; beat: number; stringCount: number; maxFret: number; canAdd: boolean; rhythm: Rhythm; remainingTicks: number }
export type EditingState = {
  revision: number; notes: EditableNote[]; voices: Record<string, number[][][]>
  canUndo: boolean; canRedo: boolean
  beats: EditableBeat[]
}

export function findEditableBeat(beat: model.Beat, editing: EditingState | null): EditableBeat | null {
  const bar = beat.voice.bar
  if (bar.staff.index !== 0 || beat.graceType !== 0) return null
  const main = beat.voice.beats.filter(b => b.graceType === 0)
  const sort = (notes: number[][]) => [...notes].sort((a, b) => a[0] - b[0])
  const shape = main.map(b => sort(b.notes.map(n => [n.string, n.fret])))
  const expected = editing?.voices[`${bar.staff.track.index}:${bar.index}:${beat.voice.index}`]?.map(sort)
  if (JSON.stringify(shape) !== JSON.stringify(expected)) return null
  return editing?.beats?.find(b => b.track === bar.staff.track.index && b.bar === bar.index && b.voice === beat.voice.index && b.beat === main.indexOf(beat)) ?? null
}

// GP5 strings count from the highest string; alphaTab counts from the lowest.
// The server provides converted string numbers and skips zero-beat voices.
export function findEditableNote(note: model.Note, editing: EditingState | null): EditableNote | null {
  const beat = note.beat
  const bar = beat.voice.bar
  if (bar.staff.index !== 0) return null
  const main = beat.voice.beats.filter(b => b.graceType === 0)
  const anchor = beat.graceType === 0 ? beat : beat.voice.beats.slice(beat.index + 1).find(b => b.graceType === 0)
  if (!anchor) return null
  const matches = editing?.notes.filter(n =>
    n.track === bar.staff.track.index && n.bar === bar.index &&
    n.voice === beat.voice.index && n.beat === main.indexOf(anchor) &&
    (n.kind ?? 'note') === (beat.graceType === 0 ? 'note' : 'grace') &&
    n.string === note.string && n.fret === note.fret)
  if (matches?.length !== 1 || !matches[0].editable) return null
  const sortNotes = (notes: number[][]) => [...notes].sort((a, b) => a[0] - b[0])
  const shape = main.map(b => sortNotes(b.notes.map(n => [n.string, n.fret])))
  const expected = editing?.voices[`${bar.staff.track.index}:${bar.index}:${beat.voice.index}`]?.map(sortNotes)
  return JSON.stringify(shape) === JSON.stringify(expected) ? matches[0] : null
}
