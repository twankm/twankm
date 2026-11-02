export type MeasureSelection = { track: number; bar: number; endBar: number; anchor: number }

export function extendMeasureSelection(current: MeasureSelection | null, track: number, bar: number, shift: boolean): MeasureSelection {
  const anchor = shift && current?.track === track ? current.anchor : bar
  return { track, bar: Math.min(anchor, bar), endBar: Math.max(anchor, bar), anchor }
}

export function measureCount(selection: MeasureSelection): number {
  return selection.endBar - selection.bar + 1
}
