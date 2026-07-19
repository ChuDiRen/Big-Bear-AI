import { beforeEach, describe, expect, test, vi } from 'vitest'


const fetchMock = vi.fn()

vi.stubGlobal('fetch', fetchMock)


async function loadAuth() {
  vi.resetModules()
  return import('./auth.js')
}


describe('authentication session', () => {
  beforeEach(() => {
    localStorage.clear()
    fetchMock.mockReset()
  })

  test('registers, signs in, and persists the returned session', async () => {
    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => ({ id: 'user-1' }) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: 'token-1',
          user: { id: 'user-1', username: 'bear' },
        }),
      })
    const { authSession, register } = await loadAuth()

    await register({
      username: 'bear',
      email: 'bear@example.com',
      password: 'password-123',
      display_name: null,
    })

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/langgraph/auth/register',
      '/api/langgraph/auth/login',
    ])
    expect(authSession.value).toEqual({
      accessToken: 'token-1',
      user: { id: 'user-1', username: 'bear' },
    })
  })

  test('clears an invalid persisted session', async () => {
    localStorage.setItem('big-bear-auth-session', '{invalid')

    const { authSession } = await loadAuth()

    expect(authSession.value).toBeNull()
    expect(localStorage.getItem('big-bear-auth-session')).toBeNull()
  })
})