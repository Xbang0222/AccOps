import { describe, expect, it } from 'vitest'

import { getDefaultWsBaseUrl, normalizeBaseUrl } from './config'

describe('config helpers', () => {
  it('normalizes base urls by trimming whitespace and trailing slashes', () => {
    expect(normalizeBaseUrl('  http://127.0.0.1:8000/  ')).toBe('http://127.0.0.1:8000')
  })

  it('returns null for blank base urls', () => {
    expect(normalizeBaseUrl('   ')).toBeNull()
  })

  it('builds secure websocket urls for https pages', () => {
    expect(getDefaultWsBaseUrl({ protocol: 'https:', host: 'accops.local' })).toBe('wss://accops.local')
  })

  it('builds websocket urls for http pages', () => {
    expect(getDefaultWsBaseUrl({ protocol: 'http:', host: '127.0.0.1:5173' })).toBe('ws://127.0.0.1:5173')
  })
})
