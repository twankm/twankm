import type { model } from '@coderline/alphatab'

export type EditableNote = {
  id: string; track: number; bar: number; voice: number; beat: number
  string: number; fret: number; maxFret: number; editable: boolean
}
export type EditingState = {
  revision: number; notes: EditableNote[]; voices: Record<string, number[][][]>
  canUndo: boolean; canRedo: boolean
}

// GP5 strings count from the highest string; alphaTab counts from the lowest.
// The server provides converted string numbers and skips zero-beat voices.
export function findEditableNote(note: model.Note, editing: EditingState | null): EditableNote | null {
  const beat = note.beat
  const bar = beat.voice.bar
  if (bar.staff.index !== 0 || note.isTieOrigin || note.isTieDestination) return null
  const matches = editing?.notes.filter(n =>
    n.track === bar.staff.track.index && n.bar === bar.index &&
    n.voice === beat.voice.index && n.beat === beat.index &&
    n.string === note.string && n.fret === note.fret)
  if (matches?.length !== 1 || !matches[0].editable) return null
  const sortNotes = (notes: number[][]) => [...notes].sort((a, b) => a[0] - b[0])
  const shape = beat.voice.beats.map(b => sortNotes(b.notes.map(n => [n.string, n.fret])))
  const expected = editing?.voices[`${bar.staff.track.index}:${bar.index}:${beat.voice.index}`]?.map(sortNotes)
  return JSON.stringify(shape) === JSON.stringify(expected) ? matches[0] : null
}
