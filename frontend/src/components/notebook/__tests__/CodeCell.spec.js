import { afterEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import CodeCell from '../CodeCell.vue'

const wrappers = []

function makeCell(overrides = {}) {
  return {
    id: 'c1',
    type: 'code',
    source: 'print(1)',
    order: 1,
    student_editable: true,
    outputs: null,
    ...overrides,
  }
}

function mountCell(props = {}) {
  const wrapper = mount(CodeCell, {
    props: { cell: makeCell(), ...props },
  })
  wrappers.push(wrapper)
  return wrapper
}

async function waitForCodeMirror(wrapper) {
  await flushPromises()
  await vi.waitFor(() => {
    expect(wrapper.find('.cm-content').exists()).toBe(true)
  })
}

afterEach(() => {
  for (const wrapper of wrappers.splice(0)) {
    wrapper.unmount()
  }
})

describe('CodeCell', () => {
  it('emits editable textarea changes with the cell id', async () => {
    const wrapper = mountCell()
    const textarea = wrapper.get('textarea')

    await textarea.setValue('print(2)')

    expect(wrapper.emitted('update:source')).toEqual([['c1', 'print(2)']])
  })

  it('keeps a readonly editor immutable but still allows running its source', async () => {
    const wrapper = mountCell({
      cell: makeCell({ student_editable: false }),
      readonly: true,
    })
    const textarea = wrapper.get('textarea')

    expect(textarea.attributes('readonly')).toBeDefined()
    expect(textarea.attributes('disabled')).toBeUndefined()
    await textarea.setValue('hacked()')
    expect(wrapper.emitted('update:source')).toBeUndefined()

    await wrapper.get('.btn-run').trigger('click')
    expect(wrapper.emitted('execute')).toEqual([['c1']])
  })

  it('makes the loaded CodeMirror content non-editable for readonly cells', async () => {
    const wrapper = mountCell({ readonly: true })

    await waitForCodeMirror(wrapper)

    expect(wrapper.get('.cm-content').attributes('contenteditable')).toBe('false')
  })

  it('syncs an external source update into CodeMirror without emitting a student edit', async () => {
    const wrapper = mountCell()
    await waitForCodeMirror(wrapper)

    await wrapper.setProps({ cell: makeCell({ source: 'print(99)' }) })
    await flushPromises()

    expect(wrapper.get('.cm-content').text()).toContain('print(99)')
    expect(wrapper.emitted('update:source')).toBeUndefined()
  })

  it.each([
    [{ disabled: true }, 'disabled'],
    [{ isExecuting: true }, 'executing'],
  ])('blocks execution while $1', async (state) => {
    const wrapper = mountCell(state)

    await wrapper.get('.btn-run').trigger('click')

    expect(wrapper.emitted('execute')).toBeUndefined()
  })
})
