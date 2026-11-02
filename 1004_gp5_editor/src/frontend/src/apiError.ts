// FastAPI returns useful rejection reasons in JSON, not in the HTTP status line.
export async function apiError(response: Pick<Response, 'text' | 'status'>): Promise<Error> {
  const text = await response.text()
  try {
    const payload = JSON.parse(text)
    if (typeof payload.detail === 'string') return new Error(payload.detail)
    if (Array.isArray(payload.detail)) {
      return new Error(payload.detail.map((item: { loc?: string[]; msg?: string }) =>
        `${item.loc?.join('.') ?? 'Request'}: ${item.msg ?? 'Invalid value'}`).join('; '))
    }
  } catch { /* Plain-text errors from a proxy/development server are also valid. */ }
  return new Error(text || `Request failed (${response.status}).`)
}
