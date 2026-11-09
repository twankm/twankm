import { useEffect, useRef, useState } from 'react'
import * as alphaTab from '@coderline/alphatab'
import { findEditableNote, findEditableBeat, type EditableBeat, type EditableNote, type EditingState, type Rhythm } from './noteEditing'
import { historyShortcut } from './historyShortcut'
import { isPlaybackShortcut } from './playbackShortcut'
import { createConstantBarCursor } from './constantBarCursor'
import { DEFAULT_SOUND_FONT, DEFAULT_SOUND_FONT_NAME, readSoundFont, replaceSoundFont } from './soundFont'
import { soundFontPresets as parseSoundFontPresets, trackPresets, type SoundFontPreset } from './soundFontPresets'
import { applyTrackMix } from './trackMix'
import { pickFile } from './filePicker'
import { measureShortcut } from './measureShortcut'
import { extendMeasureSelection, measureCount, type MeasureSelection } from './measureSelection'
import { apiError } from './apiError'
import { loadScoreSafely } from './scoreLoading'

const API = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

type Track = { index: number; name: string; measureCount: number; instrument: number; bank: number; isPercussionTrack: boolean; tuning: number[]; isSolo: boolean; isMute: boolean; sharedTracks: number[] }
type Song = { sessionId: string; title: string; artist: string; tempo: number; trackCount: number; tracks: Track[] }

