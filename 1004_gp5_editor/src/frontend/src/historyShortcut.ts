export function historyShortcut(event: Pick<KeyboardEvent, 'ctrlKey' | 'shiftKey' | 'altKey' | 'metaKey' | 'code' | 'key' | 'isComposing'>): 'undo' | 'redo' | null {
  if (!event.ctrlKey || event.altKey || event.metaKey || event.isComposing ||
      (event.code !== 'KeyZ' && event.key.toLowerCase() !== 'z')) return null
  return event.shiftKey ? 'redo' : 'undo'
}
