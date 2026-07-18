import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, test, vi } from 'vitest'

import Rules from './Rules.vue'


const push = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}))

const ResourceCatalogStub = {
  name: 'ResourceCatalogPage',
  props: ['resource', 'fields', 'useLabel'],
  emits: ['use'],
  template: '<button data-use @click="$emit(\'use\', { id: \'rule-7\' })">use</button>',
}

describe('Rules view', () => {
  beforeEach(() => push.mockReset())

  test('configures the live rule catalogue and opens Home with rule context', async () => {
    const wrapper = mount(Rules, {
      global: { stubs: { ResourceCatalogPage: ResourceCatalogStub } },
    })
    const catalogue = wrapper.getComponent(ResourceCatalogStub)

    expect(catalogue.props('resource')).toBe('rule')
    expect(catalogue.props('fields').map((field) => field.key)).toEqual([
      'title',
      'description',
      'definition',
      'tags',
      'enabled',
    ])
    expect(catalogue.props('useLabel')).toBe('在对话中使用')

    await wrapper.get('[data-use]').trigger('click')
    expect(push).toHaveBeenCalledWith({ name: 'Home', query: { rule_id: 'rule-7' } })
  })
})
