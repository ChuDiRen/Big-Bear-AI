import { describe, expect, test, vi } from 'vitest'


async function loadApi() {
  return import('./langgraph.js')
}


describe('LangGraph API adapter', () => {
  test('resolves same-origin API prefixes to an absolute SDK URL', async () => {
    const { resolveApiUrl } = await loadApi()

    expect(resolveApiUrl('/api/langgraph', 'http://127.0.0.1:5174')).toBe(
      'http://127.0.0.1:5174/api/langgraph',
    )
    expect(resolveApiUrl('https://example.com/graph', 'http://localhost')).toBe(
      'https://example.com/graph',
    )
  })

  test('adds the current session token as a Bearer authorization header', async () => {
    const { withAuthorization } = await loadApi()
    const { authSession } = await import('./auth.js')
    authSession.value = { accessToken: 'jwt-token' }

    const headers = withAuthorization({ Accept: 'application/json' })
    expect(Object.fromEntries(headers)).toEqual({
      accept: 'application/json',
      authorization: 'Bearer jwt-token',
    })
  })

  test('returns management data from a successful threadless run', async () => {
    const { createLangGraphApi } = await loadApi()
    const client = {
      runs: {
        wait: vi.fn().mockResolvedValue({ ok: true, data: { total: 2 }, error: null }),
      },
    }
    const api = createLangGraphApi({ client })

    const result = await api.manage({ operation: 'list', resource: 'rule' })

    expect(result).toEqual({ total: 2 })
    expect(client.runs.wait).toHaveBeenCalledWith(null, 'management', {
      input: { operation: 'list', resource: 'rule' },
      onDisconnect: 'cancel',
      raiseError: true,
      signal: undefined,
    })
  })

  test('turns management errors into typed exceptions', async () => {
    const { createLangGraphApi, ManagementError } = await loadApi()
    const client = {
      runs: {
        wait: vi.fn().mockResolvedValue({
          ok: false,
          data: null,
          error: { code: 'READ_ONLY_RESOURCE', message: 'read-only' },
        }),
      },
    }

    await expect(
      createLangGraphApi({ client }).manage({ operation: 'delete', resource: 'rule' }),
    ).rejects.toEqual(expect.objectContaining({
      name: 'ManagementError',
      code: 'READ_ONLY_RESOURCE',
      message: 'read-only',
    }))
    expect(ManagementError).toBeTypeOf('function')
  })

  test('decodes string and content-block message events', async () => {
    const { decodeStreamPart } = await loadApi()

    expect(decodeStreamPart({
      id: '1',
      event: 'messages',
      data: [{ content: 'hello' }, { langgraph_node: 'model', tags: [] }],
    })).toEqual(expect.objectContaining({ type: 'message', text: 'hello' }))
    expect(decodeStreamPart({
      event: 'messages',
      data: [
        { content: [{ type: 'text', text: 'big ' }, { type: 'text', text: 'bear' }] },
        { tags: [] },
      ],
    })).toEqual(expect.objectContaining({ type: 'message', text: 'big bear' }))
  })

  test('streams assistant events and records the server run id', async () => {
    const { createLangGraphApi } = await loadApi()
    const onEvent = vi.fn()
    const client = {
      runs: {
        stream: vi.fn(async function* (_threadId, _assistantId, options) {
          options.onRunCreated({ run_id: 'run-1', thread_id: 'thread-1' })
          yield {
            event: 'messages',
            data: [{ content: 'token' }, { tags: [], langgraph_node: 'model' }],
          }
          yield { event: 'updates', data: { resolve_context: { mode: 'auto' } } }
          yield { event: 'custom', data: { stage: 'search' } }
        }),
        cancel: vi.fn(),
      },
    }
    const api = createLangGraphApi({ client })

    const handle = api.streamAssistant({
      threadId: 'thread-1',
      input: { messages: [{ role: 'user', content: 'hello' }] },
      context: { mode: 'auto' },
      onEvent,
    })
    await handle.done

    expect(handle.runId).toBe('run-1')
    expect(onEvent.mock.calls.map(([event]) => event.type)).toEqual([
      'message',
      'updates',
      'custom',
    ])
    expect(client.runs.stream).toHaveBeenCalledWith('thread-1', 'assistant', expect.objectContaining({
      input: {
        messages: [{ role: 'user', content: 'hello' }],
        context: { mode: 'auto' },
      },
      streamMode: ['messages-tuple', 'updates', 'custom'],
      onDisconnect: 'cancel',
    }))
  })

  test('surfaces streamed errors and cancels the server run', async () => {
    const { createLangGraphApi } = await loadApi()
    const cancel = vi.fn().mockResolvedValue(undefined)
    const client = {
      runs: {
        stream: vi.fn(async function* (_threadId, _assistantId, options) {
          options.onRunCreated({ run_id: 'run-error', thread_id: 'thread-1' })
          yield { event: 'error', data: { error: 'MODEL_ERROR', message: 'model failed' } }
        }),
        cancel,
      },
    }
    const handle = createLangGraphApi({ client }).streamAssistant({
      threadId: 'thread-1',
      input: { messages: [] },
      onEvent: vi.fn(),
    })

    await expect(handle.done).rejects.toEqual(expect.objectContaining({
      name: 'LangGraphRunError',
      code: 'MODEL_ERROR',
      message: 'model failed',
    }))
    await handle.cancel()

    expect(cancel).toHaveBeenCalledWith('thread-1', 'run-error', true, 'interrupt')
  })

  test('creates threads through the SDK client', async () => {
    const { createLangGraphApi } = await loadApi()
    const client = {
      threads: { create: vi.fn().mockResolvedValue({ thread_id: 'thread-new' }) },
    }

    await expect(createLangGraphApi({ client }).createThread()).resolves.toBe('thread-new')
  })
})
