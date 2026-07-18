import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, test, vi } from 'vitest'

import Home from './Home.vue'


const route = reactive({ query: {} })

vi.mock('vue-router', () => ({
  useRoute: () => route,
}))

function createStorage(initial = {}) {
  const values = new Map(Object.entries(initial))
  return {
    getItem: vi.fn((key) => values.get(key) ?? null),
    setItem: vi.fn((key, value) => values.set(key, String(value))),
    removeItem: vi.fn((key) => values.delete(key)),
  }
}

function createService(overrides = {}) {
  return {
    get: vi.fn().mockImplementation((resource, id) => Promise.resolve({
      id,
      name: resource === 'agent' ? 'API 专家' : undefined,
      title: resource === 'prompt' ? '接口测试模板' : '边界规则',
    })),
    list: vi.fn().mockImplementation((resource) => Promise.resolve({
      items: resource === 'project'
        ? [{ id: 'project-1', name: '结算系统', description: '支付与订单' }]
        : [{
            id: 'design-1',
            project_id: 'project-1',
            title: '结算回归设计',
            content: '覆盖支付成功与失败路径',
          }],
      total: 1,
    })),
    create: vi.fn().mockResolvedValue({ id: 'project-new', name: '移动端' }),
    ...overrides,
  }
}

function createGraphApi(events = [{ type: 'message', text: '先验证正常路径。' }]) {
  return {
    createThread: vi.fn().mockResolvedValue('thread-new'),
    streamAssistant: vi.fn(({ onEvent }) => {
      for (const event of events) onEvent(event)
      return { done: Promise.resolve(), cancel: vi.fn() }
    }),
  }
}

function mountHome({ graphApi = createGraphApi(), service = createService(), storage = createStorage() } = {}) {
  return mount(Home, {
    props: { graphApi, service, storage },
    global: { stubs: { teleport: true } },
  })
}

