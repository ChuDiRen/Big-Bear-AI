import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, test, vi } from 'vitest'

import Agents from './Agents.vue'


const push = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}))

const ResourceCatalogStub = {
  name: 'ResourceCatalogPage',
  props: ['resource', 'fields', 'useLabel'],
  emits: ['use'],
  template: '<button data-use @click="$emit(\'use\', { id: \'agent-2\' })">use</button>',
}

describe('Agents view', () => {
  beforeEach(() => push.mockReset())

  test('configures the live Agent catalogue and opens Home with Agent context', async () => {
    const wrapper = mount(Agents, {
      global: { stubs: { ResourceCatalogPage: ResourceCatalogStub } },
    })
    const catalogue = wrapper.getComponent(ResourceCatalogStub)

    expect(catalogue.props('resource')).toBe('agent')
    expect(catalogue.props('fields').map((field) => field.key)).toEqual([
      'name',
      'description',
      'instructions',
      'category',
      'model_override',
      'allowed_rule_ids',
      'allowed_plugin_ids',
      'allowed_document_ids',
    ])
    expect(catalogue.props('useLabel')).toBe('使用智能体')

    await wrapper.get('[data-use]').trigger('click')
    expect(push).toHaveBeenCalledWith({ name: 'Home', query: { agent_id: 'agent-2' } })
  })
})
