import type { AlphaTabApi, rendering } from '@coderline/alphatab'

type TimedBar = { start: number; end: number; tempoChanges: readonly { tick: number; tempo: number }[] }

// alphaTab MIDI ticks use 960 ticks per quarter note. Integrate tempo changes
// so even a tempo change inside a bar does not change its visual sweep speed.
export function barTimeAt(bar: TimedBar, tick: number): number {
  const end = Math.max(bar.start, Math.min(tick, bar.end))
  let position = bar.start
  let tempo = bar.tempoChanges[0]?.tempo ?? 120
  let time = 0
  for (const change of bar.tempoChanges) {
    if (change.tick > end) break
    const next = Math.max(position, change.tick)
    time += (next - position) * 60000 / (tempo * 960)
    position = next
    tempo = change.tempo
  }
  return time + (end - position) * 60000 / (tempo * 960)
}

export function barSweep(bar: TimedBar, tick: number, left: number, right: number, speed: number) {
  const total = barTimeAt(bar, bar.end)
  const elapsed = barTimeAt(bar, tick)
  return { x: left + (right - left) * (total > 0 ? elapsed / total : 0),
    endX: right, duration: Math.max(0, total - elapsed) / Math.max(0.01, speed) }
}

export function createConstantBarCursor(api: AlphaTabApi): NonNullable<AlphaTabApi['customCursorHandler']> {
  const position = (bounds: rendering.BeatBounds, fallback: number) => {
    const bars = api.tickCache?.masterBars ?? []
    const tick = api.tickPosition
    // Search playback order, including repeated occurrences of a written bar.
    let low = 0, high = bars.length - 1
    while (low <= high) {
      const mid = (low + high) >>> 1
      const bar = bars[mid]
      if (tick < bar.start) high = mid - 1
      else if (tick > bar.end || (tick === bar.end && mid < bars.length - 1)) low = mid + 1
      else {
        const master = bounds.barBounds.masterBarBounds
        if (bar.masterBar.index !== master.index) break
        const starts = master.bars.flatMap(b => b.beats.map(beat => beat.onNotesX))
        const left = starts.length ? Math.min(...starts) : master.realBounds.x
        const right = master.realBounds.x + master.realBounds.w
        return barSweep(bar, tick, left, Math.max(left, right), api.playbackSpeed)
      }
    }
    return { x: fallback, endX: fallback, duration: 0 }
  }
  return {
    onAttach() {},
    onDetach() {},
    placeBarCursor(cursor, bounds) {
      const bar = bounds.barBounds.masterBarBounds.visualBounds
      cursor.setBounds(bar.x, bar.y, bar.w, bar.h)
    },
    placeBeatCursor(cursor, bounds, fallback) {
      const { x } = position(bounds, fallback)
      const bar = bounds.barBounds.masterBarBounds.visualBounds
      cursor.transitionToX(0, x)
      cursor.setBounds(x, bar.y, 1, bar.h)
    },
    transitionBeatCursor(cursor, bounds, fallback) {
      const { x, endX, duration } = position(bounds, fallback)
      const bar = bounds.barBounds.masterBarBounds.visualBounds
      cursor.transitionToX(0, x)
      cursor.setBounds(x, bar.y, 1, bar.h)
      // Commit the instantaneous position before beginning a new CSS transition.
      const element = (cursor as unknown as { element?: HTMLElement }).element
      element?.getBoundingClientRect()
      cursor.transitionToX(duration, endX)
    }
  }
}
