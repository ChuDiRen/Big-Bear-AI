import { describe, expect, test } from 'vitest'

import config from './vite.config.js'


describe('Vite development configuration', () => {
  test('proxies the same-origin LangGraph prefix to the local Agent Server', () => {
    const proxy = config.server.proxy['/api/langgraph']

    expect(proxy.target).toBe('http://127.0.0.1:2024')
    expect(proxy.changeOrigin).toBe(true)
    expect(proxy.rewrite('/api/langgraph/threads')).toBe('/threads')
  })
})
