export function measureShortcut(event: Pick<KeyboardEvent, 'ctrlKey' | 'metaKey' | 'altKey' | 'shiftKey' | 'isComposing' | 'code' | 'key'>): 'copy' | 'paste' | null {
  if (!event.ctrlKey || event.metaKey || event.altKey || event.shiftKey || event.isComposing) return null
  if (event.code === 'KeyC' || event.key.toLowerCase() === 'c') return 'copy'
  if (event.code === 'KeyV' || event.key.toLowerCase() === 'v') return 'paste'
  return null
}
