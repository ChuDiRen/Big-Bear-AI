import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, test, vi } from 'vitest'

import ResourceCatalogPage from './ResourceCatalogPage.vue'


const fields = [
  { key: 'title', label: '名称', required: true },
  { key: 'description', label: '描述', type: 'textarea' },
  { key: 'definition', label: '规则定义', type: 'textarea', required: true },
  { key: 'tags', label: '标签', type: 'list' },
]

function createService(overrides = {}) {
  return {
    list: vi.fn().mockResolvedValue({
      items: [
        {
          id: 'rule-1',
          title: 'API checks',
          description: 'Validate contracts',
          definition: 'Check schemas',
          tags: ['API'],
          read_only: false,
        },
      ],
      total: 1,
    }),
    create: vi.fn().mockResolvedValue({ id: 'rule-2' }),
    update: vi.fn().mockResolvedValue({ id: 'rule-1' }),
    remove: vi.fn().mockResolvedValue({ deleted: true }),
    ...overrides,
  }
}

function mountPage(service) {
  return mount(ResourceCatalogPage, {
    props: {
      resource: 'rule',
      title: '规则市场',
      subtitle: '管理测试规则',
      actionLabel: '新建规则',
      searchPlaceholder: '搜索规则...',
      fields,
      service,
    },
    global: {
      stubs: {
        teleport: true,
      },
    },
  })
}

describe('ResourceCatalogPage', () => {
  test('loads catalogue items and opens a detail dialog', async () => {
    const service = createService()
    const wrapper = mountPage(service)
    await flushPromises()

    expect(service.list).toHaveBeenCalledWith('rule', { search: '', limit: 100 })
    expect(wrapper.text()).toContain('API checks')
    await wrapper.get('[data-resource-card]').trigger('click')
    expect(wrapper.get('[role="dialog"]').text()).toContain('Check schemas')
  })

  test('debounces search and reloads from the service', async () => {
    vi.useFakeTimers()
    const service = createService()
    const wrapper = mountPage(service)
    await flushPromises()

    await wrapper.get('[data-resource-search]').setValue('security')
    await vi.advanceTimersByTimeAsync(249)
    expect(service.list).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1)
    await flushPromises()
    expect(service.list).toHaveBeenLastCalledWith('rule', {
      search: 'security',
      limit: 100,
    })
    vi.useRealTimers()
  })

  test('creates a resource from the configured form fields', async () => {
    const service = createService()
    const wrapper = mountPage(service)
    await flushPromises()

    await wrapper.get('[data-create-resource]').trigger('click')
    await wrapper.get('[name="title"]').setValue('Security checks')
    await wrapper.get('[name="definition"]').setValue('Scan inputs')
    await wrapper.get('[name="tags"]').setValue('安全, API')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(service.create).toHaveBeenCalledWith('rule', {
      title: 'Security checks',
      description: '',
      definition: 'Scan inputs',
      tags: ['安全', 'API'],
    })
    expect(service.list).toHaveBeenCalledTimes(2)
  })

  test('requires explicit confirmation before deletion', async () => {
    const service = createService()
    const wrapper = mountPage(service)
    await flushPromises()
    await wrapper.get('[data-resource-card]').trigger('click')

    await wrapper.get('[data-delete-resource]').trigger('click')
    expect(service.remove).not.toHaveBeenCalled()
    await wrapper.get('[data-confirm-delete]').trigger('click')
    await flushPromises()
    expect(service.remove).toHaveBeenCalledWith('rule', 'rule-1')
  })

  test('hides mutation controls for read-only resources', async () => {
    const service = createService({
      list: vi.fn().mockResolvedValue({
        items: [{ id: 'official', title: 'Official', read_only: true }],
        total: 1,
      }),
    })
    const wrapper = mountPage(service)
    await flushPromises()
    await wrapper.get('[data-resource-card]').trigger('click')

    expect(wrapper.find('[data-edit-resource]').exists()).toBe(false)
    expect(wrapper.find('[data-delete-resource]').exists()).toBe(false)
  })

  test('renders an actionable error state', async () => {
    const service = createService({
      list: vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue({
        items: [],
        total: 0,
      }),
    })
    const wrapper = mountPage(service)
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('offline')
    await wrapper.get('[data-retry]').trigger('click')
    await flushPromises()
    expect(service.list).toHaveBeenCalledTimes(2)
  })

  test('loads the next cursor without replacing existing items', async () => {
    const service = createService({
      list: vi.fn()
        .mockResolvedValueOnce({
          items: [{ id: 'rule-1', title: 'First page', read_only: false }],
          total: 2,
          next_cursor: '1',
        })
        .mockResolvedValueOnce({
          items: [{ id: 'rule-2', title: 'Second page', read_only: false }],
          total: 2,
          next_cursor: null,
        }),
    })
    const wrapper = mountPage(service)
    await flushPromises()

    await wrapper.get('[data-load-more]').trigger('click')
    await flushPromises()

    expect(service.list).toHaveBeenNthCalledWith(2, 'rule', {
      search: '',
      limit: 100,
      cursor: '1',
    })
    expect(wrapper.text()).toContain('First page')
    expect(wrapper.text()).toContain('Second page')
    expect(wrapper.find('[data-load-more]').exists()).toBe(false)
  })
})
