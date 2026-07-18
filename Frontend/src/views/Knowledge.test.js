import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, test, vi } from 'vitest'

import Knowledge from './Knowledge.vue'


function createService(overrides = {}) {
  return {
    list: vi.fn().mockResolvedValue({
      items: [{
        id: 'doc-1',
        title: '测试规范',
        description: '团队测试流程',
        filename: 'guide.txt',
        index_status: 'ready',
        read_only: false,
      }],
      total: 1,
    }),
    action: vi.fn().mockResolvedValue({ id: 'doc-2' }),
    remove: vi.fn().mockResolvedValue({ deleted: true }),
    ...overrides,
  }
}

function mountPage(service) {
  return mount(Knowledge, {
    props: { service },
    global: { stubs: { teleport: true } },
  })
}

describe('Knowledge view', () => {
  test('loads documents and uploads a selected file through management', async () => {
    const service = createService()
    const wrapper = mountPage(service)
    await flushPromises()

    expect(service.list).toHaveBeenCalledWith('document', { search: '', limit: 100 })
    expect(wrapper.text()).toContain('测试规范')

    await wrapper.get('[data-upload-document]').trigger('click')
    const input = wrapper.get('[data-document-file]')
    Object.defineProperty(input.element, 'files', {
      configurable: true,
      value: [new File(['hello'], 'guide.txt', { type: 'text/plain' })],
    })
    await input.trigger('change')
    await wrapper.get('[name="title"]').setValue('边界分析指南')
    await wrapper.get('[data-upload-form]').trigger('submit')

    await vi.waitFor(() => {
      expect(service.action).toHaveBeenCalledWith('document', null, 'upload', {
        filename: 'guide.txt',
        media_type: 'text/plain',
        content_base64: 'aGVsbG8=',
        title: '边界分析指南',
        description: '',
      })
    })
    await flushPromises()
    expect(service.list).toHaveBeenCalledTimes(2)
  })

  test('searches extracted document content and renders matching snippets', async () => {
    const service = createService({
      action: vi.fn().mockResolvedValue([{
        chunk_id: 'chunk-1',
        document_id: 'doc-1',
        title: '测试规范',
        content: '边界值包括刚好超出限制的值。',
      }]),
    })
    const wrapper = mountPage(service)
    await flushPromises()

    await wrapper.get('[data-knowledge-query]').setValue('边界值')
    await wrapper.get('[data-knowledge-search-form]').trigger('submit')
    await flushPromises()

    expect(service.action).toHaveBeenCalledWith('document', null, 'search', {
      query: '边界值',
      limit: 8,
    })
    expect(wrapper.text()).toContain('刚好超出限制')
  })

  test('requires confirmation before deleting a writable document', async () => {
    const service = createService()
    const wrapper = mountPage(service)
    await flushPromises()

    await wrapper.get('[data-document-card]').trigger('click')
    await wrapper.get('[data-delete-document]').trigger('click')
    expect(service.remove).not.toHaveBeenCalled()
    await wrapper.get('[data-confirm-delete-document]').trigger('click')
    await flushPromises()

    expect(service.remove).toHaveBeenCalledWith('document', 'doc-1')
  })
})