describe('Home view', () => {
  beforeEach(() => {
    route.query = {}
  })

  test('creates a thread, streams an answer, and forwards mode plus page context', async () => {
    route.query = {
      agent_id: 'agent-1',
      prompt_id: 'prompt-1',
      rule_id: 'rule-1',
    }
    const storage = createStorage()
    const service = createService()
    const graphApi = createGraphApi([
      { type: 'custom', data: { stage: '检索知识' } },
      { type: 'message', text: '先验证' },
      { type: 'message', text: '正常路径。' },
    ])
    const wrapper = mountHome({ graphApi, service, storage })
    await flushPromises()

    expect(wrapper.text()).toContain('API 专家')
    expect(wrapper.text()).toContain('接口测试模板')
    expect(wrapper.text()).toContain('边界规则')
    await wrapper.get('[data-mode="design"]').trigger('click')
    await wrapper.get('[data-chat-input]').setValue('设计结算接口测试')
    await wrapper.get('[data-chat-input]').trigger('keydown', { key: 'Enter' })
    await flushPromises()

    expect(graphApi.createThread).toHaveBeenCalledTimes(1)
    expect(storage.setItem).toHaveBeenCalledWith('big-bear-thread-id', 'thread-new')
    expect(graphApi.streamAssistant).toHaveBeenCalledWith(expect.objectContaining({
      threadId: 'thread-new',
      input: { messages: [{ role: 'user', content: '设计结算接口测试' }] },
      context: {
        mode: 'design',
        agent_id: 'agent-1',
        prompt_id: 'prompt-1',
        rule_id: 'rule-1',
      },
    }))
    expect(wrapper.text()).toContain('设计结算接口测试')
    expect(wrapper.text()).toContain('先验证正常路径。')
    expect(wrapper.text()).toContain('检索知识')
  })

  test('collects selected prompt variables and forwards them to assistant context', async () => {
    route.query = { prompt_id: 'prompt-variables' }
    const service = createService({
      get: vi.fn().mockResolvedValue({
        id: 'prompt-variables',
        title: '接口测试模板',
        variables: ['target', 'schema'],
      }),
    })
    const graphApi = createGraphApi()
    const wrapper = mountHome({ graphApi, service })
    await flushPromises()

    expect(wrapper.find('[data-prompt-variable="target"]').exists()).toBe(true)
    expect(wrapper.find('[data-prompt-variable="schema"]').exists()).toBe(true)
    await wrapper.get('[data-prompt-variable="target"]').setValue('checkout API')
    await wrapper.get('[data-prompt-variable="schema"]').setValue('OpenAPI contract')
    await wrapper.get('[data-chat-input]').setValue('生成测试')
    await wrapper.get('[data-send-message]').trigger('click')
    await flushPromises()

    expect(graphApi.streamAssistant).toHaveBeenCalledWith(expect.objectContaining({
      context: {
        mode: 'auto',
        prompt_id: 'prompt-variables',
        prompt_variables: {
          target: 'checkout API',
          schema: 'OpenAPI contract',
        },
      },
    }))
  })

  test('reuses a stored thread and starts a clean conversation on demand', async () => {
    const storage = createStorage({ 'big-bear-thread-id': 'thread-existing' })
    const graphApi = createGraphApi()
    const wrapper = mountHome({ graphApi, storage })

    await wrapper.get('[data-chat-input]').setValue('继续测试')
    await wrapper.get('[data-send-message]').trigger('click')
    await flushPromises()

    expect(graphApi.createThread).not.toHaveBeenCalled()
    expect(graphApi.streamAssistant).toHaveBeenCalledWith(expect.objectContaining({
      threadId: 'thread-existing',
    }))
    await wrapper.get('[data-new-conversation]').trigger('click')
    expect(storage.removeItem).toHaveBeenCalledWith('big-bear-thread-id')
    expect(wrapper.find('[data-chat-message]').exists()).toBe(false)
  })

  test('stops an active run through the server cancellation handle', async () => {
    let finish
    const cancel = vi.fn(() => {
      finish()
      return Promise.resolve()
    })
    const graphApi = {
      createThread: vi.fn().mockResolvedValue('thread-1'),
      streamAssistant: vi.fn(() => ({
        done: new Promise((resolve) => { finish = resolve }),
        cancel,
      })),
    }
    const wrapper = mountHome({ graphApi })

    await wrapper.get('[data-chat-input]').setValue('长时间任务')
    await wrapper.get('[data-send-message]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-stop-message]').trigger('click')
    await flushPromises()

    expect(cancel).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('已停止生成')
  })

  test('retains the user message on failure and retries without duplicating it', async () => {
    const graphApi = {
      createThread: vi.fn().mockResolvedValue('thread-1'),
      streamAssistant: vi.fn()
        .mockReturnValueOnce({ done: Promise.reject(new Error('model failed')), cancel: vi.fn() })
        .mockImplementationOnce(({ onEvent }) => {
          onEvent({ type: 'message', text: '重试成功' })
          return { done: Promise.resolve(), cancel: vi.fn() }
        }),
    }
    const wrapper = mountHome({ graphApi })

    await wrapper.get('[data-chat-input]').setValue('生成用例')
    await wrapper.get('[data-send-message]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('model failed')
    expect(wrapper.text().match(/生成用例/g)).toHaveLength(1)

    await wrapper.get('[data-retry-message]').trigger('click')
    await flushPromises()
    expect(graphApi.streamAssistant).toHaveBeenCalledTimes(2)
    expect(wrapper.text().match(/生成用例/g)).toHaveLength(1)
    expect(wrapper.text()).toContain('重试成功')
  })

  test('opens an existing design and creates a project for later assistant context', async () => {
    const service = createService()
    const wrapper = mountHome({ service })

    await wrapper.get('[data-open-design]').trigger('click')
    await flushPromises()
    expect(service.list).toHaveBeenCalledWith('project', { search: '', limit: 100 })
    expect(service.list).toHaveBeenCalledWith('design', { search: '', limit: 100 })
    await wrapper.get('[data-design="design-1"]').trigger('click')
    expect(wrapper.get('[data-chat-input]').element.value).toContain('结算回归设计')

    await wrapper.get('[data-new-project]').trigger('click')
    await wrapper.get('[name="project-name"]').setValue('移动端')
    await wrapper.get('[name="project-description"]').setValue('iOS 与 Android')
    await wrapper.get('[data-project-form]').trigger('submit')
    await flushPromises()
    expect(service.create).toHaveBeenCalledWith('project', {
      name: '移动端',
      description: 'iOS 与 Android',
      status: 'draft',
    })
    expect(wrapper.text()).toContain('移动端')
  })

  test('keeps Shift+Enter as a newline and sends the start-testing quick action', async () => {
    const graphApi = createGraphApi()
    const wrapper = mountHome({ graphApi })

    await wrapper.get('[data-chat-input]').setValue('第一行')
    await wrapper.get('[data-chat-input]').trigger('keydown', { key: 'Enter', shiftKey: true })
    expect(graphApi.streamAssistant).not.toHaveBeenCalled()

    await wrapper.get('[data-start-testing]').trigger('click')
    await flushPromises()
    expect(graphApi.streamAssistant).toHaveBeenCalledWith(expect.objectContaining({
      input: {
        messages: [{
          role: 'user',
          content: '请根据当前项目和已选上下文开始测试，并给出可执行的测试步骤。',
        }],
      },
    }))
  })
})
