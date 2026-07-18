import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, test, vi } from 'vitest'

import Plugins from './Plugins.vue'


function plugin(overrides = {}) {
  return {
    id: 'api-validator',
    name: 'API Validator',
    description: 'Validate JSON payloads against a JSON Schema contract.',
    category: 'Validation',
    icon: 'shield-check',
    installed: false,
    enabled: false,
    configuration: {},
    config_schema: {},
    ...overrides,
  }
}

function createService(item = plugin(), overrides = {}) {
  return {
    list: vi.fn().mockResolvedValue({ items: [item], total: 1 }),
    action: vi.fn().mockResolvedValue(item),
    ...overrides,
  }
}

function mountPage(service) {
  return mount(Plugins, {
    props: { service },
    global: { stubs: { teleport: true } },
  })
}

describe('Plugins view', () => {
  test('installs a catalogue plugin with validated JSON configuration', async () => {
    const service = createService()
    const wrapper = mountPage(service)
    await flushPromises()

    await wrapper.get('[data-plugin-card]').trigger('click')
    await wrapper.get('[name="plugin-configuration"]').setValue('{"timeout_ms":3000}')
    await wrapper.get('[data-install-plugin]').trigger('click')
    await flushPromises()

    expect(service.action).toHaveBeenCalledWith('plugin', null, 'install', {
      plugin_id: 'api-validator',
      configuration: { timeout_ms: 3000 },
    })
  })

  test('disables and uninstalls an installed plugin', async () => {
    const service = createService(plugin({ installed: true, enabled: true }))
    const wrapper = mountPage(service)
    await flushPromises()

    await wrapper.get('[data-plugin-card]').trigger('click')
    await wrapper.get('[data-disable-plugin]').trigger('click')
    await flushPromises()
    expect(service.action).toHaveBeenCalledWith('plugin', null, 'disable', {
      plugin_id: 'api-validator',
    })

    await wrapper.get('[data-uninstall-plugin]').trigger('click')
    expect(service.action).toHaveBeenCalledTimes(1)
    await wrapper.get('[data-confirm-uninstall-plugin]').trigger('click')
    await flushPromises()
    expect(service.action).toHaveBeenLastCalledWith('plugin', null, 'uninstall', {
      plugin_id: 'api-validator',
    })
  })

  test('rejects malformed configuration JSON before calling management', async () => {
    const service = createService()
    const wrapper = mountPage(service)
    await flushPromises()

    await wrapper.get('[data-plugin-card]').trigger('click')
    await wrapper.get('[name="plugin-configuration"]').setValue('{broken')
    await wrapper.get('[data-install-plugin]').trigger('click')

    expect(service.action).not.toHaveBeenCalled()
    expect(wrapper.get('[role="alert"]').text()).toContain('JSON')
  })

  test('enables a disabled plugin', async () => {
    const service = createService(plugin({ installed: true, enabled: false }))
    const wrapper = mountPage(service)
    await flushPromises()

    await wrapper.get('[data-plugin-card]').trigger('click')
    await wrapper.get('[data-enable-plugin]').trigger('click')
    await flushPromises()

    expect(service.action).toHaveBeenCalledWith('plugin', null, 'enable', {
      plugin_id: 'api-validator',
    })
  })

  test('configures and calls an enabled plugin with JSON input', async () => {
    const service = createService(plugin({ installed: true, enabled: true }), {
      action: vi.fn()
        .mockResolvedValueOnce(plugin({ installed: true, enabled: true }))
        .mockResolvedValueOnce({ valid: true, errors: [] }),
    })
    const wrapper = mountPage(service)
    await flushPromises()

    await wrapper.get('[data-plugin-card]').trigger('click')
    await wrapper.get('[name="plugin-configuration"]').setValue('{"timeout_ms":3000}')
    await wrapper.get('[data-configure-plugin]').trigger('click')
    await flushPromises()
    expect(service.action).toHaveBeenNthCalledWith(1, 'plugin', null, 'configure', {
      plugin_id: 'api-validator',
      configuration: { timeout_ms: 3000 },
    })

    await wrapper.get('[name="plugin-input"]').setValue('{"instance":{"id":1},"schema":{"type":"object"}}')
    await wrapper.get('[data-call-plugin]').trigger('click')
    await flushPromises()
    expect(service.action).toHaveBeenNthCalledWith(2, 'plugin', null, 'call', {
      plugin_id: 'api-validator',
      input: { instance: { id: 1 }, schema: { type: 'object' } },
    })
    expect(wrapper.text()).toContain('"valid": true')
  })
})
