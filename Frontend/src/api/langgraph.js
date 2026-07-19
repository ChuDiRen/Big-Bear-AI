import { Client } from '@langchain/langgraph-sdk'

import { accessToken } from './auth.js'


export class ManagementError extends Error {
  constructor(code, message, fields) {
    super(message)
    this.name = 'ManagementError'
    this.code = code
    this.fields = fields
  }
}


export class LangGraphRunError extends Error {
  constructor(code, message) {
    super(message)
    this.name = 'LangGraphRunError'
    this.code = code
  }
}


export function decodeStreamPart(part) {
  if (part.event === 'messages') {
    const [message, metadata] = part.data
    return {
      type: 'message',
      text: messageText(message?.content),
      message,
      metadata,
      id: part.id,
    }
  }
  return {
    type: part.event,
    data: part.data,
    id: part.id,
  }
}


export function createLangGraphApi({ apiUrl, apiKey = null, client } = {}) {
  const configuredUrl = apiUrl ?? import.meta.env.VITE_LANGGRAPH_API_URL ?? '/api/langgraph'
  const sdk = client ?? new Client({
    apiUrl: resolveApiUrl(configuredUrl),
    apiKey,
    onRequest: (url, init) => ({
      ...init,
      headers: withAuthorization(init.headers),
    }),
  })

  async function manage(input, { signal } = {}) {
    const output = await sdk.runs.wait(null, 'management', {
      input,
      onDisconnect: 'cancel',
      raiseError: true,
      signal,
    })
    if (!output?.ok) {
      const error = output?.error ?? {}
      throw new ManagementError(
        error.code ?? 'UNKNOWN_ERROR',
        error.message ?? 'Management operation failed',
        error.fields,
      )
    }
    return output.data
  }

  async function createThread(options = {}) {
    const thread = await sdk.threads.create(options)
    return thread.thread_id
  }

  function streamAssistant({ threadId, input, context, onEvent = () => {} }) {
    const controller = new AbortController()
    let runId
    const graphInput = context ? { ...input, context } : input
    const done = (async () => {
      for await (const part of sdk.runs.stream(threadId, 'assistant', {
        input: graphInput,
        streamMode: ['messages-tuple', 'updates', 'custom'],
        onDisconnect: 'cancel',
        signal: controller.signal,
        onRunCreated: ({ run_id: createdRunId }) => {
          runId = createdRunId
        },
      })) {
        if (part.event === 'error') {
          throw new LangGraphRunError(
            part.data?.error ?? 'RUN_ERROR',
            part.data?.message ?? 'Assistant run failed',
          )
        }
        onEvent(decodeStreamPart(part))
      }
    })()

    return {
      done,
      get runId() {
        return runId
      },
      async cancel(action = 'interrupt') {
        try {
          if (runId) {
            await sdk.runs.cancel(threadId, runId, true, action)
          }
        } finally {
          controller.abort()
        }
      },
    }
  }

  return { manage, createThread, streamAssistant }
}


export function withAuthorization(headers) {
  const normalizedHeaders = new Headers(headers)
  const token = accessToken()
  if (token) {
    normalizedHeaders.set('Authorization', `Bearer ${token}`)
  }
  return normalizedHeaders
}


export function resolveApiUrl(value, origin = globalThis.location?.origin) {
  try {
    return new URL(value).toString().replace(/\/$/, '')
  } catch {
    if (!origin) return value
    return new URL(value, origin).toString().replace(/\/$/, '')
  }
}


function messageText(content) {
  if (typeof content === 'string') {
    return content
  }
  if (!Array.isArray(content)) {
    return ''
  }
  return content
    .filter((block) => block?.type === 'text')
    .map((block) => block.text ?? '')
    .join('')
}


export const langGraphApi = createLangGraphApi()
