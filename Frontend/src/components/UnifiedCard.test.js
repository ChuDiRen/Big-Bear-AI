import { mount } from '@vue/test-utils'
import { describe, expect, test } from 'vitest'

import UnifiedCard from './UnifiedCard.vue'


describe('UnifiedCard', () => {
  const item = {
    id: '1',
    name: 'API specialist',
    description: 'Designs negative API tests',
    author: '官方',
    updated_at: '2026-07-17T00:00:00Z',
    icon: 'robot',
  }

  test('renders backend field names and emits selection from a real button', async () => {
    const wrapper = mount(UnifiedCard, { props: { item } })

    expect(wrapper.get('button').attributes('type')).toBe('button')
    expect(wrapper.text()).toContain('API specialist')
    expect(wrapper.text()).toContain('Designs negative API tests')
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('select')).toEqual([[item]])
  })

  test('uses an allowlisted icon and falls back for untrusted values', () => {
    const safe = mount(UnifiedCard, { props: { item } })
    const unsafe = mount(UnifiedCard, {
      props: { item: { ...item, icon: 'robot\" onclick=\"alert(1)' } },
    })

    expect(safe.get('[data-card-icon]').classes()).toContain('ph-robot')
    expect(unsafe.get('[data-card-icon]').classes()).toContain('ph-star')
    expect(unsafe.html()).not.toContain('onclick')
  })

  test('renders status without requiring legacy option field names', () => {
    const wrapper = mount(UnifiedCard, {
      props: { item: { ...item, health_status: 'Connected' } },
    })
    expect(wrapper.text()).toContain('Connected')
  })
})
