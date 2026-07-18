import { describe, expect, test, vi } from 'vitest'


async function loadApi() {
  return import('./resources.js')
}


describe('resource API', () => {
  test('maps list and CRUD calls to management graph inputs', async () => {
    const { createResourceApi } = await loadApi()
    const manage = vi.fn().mockResolvedValue({ id: '1' })
    const api = createResourceApi({ manage })

    await api.list('rule', { search: 'api', limit: 20 })
    await api.get('rule', '1')
    await api.create('rule', { title: 'Rule' })
    await api.update('rule', '1', { title: 'Updated' })
    await api.remove('rule', '1')

    expect(manage.mock.calls.map(([input]) => input)).toEqual([
      { operation: 'list', resource: 'rule', query: { search: 'api', limit: 20 } },
      { operation: 'get', resource: 'rule', resource_id: '1' },
      { operation: 'create', resource: 'rule', payload: { title: 'Rule' } },
      { operation: 'update', resource: 'rule', resource_id: '1', payload: { title: 'Updated' } },
      { operation: 'delete', resource: 'rule', resource_id: '1' },
    ])
  })

  test('maps named actions and omits empty resource ids', async () => {
    const { createResourceApi } = await loadApi()
    const manage = vi.fn().mockResolvedValue({ ok: true })
    const api = createResourceApi({ manage })

    await api.action('plugin', null, 'install', { plugin_id: 'api-validator' })
    await api.action('mcp', 'server-1', 'connect')

    expect(manage).toHaveBeenNthCalledWith(1, {
      operation: 'action',
      resource: 'plugin',
      payload: { action: 'install', plugin_id: 'api-validator' },
    }, {})
    expect(manage).toHaveBeenNthCalledWith(2, {
      operation: 'action',
      resource: 'mcp',
      resource_id: 'server-1',
      payload: { action: 'connect' },
    }, {})
  })
})