export default function App() {
  const scoreRef = useRef<HTMLDivElement>(null)
  const controlsRef = useRef<HTMLDivElement>(null)
  const scoreCanvasRef = useRef<HTMLDivElement>(null)
  const fretInputRef = useRef<HTMLInputElement>(null)
  const scoreFileRef = useRef<HTMLInputElement>(null)
  const soundFontFileRef = useRef<HTMLInputElement>(null)
  const apiRef = useRef<any>(null)
  const [song, setSong] = useState<Song | null>(null)
  const songRef = useRef<Song | null>(null)
  const [selectedTrack, setSelectedTrack] = useState(0)
  const [status, setStatus] = useState('Open a Guitar Pro file to begin.')
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState<EditingState | null>(null)
  const [selectedNote, setSelectedNote] = useState<EditableNote | null>(null)
  const [selectedBeat, setSelectedBeat] = useState<EditableBeat | null>(null)
  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({})
  const [rhythmDraft, setRhythmDraft] = useState<Rhythm | null>(null)
  const [appendBeat, setAppendBeat] = useState(false)
  useEffect(() => { setAppendBeat(false) }, [selectedBeat?.id])
  useEffect(() => { setRhythmDraft(selectedBeat?.rhythm ?? null) }, [selectedBeat?.id])
  const [notePosition, setNotePosition] = useState<{ x: number; y: number; width: number; height: number; editorX: number } | null>(null)
  const [fret, setFret] = useState('0')
  const [playing, setPlaying] = useState(false)
  const [playbackSpeed, setPlaybackSpeed] = useState(1)
  const [speedInput, setSpeedInput] = useState('1.00')
  const playbackSpeedRef = useRef(1)
  const [synced, setSynced] = useState(false)
  const editingRef = useRef<EditingState | null>(null)
  const pendingLoad = useRef<{ resolve: () => void; reject: (error: Error) => void } | null>(null)
  const historyPending = useRef(false)
  const [soundFontName, setSoundFontName] = useState(DEFAULT_SOUND_FONT_NAME)
  const [soundFontMessage, setSoundFontMessage] = useState('Loading default SoundFont...')
  const [soundFontSettled, setSoundFontSettled] = useState(false)
  const [soundFontUsable, setSoundFontUsable] = useState(false)
  const soundFontPending = useRef(false)
  const activeSoundFont = useRef<File | null>(null)
  const soundFontAbort = useRef<AbortController | null>(null)
  const [presets, setPresets] = useState<SoundFontPreset[]>([])
  const [editMode, setEditMode] = useState(false)
  const [selectedMeasure, setSelectedMeasure] = useState<MeasureSelection | null>(null)
  const [measurePositions, setMeasurePositions] = useState<{ bar: number; x: number; y: number; width: number; height: number }[]>([])
  const [clipboard, setClipboard] = useState<{ clipboardId: string; track: number; bar: number; count: number; excludedControllers?: number } | null>(null)
  const selectedMeasureRef = useRef<typeof selectedMeasure>(null)
  const interactionRef = useRef({ editMode, busy, playing, synced })
  interactionRef.current = { editMode, busy, playing, synced }
  const clipboardPending = useRef(false)
  const pickerPending = useRef(false)
  const lastNoteClick = useRef<{ id: number; time: number } | null>(null)
  const selectionShift = useRef(false)

  useEffect(() => {
    const down = (event: KeyboardEvent) => { if (event.key === 'Shift') selectionShift.current = true }
    const up = (event: KeyboardEvent) => { if (event.key === 'Shift') selectionShift.current = false }
    const blur = () => { selectionShift.current = false }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    window.addEventListener('blur', blur)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
      window.removeEventListener('blur', blur)
    }
  }, [])

  function selectMeasure(selection: typeof selectedMeasure) {
    selectedMeasureRef.current = selection
    setSelectedMeasure(selection)
    setSelectedNote(null)
    setNoteDrafts({})
    updateMeasurePosition()
  }

  function updateMeasurePosition() {
    const selected = selectedMeasureRef.current
    const api = apiRef.current as alphaTab.AlphaTabApi | null
    const surface = (api?.canvasElement as unknown as { element?: HTMLElement })?.element
    const wrapper = scoreCanvasRef.current
    if (!selected || !surface || !wrapper) { setMeasurePositions([]); return }
    const surfaceRect = surface.getBoundingClientRect(), wrapperRect = wrapper.getBoundingClientRect()
    const positions = []
    for (let bar = selected.bar; bar <= selected.endBar; bar++) {
      const bounds = api?.boundsLookup?.findMasterBarByIndex(bar)?.visualBounds
      if (bounds) positions.push({ bar, x: surfaceRect.left - wrapperRect.left + bounds.x,
        y: surfaceRect.top - wrapperRect.top + bounds.y, width: bounds.w, height: bounds.h })
    }
    setMeasurePositions(positions)
  }

  function updateSong(value: Song) {
    songRef.current = value
    setSong(value)
  }

  useEffect(() => {
    const controller = new AbortController()
    void fetch(DEFAULT_SOUND_FONT, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error('Could not read the default instrument list.')
      const result = parseSoundFontPresets(new Uint8Array(await response.arrayBuffer()))
      if (!controller.signal.aborted && !activeSoundFont.current && !soundFontPending.current) setPresets(result)
    }).catch(error => {
      if (!controller.signal.aborted && !activeSoundFont.current && !soundFontPending.current) setSoundFontMessage(String(error))
    })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target
      // Text/number inputs retain their native undo for the uncommitted value.
      if (target instanceof HTMLElement && (target.isContentEditable || target.closest('input, textarea, select'))) return
      const measureAction = measureShortcut(event)
      if (measureAction && editMode && selectedMeasure) {
        event.preventDefault()
        if (!event.repeat) void measureClipboard(measureAction)
        return
      }
      if (isPlaybackShortcut(event)) {
        // Space on a focused button must retain the button's native action.
        if (target instanceof HTMLElement && target.closest('button, a, [role="button"]')) return
        event.preventDefault()
        if (!event.repeat) togglePlayback()
        return
      }
      const direction = historyShortcut(event)
      if (!direction || !editMode) return
      event.preventDefault()
      if (!event.repeat) void changeHistory(direction)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [song, editing, busy, playing, synced, selectedTrack, soundFontUsable, editMode, selectedMeasure, clipboard])

  useEffect(() => {
    const controls = controlsRef.current
    if (!controls) return
    const update = () => {
      const height = controls.getBoundingClientRect().height
      document.documentElement.style.setProperty('--controls-height', `${height}px`)
      // Leave the current system visible below the sticky controls during auto-scroll.
      if (apiRef.current) apiRef.current.settings.player.scrollOffsetY = -height - 12
    }
    const observer = new ResizeObserver(update)
    observer.observe(controls)
    update()
    return () => {
      observer.disconnect()
      document.documentElement.style.removeProperty('--controls-height')
    }
  }, [])

  useEffect(() => {
    if (!selectedNote || busy || playing || !synced) return
    const frame = requestAnimationFrame(() => {
      fretInputRef.current?.focus({ preventScroll: true })
      fretInputRef.current?.select()
    })
    return () => cancelAnimationFrame(frame)
  }, [selectedNote, busy, playing, synced])

  function updateEditing(value: EditingState) {
    editingRef.current = value
    setEditing(value)
    setSelectedNote(null)
    setSelectedBeat(null)
  }

  async function loadScore(bytes: Uint8Array, track = 0) {
    setSynced(false)
    await new Promise<void>((resolve, reject) => {
      const timeout = window.setTimeout(() => {
        pendingLoad.current = null
        reject(new Error('Score loading timed out. Reload the server score to retry.'))
      }, 30000)
      pendingLoad.current = {
        resolve: () => { window.clearTimeout(timeout); resolve() },
        reject: error => { window.clearTimeout(timeout); reject(error) }
      }
      try {
        if (!apiRef.current) throw new Error('Player is not initialized.')
        const selected = loadScoreSafely(apiRef.current, bytes, track)
        setSelectedTrack(selected)
      } catch (error) {
        pendingLoad.current?.reject(error instanceof Error ? error : new Error(String(error)))
        pendingLoad.current = null
      }
    })
    if (songRef.current && apiRef.current) applyTrackMix(apiRef.current, songRef.current.tracks)
    if (apiRef.current) apiRef.current.playbackSpeed = playbackSpeedRef.current
    setSynced(true)
  }

  async function reloadSession(sessionId: string, track: number) {
    const response = await fetch(`${API}/api/sessions/${sessionId}/download?format=gp5&revision=${editingRef.current?.revision}`)
    if (!response.ok) throw new Error(await response.text())
    await loadScore(new Uint8Array(await response.arrayBuffer()), track)
  }

  useEffect(() => {
  if (!scoreRef.current) return

  
  const api = new alphaTab.AlphaTabApi(scoreRef.current, {
    core: {
      fontDirectory: '/font/',
      includeNoteBounds: true
    },
    display: {
      layoutMode: alphaTab.LayoutMode.Page,
      staveProfile: alphaTab.StaveProfile.Tab
    },
    notation: { rhythmMode: alphaTab.TabRhythmMode.ShowWithBars },
    player: {
      enablePlayer: true,
      playerMode: 'EnabledSynthesizer',
      soundFont: DEFAULT_SOUND_FONT,
      scrollElement: 'html,body',

      // 재생 위치 표시
      enableCursor: true,
      enableAnimatedBeatCursor: true,
      enableElementHighlighting: true
    }
  } as any)


  apiRef.current = api
  api.customCursorHandler = createConstantBarCursor(api)
  api.playerReady.on(() => {
    api.playbackSpeed = playbackSpeedRef.current
    if (songRef.current) applyTrackMix(api, songRef.current.tracks)
    setStatus('Player ready.')
  })
  const removeSoundFontLoaded = api.soundFontLoaded.on(() => {
    if (soundFontPending.current) return
    setSoundFontSettled(true)
    setSoundFontUsable(true)
    setSoundFontMessage('SoundFont ready.')
  })
  const removeSoundFontFailure = api.player?.soundFontLoadFailed.on((error: unknown) => {
    if (soundFontPending.current) return
    setSoundFontSettled(true)
    setSoundFontUsable(false)
    setSoundFontMessage(`SoundFont error: ${String(error)}. Select a file or retry the default.`)
  })
  api.playerStateChanged.on((e: any) => setPlaying(e.state === alphaTab.synth.PlayerState.Playing))
  api.error.on((e: unknown) => {
    // SoundFont failures have their own recovery and do not invalidate the score.
    if (soundFontPending.current) return
    setSynced(false)
    setStatus(`Score error: ${String(e)}`)
    pendingLoad.current?.reject(new Error(String(e)))
    pendingLoad.current = null
  })
  api.postRenderFinished.on(() => {
    updateMeasurePosition()
    pendingLoad.current?.resolve()
    pendingLoad.current = null
  })
  api.renderStarted.on(() => { setSelectedNote(null); setSelectedBeat(null); setNoteDrafts({}); setMeasurePositions([]) })
  api.beatMouseDown.on(beat => {
    const state = interactionRef.current
    if (!state.editMode || state.busy || state.playing || !state.synced) return
    const bar = beat.voice.bar
    if (selectionShift.current) lastNoteClick.current = null
    selectMeasure(extendMeasureSelection(selectedMeasureRef.current, bar.staff.track.index, bar.index, selectionShift.current))
    setSelectedNote(null)
    setSelectedBeat(selectionShift.current ? null : findEditableBeat(beat, editingRef.current))
    const bounds = api.boundsLookup?.findBeat(beat)?.realBounds
    const surface = (api.canvasElement as unknown as { element: HTMLElement }).element
    const wrapper = scoreCanvasRef.current
    if (bounds && surface && wrapper) {
      const a = surface.getBoundingClientRect(), b = wrapper.getBoundingClientRect()
      const x = a.left - b.left + bounds.x, y = a.top - b.top + bounds.y
      setNotePosition({ x, y, width: bounds.w, height: bounds.h, editorX: Math.max(0, Math.min(x, wrapper.clientWidth - 300)) })
    }
  })
  api.noteMouseDown.on((note: any) => {
    const state = interactionRef.current
    if (!state.editMode || state.busy || state.playing || !state.synced || selectionShift.current) return
    const now = performance.now()
    const previous = lastNoteClick.current
    lastNoteClick.current = { id: note.id, time: now }
    // Single click selects a measure for Ctrl+C/V; double click edits a fret.
    if (!previous || previous.id !== note.id || now - previous.time > 450) return
    const match = findEditableNote(note, editingRef.current)
    if (!match) {
      setSelectedNote(null)
      setStatus('This note could not be matched safely to the GP5 data.')
      return
    }
    const bounds = api.boundsLookup?.findBeat(note.beat)?.notes?.find(n => n.note.id === note.id)?.noteHeadBounds
    const surface = (api.canvasElement as unknown as { element: HTMLElement }).element
    const wrapper = scoreCanvasRef.current
    if (!bounds || !surface || !wrapper) {
      setSelectedNote(null)
      setStatus('Note position is unavailable. Select the note again after rendering.')
      return
    }
    const surfaceRect = surface.getBoundingClientRect()
    const wrapperRect = wrapper.getBoundingClientRect()
    const x = surfaceRect.left - wrapperRect.left + bounds.x
    const y = surfaceRect.top - wrapperRect.top + bounds.y
    setNotePosition({ x, y, width: bounds.w, height: bounds.h,
      editorX: Math.max(0, Math.min(x, wrapper.clientWidth - 240)) })
    setSelectedNote(match)
    setSelectedBeat(editingRef.current?.beats.find(b => b.track === match.track && b.bar === match.bar && b.voice === match.voice && b.beat === match.beat) ?? null)
    setFret(String(match.fret))
  })
  return () => {
    soundFontAbort.current?.abort()
    removeSoundFontLoaded()
    removeSoundFontFailure?.()
    pendingLoad.current?.reject(new Error('Player closed.'))
    pendingLoad.current = null
    api.destroy()
    apiRef.current = null
  }
}, [])

  async function openFile(file?: File) {
    if (!file) return
    setSynced(false)
    setSelectedNote(null)
    selectMeasure(null)
    setClipboard(null)
    setEditMode(false)
    lastNoteClick.current = null
    editingRef.current = null
    setEditing(null)
    apiRef.current?.stop()
    setBusy(true)
    setStatus('Reading file…')
    try {
      const form = new FormData()
      form.append('file', file)
      const response = await fetch(`${API}/api/sessions`, { method: 'POST', body: form })
      if (!response.ok) throw new Error(await response.text())
      const metadata: Song = await response.json()
      updateSong(metadata)
      setSelectedTrack(0)
      const bytes = new Uint8Array(await file.arrayBuffer())
      const stateResponse = await fetch(`${API}/api/sessions/${metadata.sessionId}/editing`)
      if (!stateResponse.ok) throw new Error(await stateResponse.text())
      updateEditing(await stateResponse.json())
      await loadScore(bytes)

      setStatus(`Loading score: ${file.name}`)
    } catch (e) {
      setStatus(e instanceof Error ? e.message : String(e))
    } finally { setBusy(false) }
  }

  
