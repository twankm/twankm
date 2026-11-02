import assert from 'node:assert/strict'
import { apiError } from '../src/apiError.ts'

assert.equal((await apiError(new Response(JSON.stringify({ detail: 'Tie connection would change at bar 4.' }), { status: 422 }))).message,
  'Tie connection would change at bar 4.')
assert.equal((await apiError(new Response(JSON.stringify({ detail: [{ loc: ['body', 'count'], msg: 'Must be positive' }] }), { status: 422 }))).message,
  'body.count: Must be positive')
assert.equal((await apiError(new Response('Backend unavailable', { status: 503 }))).message, 'Backend unavailable')
console.log('Readable API rejection reasons: passed')
