import { useEffect, useRef, useState } from 'react'
import * as alphaTab from '@coderline/alphatab'
import { findEditableNote, type EditableNote, type EditingState } from './noteEditing'
import { historyShortcut } from './historyShortcut'
import { createConstantBarCursor } from './constantBarCursor'
import { DEFAULT_SOUND_FONT, DEFAULT_SOUND_FONT_NAME, readSoundFont, replaceSoundFont } from './soundFont'

const API = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

type Track = { index: number; name: string; measureCount: number; instrument: number; isPercussionTrack: boolean; tuning: number[] }
type Song = { sessionId: string; title: string; artist: string; tempo: number; trackCount: number; tracks: Track[] }

export default function App() {
  const scoreRef = useRef<HTMLDivElement>(null)
  const scoreCanvasRef = useRef<HTMLDivElement>(null)
  const fretInputRef = useRef<HTMLInputElement>(null)
  const apiRef = useRef<any>(null)
  const [song, setSong] = useState<Song | null>(null)
  const [selectedTrack, setSelectedTrack] = useState(0)
  const [status, setStatus] = useState('Open a Guitar Pro file to begin.')
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState<EditingState | null>(null)
  const [selectedNote, setSelectedNote] = useState<EditableNote | null>(null)
  const [notePosition, setNotePosition] = useState<{ x: number; y: number; width: number; height: number; editorX: number } | null>(null)
  const [fret, setFret] = useState('0')
  const [playing, setPlaying] = useState(false)
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

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const direction = historyShortcut(event)
      if (!direction) return
      const target = event.target
      // Text/number inputs retain their native undo for the uncommitted value.
      if (target instanceof HTMLElement && (target.isContentEditable || target.closest('input, textarea, select'))) return
      event.preventDefault()
      if (!event.repeat) void changeHistory(direction)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [song, editing, busy, playing, synced, selectedTrack])

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
        if (!apiRef.current?.load(bytes, [track])) throw new Error('alphaTab rejected the file data.')
      } catch (error) {
        pendingLoad.current?.reject(error instanceof Error ? error : new Error(String(error)))
        pendingLoad.current = null
      }
    })
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
  api.playerReady.on(() => setStatus('Player ready.'))
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
    pendingLoad.current?.resolve()
    pendingLoad.current = null
  })
  api.renderStarted.on(() => setSelectedNote(null))
  api.noteMouseDown.on((note: any) => {
    const match = findEditableNote(note, editingRef.current)
    if (!match) {
      setSelectedNote(null)
      setStatus('This note cannot be safely edited yet (effects, ties or unsupported mapping).')
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
      setSong(metadata)
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

  api.renderTracks([score.tracks[index]])

  console.log('[Track selected]', score.tracks[index].name)
}


  async function refreshSession() {
    if (!song) return
    const response = await fetch(`${API}/api/sessions/${song.sessionId}`)
    if (!response.ok) throw new Error(await response.text())
    setSong(await response.json())
  }

  async function duplicateTrack() {
    if (!song) return
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
      setStatus('Track duplicated. Fret history reset. Save GP5 to export it.')
    } catch (e) { setStatus(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(false) }
  }

  async function applyFret() {
    if (!song || !selectedNote || !editing || busy || playing || apiRef.current?.playerState === alphaTab.synth.PlayerState.Playing || !synced) return
    if (fret.trim() === '' || !Number.isInteger(Number(fret)) || Number(fret) < 0 ||
        Number(fret) > selectedNote.maxFret || Number(fret) === selectedNote.fret) return
    setBusy(true)
    apiRef.current?.stop()
    try {
      const response = await fetch(`${API}/api/sessions/${song.sessionId}/fret`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ commandId: crypto.randomUUID(), expectedRevision: editing.revision,
          noteId: selectedNote.id, fret: Number(fret) })
      })
      if (!response.ok) throw new Error(await response.text())
      setSynced(false)
      updateEditing(await response.json())
      await reloadSession(song.sessionId, selectedTrack)
      setStatus('Fret updated. Save GP5 to download the edited score.')
    } catch (e) {
      // A lost response may follow a committed edit. Require an explicit resync.
      setSynced(false)
      setStatus(e instanceof Error ? e.message : String(e))
    } finally { setBusy(false) }
  }

  async function recoverScore() {
    if (!song) return
    setBusy(true)
    apiRef.current?.stop()
    try {
      const response = await fetch(`${API}/api/sessions/${song.sessionId}/editing`)
      if (!response.ok) throw new Error(await response.text())
      updateEditing(await response.json())
      await reloadSession(song.sessionId, selectedTrack)
      setStatus('Score synchronized.')
    } catch (e) { setStatus(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(false) }
  }

  async function changeHistory(direction: 'undo' | 'redo') {
    if (!song || !editing || busy || historyPending.current || playing || !synced ||
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
      await reloadSession(song.sessionId, selectedTrack)
      setStatus(direction === 'undo' ? 'Fret change undone.' : 'Fret change redone.')
    } catch (e) {
      setSynced(false)
      setStatus(e instanceof Error ? e.message : String(e))
    } finally { historyPending.current = false; setBusy(false) }
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
      const data = file ? await readSoundFont(file) : DEFAULT_SOUND_FONT
      if (controller.signal.aborted) return
      replacing = true
      setSoundFontUsable(false)
      await replaceSoundFont(api, data, controller.signal)
      activeSoundFont.current = file
      setSoundFontName(file?.name ?? DEFAULT_SOUND_FONT_NAME)
      setSoundFontUsable(true)
      setSoundFontMessage('SoundFont ready. Press Play to listen.')
    } catch (error) {
      if (controller.signal.aborted) return
      const message = error instanceof Error ? error.message : String(error)
      if (replacing) {
        setSoundFontMessage(`${message} Restoring previous SoundFont...`)
        try {
          const data = previous ? await readSoundFont(previous) : DEFAULT_SOUND_FONT
          await replaceSoundFont(api, data, controller.signal)
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

  return <main className="app">
    <header className="topbar">
      <div><div className="brand">GP5 Editor</div><div className="sub">Player · TAB editor prototype</div></div>
      <label className="open-button">Open GP file<input type="file" disabled={busy} accept=".gp3,.gp4,.gp5" onChange={e => openFile(e.target.files?.[0])} /></label>
      <button disabled={!song || busy} onClick={saveGp5}>Save GP5</button>
      <button disabled={!song} onClick={() => apiRef.current?.print()}>Print / PDF</button>
    </header>

    <section className="toolbar">
      <button
        disabled={!song || busy || !synced || !soundFontUsable}
        onClick={() => {
          const api = apiRef.current

          console.log('=== PLAY TEST ===')
          console.log('API:', api)
          console.log('Ready:', api?.isReadyForPlayback)
          console.log('Player mode:', api?.actualPlayerMode)

          const result = api?.play()

          console.log('Play result:', result)

          if (!api?.isReadyForPlayback) {
            setStatus('Player is not ready. Check SoundFont loading.')
          } else if (!result) {
            setStatus('Playback could not start.')
          } else {
            setStatus('Playback started.')
          }
        }}
      >
        Play
      </button>
      <button disabled={!song} onClick={() => apiRef.current?.stop()}>Stop</button>
      <button title="Undo (Ctrl+Z)" aria-keyshortcuts="Control+Z" disabled={!editing?.canUndo || busy || playing || !synced} onClick={() => changeHistory('undo')}>Undo</button>
      <button title="Redo (Ctrl+Shift+Z)" aria-keyshortcuts="Control+Shift+Z" disabled={!editing?.canRedo || busy || playing || !synced} onClick={() => changeHistory('redo')}>Redo</button>
      <button disabled={!song || busy || playing || !synced} onClick={duplicateTrack}>Duplicate selected track</button>
    </section>

    <section className="toolbar" aria-label="SoundFont">
      <label className="open-button">Load SoundFont<input type="file" accept=".sf2,.sf3" disabled={busy || !soundFontSettled}
        onChange={e => { const file = e.target.files?.[0]; e.target.value = ''; if (file) void changeSoundFont(file) }} /></label>
      <button disabled={busy || !soundFontSettled} onClick={() => changeSoundFont(null)}>Use default SoundFont</button>
      <span>{soundFontName}</span>
      <span className="muted" role="status">{soundFontMessage}</span>
    </section>

    <section className="toolbar" aria-label="Note editor">
      <span>{selectedNote ? `Bar ${selectedNote.bar + 1} / selected fret ${selectedNote.fret}` : 'Click an ordinary TAB note to edit its fret.'}</span>
      {song && !synced && !busy && <button onClick={recoverScore}>Reload server score</button>}
    </section>

    <div className="workspace">
      <aside className="tracks">
        <h3>Tracks</h3>
        {song?.tracks.map(track => <button key={track.index} disabled={busy || !synced} className={selectedTrack === track.index ? 'track selected' : 'track'} onClick={() => selectTrack(track.index)}>
          <span>{track.name}</span><small>{track.measureCount} bars</small>
        </button>)}
        {!song && <p className="muted">No score loaded</p>}
      </aside>
      <section className="score-area">
        <div className="score-heading">
          <div><h2>{song?.title || 'Untitled score'}</h2><p>{song?.artist || 'Open a GP5 file to view the score'}</p></div>
          {song && <span>{song.tempo} BPM · {song.trackCount} tracks</span>}
        </div>
        <div className="score-scroll"><div ref={scoreCanvasRef} className="score-canvas">
          <div ref={scoreRef} className="score" />
          {selectedNote && notePosition && !busy && !playing && synced && <>
            <div className="selected-note-outline" aria-hidden="true" style={{
              left: notePosition.x - 3, top: notePosition.y - 3,
              width: notePosition.width + 6, height: notePosition.height + 6 }} />
            <form className="inline-fret-editor" aria-label="Selected note fret editor"
              style={{ left: notePosition.editorX, top: notePosition.y + notePosition.height + 8 }}
              onSubmit={e => { e.preventDefault(); void applyFret() }}
              onKeyDown={e => { if (e.key === 'Escape') { e.preventDefault(); setSelectedNote(null) } }}>
              <label>Fret <input ref={fretInputRef} aria-label="Fret" type="number" min="0" max={selectedNote.maxFret}
                required step="1" value={fret} onChange={e => setFret(e.target.value)} /></label>
              <button type="submit" disabled={fret.trim() === '' || !Number.isInteger(Number(fret)) ||
                Number(fret) < 0 || Number(fret) > selectedNote.maxFret || Number(fret) === selectedNote.fret}>Apply fret</button>
              <button type="button" onClick={() => setSelectedNote(null)}>Cancel</button>
            </form>
          </>}
        </div></div>
      </section>
    </div>
    <footer><span>{busy ? 'Working…' : status}</span><span>Prototype 0.1</span></footer>
  </main>
}
