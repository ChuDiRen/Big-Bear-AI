import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, test, vi } from 'vitest'

import MCP from './MCP.vue'


function server(overrides = {}) {
  return {
    id: 'mcp-1',
    name: 'Local tools',
    description: 'Local MCP server',
    transport: 'stdio',
    configuration: { command: 'python', args: ['server.py'], env: {} },
    desired_state: 'disconnected',
    health_status: 'Disconnected',
    last_error: null,
    ...overrides,
  }
}

function createService(item = server(), overrides = {}) {
  return {
    list: vi.fn().mockResolvedValue({ items: [item], total: 1 }),
    create: vi.fn().mockResolvedValue(server({ id: 'mcp-2' })),
    update: vi.fn().mockResolvedValue(item),
    remove: vi.fn().mockResolvedValue({ deleted: true }),
    action: vi.fn().mockResolvedValue(server({ desired_state: 'connected', health_status: 'Connected' })),
    ...overrides,
  }
}

function mountPage(service) {
  return mount(MCP, {
    props: { service },
    global: { stubs: { teleport: true } },
  })
}

describe('MCP view', () => {
  test('debounces server search through the management list operation', async () => {
    vi.useFakeTimers()
    const service = createService()
    const wrapper = mountPage(service)
    await flushPromises()

    await wrapper.get('[data-mcp-search]').setValue('python')
    await vi.advanceTimersByTimeAsync(249)
    expect(service.list).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1)
    await flushPromises()
    expect(service.list).toHaveBeenLastCalledWith('mcp', { search: 'python', limit: 100 })
    vi.useRealTimers()
  })

  test('creates a stdio server with environment references', async () => {
    const service = createService()
    const wrapper = mountPage(service)
    await flushPromises()

    await wrapper.get('[data-add-mcp]').trigger('click')
    await wrapper.get('[name="name"]').setValue('Python tools')
    await wrapper.get('[name="command"]').setValue('python')
    await wrapper.get('[name="args"]').setValue('server.py\n--verbose')
    await wrapper.get('[name="environment"]').setValue('{"TOKEN":"$env:MCP_TOKEN"}')
    await wrapper.get('[data-mcp-form]').trigger('submit')
    await flushPromises()

    expect(service.create).toHaveBeenCalledWith('mcp', {
      name: 'Python tools',
      description: '',
      transport: 'stdio',
      configuration: {
        command: 'python',
        args: ['server.py', '--verbose'],
        env: { TOKEN: '$env:MCP_TOKEN' },
      },
    })
  })

  test('connects a configured server and discovers its tools', async () => {
    const service = createService(undefined, {
      action: vi.fn()
        .mockResolvedValueOnce(server({ desired_state: 'connected', health_status: 'Connected' }))
        .mockResolvedValueOnce([{ name: 'add', description: 'Add numbers', input_schema: {} }]),
    })
    const wrapper = mountPage(service)
    await flushPromises()

    await wrapper.get('[data-mcp-card]').trigger('click')
    await wrapper.get('[data-connect-mcp]').trigger('click')
    await flushPromises()

    expect(service.action).toHaveBeenNthCalledWith(1, 'mcp', 'mcp-1', 'connect')
    expect(service.action).toHaveBeenNthCalledWith(2, 'mcp', 'mcp-1', 'list_tools')
    expect(wrapper.text()).toContain('add')
  })

  test('keeps a failed server out of Connected state and surfaces the error', async () => {
    const service = createService(undefined, {
      action: vi.fn().mockRejectedValue(new Error('connection failed')),
    })
    const wrapper = mountPage(service)
    await flushPromises()

    await wrapper.get('[data-mcp-card]').trigger('click')
    await wrapper.get('[data-connect-mcp]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('connection failed')
    expect(wrapper.text()).not.toContain('Connected')
  })

  test('updates an HTTP server and requires confirmation before deletion', async () => {
    const item = server({
      transport: 'streamable_http',
      configuration: { url: 'http://localhost:9000/mcp', headers: {} },
    })
    const service = createService(item)
    const wrapper = mountPage(service)
    await flushPromises()

    await wrapper.get('[data-mcp-card]').trigger('click')
    await wrapper.get('[data-edit-mcp]').trigger('click')
    await wrapper.get('[name="description"]').setValue('Updated server')
    await wrapper.get('[name="url"]').setValue('https://tools.example.com/mcp')
    await wrapper.get('[data-mcp-form]').trigger('submit')
    await flushPromises()

    expect(service.update).toHaveBeenCalledWith('mcp', 'mcp-1', {
      name: 'Local tools',
      description: 'Updated server',
      transport: 'streamable_http',
      configuration: {
        url: 'https://tools.example.com/mcp',
        headers: {},
      },
    })

    await wrapper.get('[data-mcp-card]').trigger('click')
    await wrapper.get('[data-delete-mcp]').trigger('click')
    expect(service.remove).not.toHaveBeenCalled()
    await wrapper.get('[data-confirm-delete-mcp]').trigger('click')
    await flushPromises()
    expect(service.remove).toHaveBeenCalledWith('mcp', 'mcp-1')
  })

  test('calls a discovered tool and disconnects a connected server', async () => {
    const service = createService(server({
      desired_state: 'connected',
      health_status: 'Connected',
    }), {
      action: vi.fn()
        .mockResolvedValueOnce([{ name: 'add', description: 'Add numbers', input_schema: {} }])
        .mockResolvedValueOnce({ structured_content: { total: 5 }, content: [] })
        .mockResolvedValueOnce(server()),
    })
    const wrapper = mountPage(service)
    await flushPromises()

    await wrapper.get('[data-mcp-card]').trigger('click')
    await wrapper.get('[data-list-mcp-tools]').trigger('click')
    await flushPromises()
    await wrapper.get('[name="mcp-tool-arguments"]').setValue('{"a":2,"b":3}')
    await wrapper.get('[data-call-mcp-tool]').trigger('click')
    await flushPromises()
    expect(service.action).toHaveBeenNthCalledWith(2, 'mcp', 'mcp-1', 'call', {
      tool_name: 'add',
      arguments: { a: 2, b: 3 },
    })
    expect(wrapper.text()).toContain('"total": 5')

    await wrapper.get('[data-disconnect-mcp]').trigger('click')
    await flushPromises()
    expect(service.action).toHaveBeenNthCalledWith(3, 'mcp', 'mcp-1', 'disconnect')
  })
})
