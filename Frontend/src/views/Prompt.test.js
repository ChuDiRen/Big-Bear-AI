import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, test, vi } from 'vitest'

import Prompt from './Prompt.vue'


const push = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}))

const ResourceCatalogStub = {
  name: 'ResourceCatalogPage',
  props: ['resource', 'fields', 'useLabel'],
  emits: ['use'],
  template: '<button data-use @click="$emit(\'use\', { id: \'prompt-4\' })">use</button>',
}

describe('Prompt view', () => {
  beforeEach(() => push.mockReset())

  test('configures the live prompt catalogue and opens Home with prompt context', async () => {
    const wrapper = mount(Prompt, {
      global: { stubs: { ResourceCatalogPage: ResourceCatalogStub } },
    })
    const catalogue = wrapper.getComponent(ResourceCatalogStub)

    expect(catalogue.props('resource')).toBe('prompt')
    expect(catalogue.props('fields').map((field) => field.key)).toEqual([
      'title',
      'description',
      'template',
      'variables',
      'tags',
    ])
    expect(catalogue.props('useLabel')).toBe('在对话中使用')

    await wrapper.get('[data-use]').trigger('click')
    expect(push).toHaveBeenCalledWith({ name: 'Home', query: { prompt_id: 'prompt-4' } })
  })
})
