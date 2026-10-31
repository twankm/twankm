import { useEffect, useRef, useState } from 'react'
import * as alphaTab from '@coderline/alphatab'

const API = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

type Track = { index: number; name: string; measureCount: number; instrument: number; isPercussionTrack: boolean; tuning: number[] }
type Song = { sessionId: string; title: string; artist: string; tempo: number; trackCount: number; tracks: Track[] }

export default function App() {
  const scoreRef = useRef<HTMLDivElement>(null)
  const apiRef = useRef<any>(null)
  const [song, setSong] = useState<Song | null>(null)
  const [selectedTrack, setSelectedTrack] = useState(0)
  const [status, setStatus] = useState('Open a Guitar Pro file to begin.')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
  if (!scoreRef.current) return

  
  const api = new alphaTab.AlphaTabApi(scoreRef.current, {
    core: {
      fontDirectory: '/font/'
    },
    display: {
      layoutMode: alphaTab.LayoutMode.Page,
      staveProfile: alphaTab.StaveProfile.Tab
    },
    player: {
      enablePlayer: true,
      playerMode: 'EnabledSynthesizer',
      soundFont: '/soundfont/sonivox.sf2',
      scrollElement: 'html,body',

      // 재생 위치 표시
      enableCursor: true,
      enableAnimatedBeatCursor: true,
      enableElementHighlighting: true
    }
  } as any)


  api.playerReady.on(() => {
    console.log('[Player] READY')
    console.log('isReadyForPlayback:', api.isReadyForPlayback)
    setStatus('Player ready. Press Play.')
  })

  api.soundFontLoad.on((e: any) => {
    const percent = e.total > 0
      ? Math.round((e.loaded / e.total) * 100)
      : 0

    console.log(`[SoundFont] ${percent}%`)
  })

  api.soundFontLoaded.on(() => {
    console.log('[SoundFont] LOADED')
  })

  api.playerStateChanged.on((e: any) => {
    console.log('[Player State]', e)
  })

  api.error.on((e: unknown) => {
    console.error('[alphaTab Error]', e)
    setStatus(`alphaTab Error: ${String(e)}`)
  })

  apiRef.current = api

  api.error.on((e: unknown) => {
    console.error('[alphaTab error]', e)
    setStatus(`Score error: ${String(e)}`)
  })

  api.scoreLoaded.on((score: any) => {
    console.log('[alphaTab] Score loaded:', score)
    setStatus('Score parsed. Rendering…')
  })

  api.soundFontLoaded.on(() => {
    console.log('[alphaTab] SoundFont loaded')
    setStatus('SoundFont loaded.')
  })

  api.playerReady.on(() => {
    console.log('[alphaTab] Player ready')
    setStatus('Player ready.')
  })

  api.playerStateChanged.on((e: unknown) => {
    console.log('[alphaTab] Player state:', e)
    setStatus(`Playback: ${String(e)}`)
  })

  return () => {
    api.destroy()
    apiRef.current = null
  }

  api.playerReady.on(() => {
    console.log('[Player] Ready for playback')
    setStatus('Player ready. Press Play.')
  })

  api.soundFontLoaded.on(() => {
    console.log('[Player] SoundFont loaded')
  })

  api.error.on((e: unknown) => {
    console.error('[alphaTab error]', e)
    setStatus(`Error: ${String(e)}`)
  })
}, [])

  async function openFile(file?: File) {
    if (!file) return
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
      const loaded = apiRef.current?.load(bytes)

      console.log('[alphaTab] Load requested:', loaded)
      console.log('[alphaTab] File size:', bytes.length)

      if (!loaded) {
        throw new Error('alphaTab rejected the file data.')
      }

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

  // 이전에 설정된 솔로 상태 초기화
  api.changeTrackSolo(score.tracks, false)

  // 선택한 트랙만 악보에 표시
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
    try {
      const response = await fetch(`${API}/api/sessions/${song.sessionId}/tracks/${selectedTrack}/duplicate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({})
      })
      if (!response.ok) throw new Error(await response.text())
      await refreshSession()
      setStatus('Track duplicated in the editing session. Save GP5 to export it.')
    } catch (e) { setStatus(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(false) }
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

  return <main className="app">
    <header className="topbar">
      <div><div className="brand">GP5 Editor</div><div className="sub">Player · TAB editor prototype</div></div>
      <label className="open-button">Open GP file<input type="file" accept=".gp3,.gp4,.gp5" onChange={e => openFile(e.target.files?.[0])} /></label>
      <button disabled={!song || busy} onClick={saveGp5}>Save GP5</button>
      <button disabled={!song} onClick={() => apiRef.current?.print()}>Print / PDF</button>
    </header>

    <section className="toolbar">
      <button
        disabled={!song || busy}
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
      <button disabled={!song || busy} onClick={duplicateTrack}>Duplicate selected track</button>
    </section>

    <div className="workspace">
      <aside className="tracks">
        <h3>Tracks</h3>
        {song?.tracks.map(track => <button key={track.index} className={selectedTrack === track.index ? 'track selected' : 'track'} onClick={() => selectTrack(track.index)}>
          <span>{track.name}</span><small>{track.measureCount} bars</small>
        </button>)}
        {!song && <p className="muted">No score loaded</p>}
      </aside>
      <section className="score-area">
        <div className="score-heading">
          <div><h2>{song?.title || 'Untitled score'}</h2><p>{song?.artist || 'Open a GP5 file to view the score'}</p></div>
          {song && <span>{song.tempo} BPM · {song.trackCount} tracks</span>}
        </div>
        <div className="score-scroll"><div ref={scoreRef} className="score" /></div>
      </section>
    </div>
    <footer><span>{busy ? 'Working…' : status}</span><span>Prototype 0.1</span></footer>
  </main>
}
