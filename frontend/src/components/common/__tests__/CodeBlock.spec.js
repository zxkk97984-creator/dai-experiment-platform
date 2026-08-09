import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import CodeBlock from '../CodeBlock.vue'

const wrappers = []

function mountBlock(props = {}) {
  const wrapper = mount(CodeBlock, {
    props: { code: 'print(1)', language: 'python', filename: 'main.py', ...props },
  })
  wrappers.push(wrapper)
  return wrapper
}

afterEach(() => {
  for (const wrapper of wrappers.splice(0)) {
    wrapper.unmount()
  }
})

describe('CodeBlock', () => {
  it('renders code, line numbers, filename and language label', () => {
    const wrapper = mountBlock({ code: 'print(1)\nprint(2)' })

    expect(wrapper.get('.cb-code').text()).toBe('print(1)\nprint(2)')
    expect(wrapper.findAll('.cb-ln')).toHaveLength(2)
    expect(wrapper.get('.cb-filename').text()).toBe('main.py')
    expect(wrapper.get('.cb-lang').text()).toBe('Python 3.11')
  })

  it('maps unknown languages to an uppercase label', () => {
    const wrapper = mountBlock({ language: 'rust' })
    expect(wrapper.get('.cb-lang').text()).toBe('RUST')
  })

  it('declares the light theme marker', () => {
    const wrapper = mountBlock()
    expect(wrapper.attributes('data-code-theme')).toBe('light')
  })

  it('copies code via the clipboard API', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })
    const wrapper = mountBlock({ code: 'x = 1' })

    await wrapper.get('.cb-copy').trigger('click')

    expect(writeText).toHaveBeenCalledWith('x = 1')
    expect(wrapper.get('.cb-copy').text()).toContain('已复制')
  })

  it('falls back to execCommand when the clipboard API is unavailable', async () => {
    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
    // jsdom 未实现 execCommand，先补一个记录用的实现
    const exec = vi.fn(() => true)
    Object.defineProperty(document, 'execCommand', { value: exec, configurable: true, writable: true })
    const wrapper = mountBlock({ code: 'y = 2' })

    await wrapper.get('.cb-copy').trigger('click')

    expect(exec).toHaveBeenCalledWith('copy')
  })
})
