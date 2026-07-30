import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { useReveal } from '../useReveal.js'

let origIO

beforeEach(() => {
  origIO = globalThis.IntersectionObserver
})

afterEach(() => {
  globalThis.IntersectionObserver = origIO
})

function mountReveal(options = {}) {
  let result
  const TestComp = defineComponent({
    setup() {
      result = useReveal(options)
      return () => h('div', { ref: result.elRef }, 'test')
    },
  })
  const wrapper = mount(TestComp)
  return { wrapper, ...result }
}

describe('useReveal', () => {
  it('falls back to always visible when IntersectionObserver is unavailable', async () => {
    // @ts-ignore
    delete globalThis.IntersectionObserver
    const { isVisible } = mountReveal()
    expect(isVisible.value).toBe(true)
  })

  it('stays false when IntersectionObserver available but not intersecting', async () => {
    globalThis.IntersectionObserver = function MockIO() {
      this.observe = vi.fn()
      this.unobserve = vi.fn()
      this.disconnect = vi.fn()
    }
    const { isVisible } = mountReveal()
    expect(isVisible.value).toBe(false)
  })

  it('sets isVisible when element intersects', async () => {
    let cb
    globalThis.IntersectionObserver = function MockIO(callback) {
      cb = callback
      this.observe = vi.fn()
      this.unobserve = vi.fn()
      this.disconnect = vi.fn()
    }
    const { isVisible } = mountReveal()
    // Simulate intersection
    if (cb) {
      cb([{ isIntersecting: true }])
    }
    await vi.waitFor(() => expect(isVisible.value).toBe(true), { timeout: 100 })
  })

  it('returns elRef', async () => {
    globalThis.IntersectionObserver = function MockIO() {
      this.observe = vi.fn()
      this.unobserve = vi.fn()
      this.disconnect = vi.fn()
    }
    const { elRef } = mountReveal()
    expect(elRef.value).toBeInstanceOf(HTMLElement)
  })
})