function selectTrack(index: number) {
  const api = apiRef.current
  const score = api?.score

  if (!score?.tracks?.[index]) {
    console.error('Track not found:', index)
    return
  }

  setSelectedTrack(index)
  setSelectedNote(null)
  selectMeasure(null)
  lastNoteClick.current = null

  api.renderTracks([score.tracks[index]])

  console.log('[Track selected]', score.tracks[index].name)
}


  async function refreshSession() {
    if (!song) return
    const response = await fetch(`${API}/api/sessions/${song.sessionId}`)
    if (!response.ok) throw new Error(await response.text())
    updateSong(await response.json())
  }

  async function duplicateTrack() {
    if (!song || !editMode) return
    setBusy(true)
    setSynced(false)
    try {
      const response = await fetch(`${API}/api/sessions/${song.sessionId}/tracks/${selectedTrack}/duplicate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({})
      })
      if (!response.ok) throw new Error(await response.text())
      await refreshSession()
      setSynced(false)
      const stateResponse = await fetch(`${API}/api/sessions/${song.sessionId}/editing`)
      if (!stateResponse.ok) throw new Error(await stateResponse.text())
      updateEditing(await stateResponse.json())
      await reloadSession(song.sessionId, selectedTrack)
      setStatus('Track duplicated with independent channels. Editing history reset. Save GP5 to export it.')
    } catch (e) { setStatus(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(false) }
  }

  async function deleteTrack() {
    if (!song || !editing || !editMode || busy || playing || !synced || song.tracks.length <= 1) return
    setBusy(true)
    apiRef.current?.stop()
    try {
      const response = await fetch(`${API}/api/sessions/${song.sessionId}/tracks/${selectedTrack}/delete`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ commandId: crypto.randomUUID(), expectedRevision: editing.revision })
      })
      if (!response.ok) throw await apiError(response)
      const result = await response.json()
      setSynced(false)
      updateSong(result.song)
      updateEditing(result.editing)
      setClipboard(null)
      selectMeasure(null)
      const next = Math.min(selectedTrack, result.song.tracks.length - 1)
      setSelectedTrack(next)
      await reloadSession(song.sessionId, next)
      setStatus('Track deleted. Ctrl+Z restores it. Save GP5 to export the change.')
    } catch (error) {
      setSynced(false)
      setStatus(error instanceof Error ? error.message : String(error))
    } finally { setBusy(false) }
  }

  async function unlinkTrack(track: Track) {
    if (!song || !editing || !editMode || busy || playing || !synced ||
        apiRef.current?.playerState === alphaTab.synth.PlayerState.Playing) return
    setBusy(true)
    apiRef.current?.stop()
    try {
      const response = await fetch(`${API}/api/sessions/${song.sessionId}/tracks/${track.index}/unlink`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ commandId: crypto.randomUUID(), expectedRevision: editing.revision })
      })
      if (!response.ok) throw new Error(await response.text())
      const result: { song: Song; editing: EditingState } = await response.json()
      updateSong(result.song)
      updateEditing(result.editing)
      setSynced(false)
      await reloadSession(song.sessionId, selectedTrack)
      setStatus(`${track.name} now has independent MIDI channels.`)
    } catch (error) {
      setSynced(false)
      setStatus(error instanceof Error ? error.message : String(error))
    } finally { setBusy(false) }
  }

  async function applyFret() {
    if (!editMode || !song || !editing || busy || playing || apiRef.current?.playerState === alphaTab.synth.PlayerState.Playing || !synced) return
    if (!selectedBeat || (selectedNote && !validFretDraft(fret, selectedNote.maxFret))) return
    const drafts = selectedNote ? { ...noteDrafts, [`${selectedNote.kind ?? 'note'}:${selectedNote.string}`]: fret } : noteDrafts
    const changes = Object.entries(drafts).map(([key, value]) => {
      const [kind, string] = key.split(':')
      return { kind, string: Number(string), fret: value.trim() === '' ? null : Number(value) }
    }).filter(change => {
      if (change.kind === 'grace' && drafts[`note:${change.string}`]?.trim() === '') return false
      const original = appendBeat ? undefined : editing.notes.find(n => n.track === selectedBeat.track && n.bar === selectedBeat.bar && n.voice === selectedBeat.voice && n.beat === selectedBeat.beat && (n.kind ?? 'note') === change.kind && n.string === change.string)
      return change.fret !== (original?.fret ?? null)
    })
    const rhythm = rhythmDraft && (appendBeat || JSON.stringify(rhythmDraft) !== JSON.stringify(selectedBeat.rhythm)) ? rhythmDraft : undefined
    if (!changes.length && !rhythm) return
    setBusy(true)
    apiRef.current?.stop()
    try {
      const response = await fetch(`${API}/api/sessions/${song.sessionId}/beat-notes`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ commandId: crypto.randomUUID(), expectedRevision: editing.revision,
          beatId: selectedBeat.id, changes, rhythm, append: appendBeat })
      })
      if (!response.ok) {
        const error = await apiError(response)
        if (response.status === 422) { setStatus(error.message); return }
        throw error
      }
      setSynced(false)
      updateEditing(await response.json())
      await reloadSession(song.sessionId, selectedTrack)
      setNoteDrafts({})
      setStatus('Notes updated. Save GP5 to download the edited score.')
    } catch (e) {
      // A lost response may follow a committed edit. Require an explicit resync.
      setSynced(false)
      setStatus(e instanceof Error ? e.message : String(e))
    } finally { setBusy(false) }
  }

  function validFretDraft(value: string, max: number) {
    return value.trim() === '' || (Number.isInteger(Number(value)) && Number(value) >= 0 && Number(value) <= max)
  }

  function rhythmFields() {
    if (!rhythmDraft || !selectedBeat) return null
    return <>
      <small>{appendBeat ? 'New beat at end of measure' : 'Selected beat'} · Remaining: {(selectedBeat.remainingTicks / 960).toFixed(3).replace(/\.?0+$/, '')} beats</small>
      <label>Length <select aria-label="Note length" value={rhythmDraft.value}
        onChange={e => setRhythmDraft({ ...rhythmDraft, value: Number(e.target.value) })}>
        {[1, 2, 4, 8, 16, 32, 64, 128].map(value => <option key={value} value={value}>{value === 1 ? 'Whole' : `1/${value}`}</option>)}
      </select></label>
      <label><input type="checkbox" checked={rhythmDraft.dotted}
        onChange={e => setRhythmDraft({ ...rhythmDraft, dotted: e.target.checked })} />Dotted</label>
      <label>Tuplet <select aria-label="Tuplet" value={rhythmDraft.tuplet}
        onChange={e => setRhythmDraft({ ...rhythmDraft, tuplet: Number(e.target.value) })}>
        {[1, 3, 5, 6, 7, 9, 10, 11, 12, 13].map(value => <option key={value} value={value}>{value === 1 ? 'None' : `${value}:${value === 3 ? 2 : value <= 7 ? 4 : 8}`}</option>)}
      </select></label>
      <small>Length applies to every string at this beat, including rests.</small>
    </>
  }

  function startNewBeat() {
    if (!selectedBeat || selectedBeat.remainingTicks <= 0) return
    const durations = [1, 2, 4, 8, 16, 32, 64, 128].flatMap(value =>
      [false, true].map(dotted => ({ value, dotted, tuplet: 1, ticks: 3840 / value * (dotted ? 1.5 : 1) })))
      .filter(r => r.ticks <= selectedBeat.remainingTicks).sort((a, b) => b.ticks - a.ticks)
    if (!durations.length) { setStatus('The remaining time is shorter than a 128th note.'); return }
    const { value, dotted, tuplet } = durations[0]
    setAppendBeat(true)
    setRhythmDraft({ value, dotted, tuplet })
    setNoteDrafts({})
    setSelectedNote({ ...selectedBeat, id: '', string: selectedBeat.stringCount, fret: 0, editable: true, beatId: selectedBeat.id })
    setFret('')
  }

  function nextString() {
    if (!selectedNote || !selectedBeat || !validFretDraft(fret, selectedNote.maxFret)) return
    const drafts = { ...noteDrafts, [`${selectedNote.kind ?? 'note'}:${selectedNote.string}`]: fret }
    setNoteDrafts(drafts)
    const string = selectedNote.string > 1 ? selectedNote.string - 1 : selectedBeat.stringCount
    const note = appendBeat ? undefined : editing?.notes.find(n => n.track === selectedBeat.track && n.bar === selectedBeat.bar && n.voice === selectedBeat.voice && n.beat === selectedBeat.beat && n.string === string && n.kind !== 'grace')
    setSelectedNote(note ?? { ...selectedBeat, id: '', string, fret: 0, editable: true, beatId: selectedBeat.id })
    setFret(drafts[`note:${string}`] ?? (note ? String(note.fret) : ''))
  }

  async function recoverScore() {
    if (!song) return
    setBusy(true)
    apiRef.current?.stop()
    try {
      const summaryResponse = await fetch(`${API}/api/sessions/${song.sessionId}`)
      if (!summaryResponse.ok) throw await apiError(summaryResponse)
      const summary: Song = await summaryResponse.json()
      updateSong(summary)
      const response = await fetch(`${API}/api/sessions/${song.sessionId}/editing`)
      if (!response.ok) throw new Error(await response.text())
      updateEditing(await response.json())
      await reloadSession(song.sessionId, Math.min(selectedTrack, summary.tracks.length - 1))
      setStatus('Score synchronized.')
    } catch (e) { setStatus(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(false) }
  }

  async function changeTrackSetting(track: Track, change: { solo?: boolean; mute?: boolean; instrument?: number; bank?: number }) {
    if (!song || !editing || busy || !synced || (change.instrument !== undefined &&
        (playing || apiRef.current?.playerState === alphaTab.synth.PlayerState.Playing))) return
    setBusy(true)
    try {
      const response = await fetch(`${API}/api/sessions/${song.sessionId}/tracks/${track.index}/settings`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ commandId: crypto.randomUUID(), expectedRevision: editing.revision, ...change })
      })
      if (!response.ok) throw new Error(await response.text())
      const result: { song: Song; editing: EditingState } = await response.json()
      updateSong(result.song)
      updateEditing(result.editing)
      if (change.instrument !== undefined) {
        setSynced(false)
        apiRef.current?.stop()
        await reloadSession(song.sessionId, selectedTrack)
      } else {
        applyTrackMix(apiRef.current, result.song.tracks)
      }
      setStatus(track.sharedTracks.length > 1 ? 'Updated linked tracks sharing MIDI channels.' : 'Track setting updated.')
    } catch (error) {
      apiRef.current?.pause()
      setSynced(false)
      setStatus(error instanceof Error ? error.message : String(error))
    } finally { setBusy(false) }
  }

  async function changeHistory(direction: 'undo' | 'redo') {
    if (!editMode || !song || !editing || busy || historyPending.current || playing || !synced ||
        apiRef.current?.playerState === alphaTab.synth.PlayerState.Playing ||
        !(direction === 'undo' ? editing.canUndo : editing.canRedo)) return
    historyPending.current = true
    setBusy(true)
    apiRef.current?.stop()
    try {
      const response = await fetch(`${API}/api/sessions/${song.sessionId}/history/${direction}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ commandId: crypto.randomUUID(), expectedRevision: editing.revision })
      })
      if (!response.ok) throw new Error(await response.text())
      setSynced(false)
      updateEditing(await response.json())
      const summaryResponse = await fetch(`${API}/api/sessions/${song.sessionId}`)
      if (!summaryResponse.ok) throw await apiError(summaryResponse)
      const summary: Song = await summaryResponse.json()
      updateSong(summary)
      const next = Math.min(selectedTrack, summary.tracks.length - 1)
      setSelectedTrack(next)
      setClipboard(null)
      selectMeasure(null)
      await reloadSession(song.sessionId, next)
      setStatus(direction === 'undo' ? 'Change undone.' : 'Change redone.')
    } catch (e) {
      setSynced(false)
      setStatus(e instanceof Error ? e.message : String(e))
    } finally { historyPending.current = false; setBusy(false) }
  }

  function toggleEditMode() {
    if (!song || busy || !synced) return
    apiRef.current?.pause()
    setEditMode(value => !value)
    selectMeasure(null)
    lastNoteClick.current = null
    setStatus(editMode ? 'Edit mode exited.' : 'Edit mode: click a bar, Ctrl+C to copy, select a destination and Ctrl+V to replace. Double-click a note to edit its fret.')
  }

  async function chooseFile(kind: 'score' | 'soundfont') {
    if (busy || pickerPending.current) return
    pickerPending.current = true
    try {
      const file = await pickFile(kind, () => (kind === 'score' ? scoreFileRef : soundFontFileRef).current?.click())
      if (file) {
        if (kind === 'score') await openFile(file)
        else await changeSoundFont(file)
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error))
    } finally { pickerPending.current = false }
  }

  async function measureClipboard(action: 'copy' | 'paste') {
    if (!song || !editing || !editMode || !selectedMeasure || busy || playing || !synced || clipboardPending.current ||
        apiRef.current?.playerState === alphaTab.synth.PlayerState.Playing) return
    if (action === 'paste' && !clipboard) { setStatus('Copy a source measure with Ctrl+C first.'); return }
    clipboardPending.current = true
    setBusy(true)
    let committedPaste = false
    try {
      const response = await fetch(`${API}/api/sessions/${song.sessionId}/measures/${action}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expectedRevision: editing.revision, track: selectedMeasure.track, bar: selectedMeasure.bar,
          ...(action === 'copy' ? { count: measureCount(selectedMeasure) } : {}),
          ...(action === 'paste' ? { commandId: crypto.randomUUID(), clipboardId: clipboard!.clipboardId } : {}) })
      })
      if (!response.ok) {
        if (response.status === 409) setSynced(false)
        throw await apiError(response)
      }
      if (action === 'copy') {
        const copied = await response.json()
        setClipboard(copied)
        setStatus(`Copied ${measureCount(selectedMeasure)} bars from track ${selectedMeasure.track + 1}. Select a destination start bar and press Ctrl+V to overwrite.${copied.excludedControllers ? ' Source tempo/instrument/mixer changes are not copied; destination settings are kept.' : ''}`)
      } else {
        committedPaste = true
        setSynced(false)
        updateEditing(await response.json())
        selectMeasure({ track: selectedMeasure.track, bar: selectedMeasure.bar,
          endBar: selectedMeasure.bar + clipboard!.count - 1, anchor: selectedMeasure.bar })
        await reloadSession(song.sessionId, selectedTrack)
        setStatus(`${clipboard!.count} destination bars overwritten. Ctrl+Z to undo the whole paste.`)
      }
    } catch (error) {
      if (committedPaste || (error instanceof TypeError)) setSynced(false)
      setStatus(error instanceof Error ? error.message : String(error))
    } finally { clipboardPending.current = false; setBusy(false) }
  }

  async function saveGp5() {
    if (!song) return
    setBusy(true)
    try {
      const response = await fetch(`${API}/api/sessions/${song.sessionId}/download?format=gp5`)
      if (!response.ok) throw new Error(await response.text())
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `${song.title || 'score'}_edited.gp5`; a.click()
      URL.revokeObjectURL(url)
      setStatus('GP5 export downloaded.')
    } catch (e) { setStatus(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(false) }
  }

  function togglePlayback() {
    const api = apiRef.current as alphaTab.AlphaTabApi | null
    if (!api || !song || busy || !synced || soundFontPending.current) return
    if (api.playerState === alphaTab.synth.PlayerState.Playing) {
      api.pause()
      setStatus('Playback paused. Space to resume.')
      return
    }
    if (!soundFontUsable || !api.isReadyForPlayback) {
      setStatus('Player is not ready. Check SoundFont loading.')
      return
    }
    setSelectedNote(null)
    setStatus(api.play() ? 'Playback started. Space to pause.' : 'Playback could not start.')
  }

  function changePlaybackSpeed(value: number) {
    const speed = Math.round(Math.max(0.1, Math.min(2, value)) * 20) / 20
    playbackSpeedRef.current = speed
    setPlaybackSpeed(speed)
    setSpeedInput(speed.toFixed(2))
    if (apiRef.current) apiRef.current.playbackSpeed = speed
  }

  function commitSpeedInput() {
    const value = Number(speedInput)
    if (speedInput.trim() && Number.isFinite(value)) changePlaybackSpeed(value)
    else setSpeedInput(playbackSpeedRef.current.toFixed(2))
  }

  async function changeSoundFont(file: File | null) {
    const api = apiRef.current as alphaTab.AlphaTabApi | null
    if (!api || busy || soundFontPending.current || !soundFontSettled) return
    const previous = activeSoundFont.current
    const controller = new AbortController()
    soundFontAbort.current = controller
    soundFontPending.current = true
    setBusy(true)
    setSelectedNote(null)
    api.stop()
    setSoundFontMessage(`Loading ${file?.name ?? DEFAULT_SOUND_FONT_NAME}...`)
    let replacing = false
    try {
      const data = file ? await readSoundFont(file) : await defaultSoundFontData(controller.signal)
      const nextPresets = parseSoundFontPresets(data)
      if (controller.signal.aborted) return
      replacing = true
      setSoundFontUsable(false)
      await replaceSoundFont(api, data, controller.signal)
      activeSoundFont.current = file
      setPresets(nextPresets)
      setSoundFontName(file?.name ?? DEFAULT_SOUND_FONT_NAME)
      setSoundFontUsable(true)
      setSoundFontMessage('SoundFont ready. Press Space to listen.')
    } catch (error) {
      if (controller.signal.aborted) return
      const message = error instanceof Error ? error.message : String(error)
      if (replacing) {
        setSoundFontMessage(`${message} Restoring previous SoundFont...`)
        try {
          const data = previous ? await readSoundFont(previous) : await defaultSoundFontData(controller.signal)
          await replaceSoundFont(api, data, controller.signal)
          setPresets(parseSoundFontPresets(data))
          setSoundFontName(previous?.name ?? DEFAULT_SOUND_FONT_NAME)
          setSoundFontUsable(true)
          setSoundFontMessage(`${message} Previous SoundFont restored.`)
        } catch (restoreError) {
          if (controller.signal.aborted) return
          setSoundFontName('Unavailable')
          setSoundFontUsable(false)
          setSoundFontMessage(`${message} Restore failed: ${String(restoreError)}. Retry the default SoundFont.`)
        }
      } else {
        setSoundFontMessage(message)
      }
    } finally {
      soundFontPending.current = false
      soundFontAbort.current = null
      setBusy(false)
    }
  }

  async function defaultSoundFontData(signal: AbortSignal) {
    const response = await fetch(DEFAULT_SOUND_FONT, { signal })
    if (!response.ok) throw new Error('Could not load the default SoundFont.')
    return new Uint8Array(await response.arrayBuffer())
  }

  return <main className="app">
    <div ref={controlsRef} className="app-controls">
      <header className="topbar" aria-label="Score controls">
        <div className="transport-actions" title="Space: play / pause; Ctrl+Z: undo; Ctrl+Shift+Z: redo">
          <button disabled={!song || busy || !synced || !soundFontUsable} onClick={togglePlayback} aria-keyshortcuts="Space">{playing ? 'Pause' : 'Play'}</button>
          <div className="playback-speed" title="Playback speed">
            <input aria-label="Playback speed slider" type="range" min="0.1" max="2" step="0.05"
              value={playbackSpeed} onChange={e => changePlaybackSpeed(Number(e.target.value))} />
            <input aria-label="Playback speed" type="number" min="0.1" max="2" step="0.05"
              value={speedInput} onChange={e => {
                const text = e.target.value
                setSpeedInput(text)
                const value = Number(text)
                if (text.trim() && value >= 0.1 && value <= 2 && Math.abs(value * 20 - Math.round(value * 20)) < 1e-8) {
                  playbackSpeedRef.current = value
                  setPlaybackSpeed(value)
                  if (apiRef.current) apiRef.current.playbackSpeed = value
                }
              }} onBlur={commitSpeedInput} onKeyDown={e => {
                if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); commitSpeedInput() }
              }} />
            <span aria-hidden="true">×</span>
          </div>
          <button disabled={!song || busy} onClick={() => apiRef.current?.stop()}>Stop</button>
          <button aria-pressed={editMode} disabled={!song || busy || !synced} onClick={toggleEditMode}>{editMode ? 'Exit edit mode' : 'Enter edit mode'}</button>
          {editMode && <button disabled={!song || busy || playing || !synced || song.tracks[selectedTrack]?.isPercussionTrack}
            title={song?.tracks[selectedTrack]?.isPercussionTrack ? 'Independent percussion routing is not supported yet.' : 'Copy this track to independent MIDI channels'}
            onClick={duplicateTrack}>Duplicate selected track</button>}
          {editMode && <button disabled={!song || busy || playing || !synced || song.tracks.length <= 1}
            title={song?.tracks.length === 1 ? 'At least one track must remain.' : 'Delete this track (Ctrl+Z to restore)'}
            onClick={() => void deleteTrack()}>Delete selected track</button>}
        </div>
        <div className="file-actions">
          <div className="soundfont-actions" role="group" aria-label="SoundFont">
            <button className="open-button" title={soundFontMessage} disabled={busy || !soundFontSettled} onClick={() => chooseFile('soundfont')}>SoundFont</button>
            <input ref={soundFontFileRef} hidden type="file" accept=".sf2,.sf3" onChange={e => { const file = e.target.files?.[0]; e.target.value = ''; if (file) void changeSoundFont(file) }} />
            <button disabled={busy || !soundFontSettled} onClick={() => changeSoundFont(null)} title="Use default SoundFont">Default</button>
            <span className="soundfont-name" title={`${soundFontName}: ${soundFontMessage}`}>{soundFontName}</span>
          </div>
          <button className="open-button" disabled={busy} onClick={() => chooseFile('score')}>Open GP file</button>
          <input ref={scoreFileRef} hidden type="file" accept=".gp3,.gp4,.gp5" onChange={e => { const file = e.target.files?.[0]; e.target.value = ''; if (file) void openFile(file) }} />
          <button disabled={!song || busy} onClick={saveGp5}>Save GP5</button>
          <button disabled={!song || busy} onClick={() => apiRef.current?.print()}>Print / PDF</button>
        </div>
      </header>
      <div className="operation-status" role="status" aria-live="polite">{busy ? 'Working... ' : ''}{status}</div>



    </div>

    <section className="toolbar" aria-label="Note editor">
      <span className="muted soundfont-status" role="status">{soundFontMessage}</span>
      <span>{editMode ? (selectedMeasure ? `Track ${selectedMeasure.track + 1} / Bars ${selectedMeasure.bar + 1}-${selectedMeasure.endBar + 1} (${measureCount(selectedMeasure)} selected)` : 'Click a bar; Shift+click another bar to select a range. Double-click a note to edit its fret.') : 'View mode'}</span>
      {editMode && <span className="muted">Ctrl+C: copy range / Ctrl+V: overwrite from selected start / Ctrl+Z: undo{clipboard ? ` / Copied: ${clipboard.count} bars from track ${clipboard.track + 1}` : ''}</span>}
      {song && !synced && !busy && <button onClick={recoverScore}>Reload server score</button>}
    </section>

    <div className="workspace">
      <aside className="tracks">
        <h3>Tracks</h3>
        {song?.tracks.map(track => {
          const available = trackPresets(presets, track.isPercussionTrack)
          const currentBank = track.isPercussionTrack ? track.bank | 128 : track.bank
          const current = `${currentBank}:${track.instrument}`
          const present = available.some(p => `${p.bank}:${p.program}` === current)
          return <div key={track.index} className={selectedTrack === track.index ? 'track-card selected' : 'track-card'}>
            <button className="track" disabled={busy || !synced} onClick={() => selectTrack(track.index)}>
              <span>{track.name}</span><small>{track.measureCount} bars</small>
            </button>
            <div className="track-mix">
              <button aria-pressed={track.isSolo} className={track.isSolo ? 'active' : ''} disabled={busy || !synced}
                onClick={() => changeTrackSetting(track, { solo: !track.isSolo })}>Solo</button>
              <button aria-pressed={track.isMute} className={track.isMute ? 'active muted-track' : ''} disabled={busy || !synced}
                onClick={() => changeTrackSetting(track, { mute: !track.isMute })}>Mute</button>
              {track.sharedTracks.length > 1 && <small title="These tracks share MIDI channels and change together.">Linked: {track.sharedTracks.map(i => i + 1).join(', ')}</small>}
              {editMode && track.sharedTracks.length > 1 && <button disabled={busy || playing || !synced || track.isPercussionTrack}
                title={track.isPercussionTrack ? 'Independent percussion routing is not supported yet.' : 'Give this track its own MIDI channels'}
                onClick={() => unlinkTrack(track)}>Unlink</button>}
            </div>
            <select className="track-instrument" aria-label={`${track.name} instrument`} value={current}
              title="Initial instrument from the loaded SoundFont. Existing in-song instrument changes are preserved."
              disabled={busy || playing || !synced || !soundFontUsable || !available.length}
              onChange={e => { const [bank, instrument] = e.target.value.split(':').map(Number); void changeTrackSetting(track, { bank, instrument }) }}>
              {!present && <option value={current}>{available.length ? 'Current preset not in this SoundFont' : 'No compatible presets'} ({currentBank}:{track.instrument + 1})</option>}
              {available.map(p => <option key={`${p.bank}:${p.program}`} value={`${p.bank}:${p.program}`}>{p.name || 'Unnamed'} ({p.bank}:{p.program + 1})</option>)}
            </select>
          </div>
        })}
        {!song && <p className="muted">No score loaded</p>}
      </aside>
      <section className="score-area">
        <div className="score-heading">
          <div><h2>{song?.title || 'Untitled score'}</h2><p>{song?.artist || 'Open a GP5 file to view the score'}</p></div>
          {song && <span>{song.tempo} BPM · {song.trackCount} tracks</span>}
        </div>
        <div className="score-scroll"><div ref={scoreCanvasRef} className="score-canvas">
          <div ref={scoreRef} className="score" onPointerDownCapture={event => { selectionShift.current = event.shiftKey }} />
          {editMode && selectedMeasure && !busy && !playing && synced && measurePositions.map(position =>
            <div key={position.bar} className="selected-measure-outline" aria-hidden="true" style={{ left: position.x, top: position.y,
              width: position.width, height: position.height }} />)}
          {editMode && selectedBeat && !selectedNote && notePosition && !busy && !playing && synced &&
            <div className="inline-fret-editor" style={{ left: notePosition.editorX, top: notePosition.y + notePosition.height + 8 }}
              onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); e.stopPropagation(); void applyFret() } }}>
              {rhythmFields()}
              <span>Select string:</span>
              <button disabled={!selectedBeat.canAdd || selectedBeat.remainingTicks <= 0} onClick={startNewBeat}>Add beat at end</button>
              {Array.from({ length: selectedBeat.stringCount }, (_, i) => {
                const string = selectedBeat.stringCount - i
                const note = editing?.notes.find(n => n.track === selectedBeat.track && n.bar === selectedBeat.bar && n.voice === selectedBeat.voice && n.beat === selectedBeat.beat && n.string === string && n.kind !== 'grace')
                return <button key={string} disabled={note ? !note.editable : !selectedBeat.canAdd}
                  title={`String ${i + 1}${note ? `: fret ${note.fret}` : ': add note'}`}
                  onClick={() => {
                    setSelectedNote(note ?? { ...selectedBeat, id: '', string, fret: 0, editable: true, beatId: selectedBeat.id })
                    setFret(noteDrafts[`note:${string}`] ?? (note ? String(note.fret) : ''))
                  }}>{i + 1}: {note?.fret ?? '+'}</button>
              })}
              <button onClick={() => void applyFret()}>Apply Ctrl+Enter</button>
              <button onClick={() => { setNoteDrafts({}); setSelectedBeat(null) }}>Close</button>
            </div>}
          {editMode && selectedNote && notePosition && !busy && !playing && synced && <>
            <div className="selected-note-outline" aria-hidden="true" style={{
              left: notePosition.x - 3, top: notePosition.y - 3,
              width: notePosition.width + 6, height: notePosition.height + 6 }} />
            <form className="inline-fret-editor" aria-label="Selected note fret editor"
              style={{ left: notePosition.editorX, top: notePosition.y + notePosition.height + 8 }}
              onSubmit={e => { e.preventDefault(); void applyFret() }}
              onKeyDown={e => {
                if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); if (e.ctrlKey || e.metaKey) void applyFret(); else nextString() }
                if (e.key === 'Escape') { e.preventDefault(); setAppendBeat(false); setNoteDrafts({}); setRhythmDraft(selectedBeat?.rhythm ?? null); setSelectedNote(null) }
              }}>
              <span>String {selectedBeat ? selectedBeat.stringCount + 1 - selectedNote.string : selectedNote.string}{selectedNote.kind === 'grace' ? ' (grace)' : ''}</span>
              {rhythmFields()}
              <label>Fret <input ref={fretInputRef} aria-label="Fret" type="number" min="0" max={selectedNote.maxFret}
                step="1" placeholder="Empty = delete" value={fret} onChange={e => setFret(e.target.value)} /></label>
              <button type="button" onClick={() => setFret('')}>Delete note</button>
              <button type="button" onClick={nextString} disabled={!validFretDraft(fret, selectedNote.maxFret)}>Next string ↵</button>
              <button type="submit" disabled={!validFretDraft(fret, selectedNote.maxFret)}>Apply Ctrl+Enter</button>
              <small>Blank deletes the note. Enter moves to the next string; Ctrl+Enter applies all changes.</small>
              <button type="button" onClick={() => { setAppendBeat(false); setNoteDrafts({}); setRhythmDraft(selectedBeat?.rhythm ?? null); setSelectedNote(null) }}>Cancel</button>
            </form>
          </>}
        </div></div>
      </section>
    </div>
    <footer><span>{busy ? 'Working…' : status}</span><span>Prototype 0.1</span></footer>
  </main>
}
