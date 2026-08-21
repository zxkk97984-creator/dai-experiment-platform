import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

vi.mock('../../../../api/environments.js', () => ({
  environmentsAPI: {
    getEditorOptions: vi.fn(),
    getBuildReadiness: vi.fn(),
    getProfile: vi.fn(),
    createProfile: vi.fn(),
    saveDraft: vi.fn(),
    buildDraft: vi.fn(),
    publish: vi.fn(),
    retryBuild: vi.fn(),
    updateProfile: vi.fn(),
  },
}))

vi.mock('../../../../stores/app.js', () => ({
  useAppStore: () => ({ showToast: vi.fn() }),
}))

import { environmentsAPI } from '../../../../api/environments.js'
import EnvironmentEditorPanel from '../EnvironmentEditorPanel.vue'

const profile = {
  id: 1,
  slug: 'data',
  display_name: '数据分析环境',
  description: '分析作业',
  status: 'active',
  current_version: null,
  draft: {
    profile_id: 1,
    revision: 1,
    state: 'editing',
    python_version: '3.12',
    minimum_memory_mb: 256,
    requested_spec: { schema_version: 1, python_packages: [], system_packages: [] },
    capabilities: {
      can_edit_draft: true,
      can_build: false,
      can_publish: false,
      can_retry: false,
      can_abandon_draft: true,
      can_rollback: false,
    },
  },
  versions: [],
  capabilities: { can_edit_draft: true },
}

const detail = JSON.parse(JSON.stringify(profile))

beforeEach(() => {
  vi.resetAllMocks()
  environmentsAPI.getEditorOptions.mockResolvedValue({
    data: {
      python_versions: ['3.10', '3.11', '3.12'],
      default_python_version: '3.12',
      default_memory_mb: 256,
    },
  })
  environmentsAPI.getBuildReadiness.mockResolvedValue({ data: { ready: true, checks: {} } })
  environmentsAPI.getProfile.mockResolvedValue({ data: JSON.parse(JSON.stringify(detail)) })
  environmentsAPI.createProfile.mockResolvedValue({ data: { id: 2 } })
  environmentsAPI.saveDraft.mockResolvedValue({
    data: { ...JSON.parse(JSON.stringify(detail.draft)), revision: 2 },
  })
})

async function mountEditor() {
  const wrapper = mount(EnvironmentEditorPanel, { props: { profiles: [profile] } })
  await flushPromises()
  return wrapper
}

describe('EnvironmentEditorPanel', () => {
  it('opens the new environment form in a dialog while keeping the original fields', async () => {
    const wrapper = await mountEditor()
    const openButton = wrapper.find('.v2-toolbar button')

    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    await openButton.trigger('click')

    const dialog = wrapper.find('[role="dialog"]')
    expect(dialog.exists()).toBe(true)
    expect(dialog.attributes('aria-labelledby')).toBe('create-env-title')
    expect(dialog.find('h2#create-env-title').text()).toBe('新建环境')
    expect(dialog.find('#v2-display-name').exists()).toBe(true)
    expect(dialog.find('#v2-description').exists()).toBe(true)
    expect(dialog.text()).toContain('创建并编辑')
    expect(wrapper.find('.create-card').exists()).toBe(false)

    await dialog.find('button[aria-label="关闭"]').trigger('click')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })

  it('submits the original fields from the dialog and closes after creation', async () => {
    const wrapper = await mountEditor()
    await wrapper.find('.v2-toolbar button').trigger('click')
    const dialog = wrapper.find('[role="dialog"]')

    await dialog.find('#v2-display-name').setValue('  新建数据环境  ')
    await dialog.find('#v2-description').setValue('  用于数据分析作业  ')
    await dialog.trigger('submit')
    await flushPromises()

    expect(environmentsAPI.createProfile).toHaveBeenCalledWith({
      display_name: '新建数据环境',
      description: '用于数据分析作业',
      slug: null,
    })
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })

  it('keeps the dialog open and shows the duplicate-name error inside it', async () => {
    environmentsAPI.createProfile.mockRejectedValue({
      response: {
        data: {
          detail: {
            code: 'PROFILE_DISPLAY_NAME_CONFLICT',
            message: '环境名称已存在，请使用其他名称',
          },
        },
      },
    })
    const wrapper = await mountEditor()
    await wrapper.find('.v2-toolbar button').trigger('click')
    const dialog = wrapper.find('[role="dialog"]')
    await dialog.find('#v2-display-name').setValue('重复环境')
    await dialog.trigger('submit')
    await flushPromises()

    expect(dialog.exists()).toBe(true)
    expect(dialog.find('[role="alert"]').text()).toContain('环境名称已存在，请使用其他名称')
  })

  it('loads a draft, adds a package, and saves with its revision', async () => {
    const wrapper = await mountEditor()
    expect(wrapper.text()).toContain('数据分析环境')
    const inputs = wrapper.findAll('input')
    const packageInput = inputs.find((input) => input.attributes('id') === 'v2-python-name')
    await packageInput.setValue('numpy')
    await wrapper.find('.add-row .btn-ghost').trigger('click')
    expect(wrapper.text()).toContain('numpy')
    const saveButton = wrapper.findAll('button.btn-primary').find((button) => button.text() === '保存草稿')
    await saveButton.trigger('click')
    expect(environmentsAPI.saveDraft).toHaveBeenCalledWith(1, expect.objectContaining({
      revision: 1,
      requested_spec: expect.objectContaining({
        python_packages: [{ name: 'numpy', version: null, import_names: [] }],
      }),
    }))
  })

  it('keeps build disabled while local changes are dirty', async () => {
    const wrapper = await mountEditor()
    const packageInput = wrapper.find('#v2-python-name')
    await packageInput.setValue('pandas')
    await wrapper.find('.add-row .btn-ghost').trigger('click')
    const buildButton = wrapper.findAll('button').find((button) => button.text() === '构建并解析')
    expect(buildButton.attributes('disabled')).toBeDefined()
  })

  it('keeps build disabled when the backend worker heartbeat is missing', async () => {
    environmentsAPI.getBuildReadiness.mockResolvedValue({
      data: { ready: false, checks: { worker: { status: 'unavailable', message: 'Worker 未就绪' } } },
    })
    environmentsAPI.getProfile.mockResolvedValue({
      data: {
        ...JSON.parse(JSON.stringify(detail)),
        draft: {
          ...JSON.parse(JSON.stringify(detail.draft)),
          capabilities: { ...detail.draft.capabilities, can_build: true },
        },
      },
    })
    const wrapper = await mountEditor()
    const buildButton = wrapper.findAll('button').find((button) => button.text() === '构建并解析')
    expect(buildButton.attributes('disabled')).toBeDefined()
  })

  it('shows the structured error code for a failed build', async () => {
    environmentsAPI.getProfile.mockResolvedValue({
      data: {
        ...JSON.parse(JSON.stringify(detail)),
        draft: {
          ...JSON.parse(JSON.stringify(detail.draft)),
          candidate_version_id: 2,
          state: 'failed',
        },
        versions: [{ id: 2, version_number: 2, status: 'failed', python_version: '3.12' }],
        recent_build: {
          id: 9,
          environment_version_id: 2,
          status: 'failed',
          phase: 'done',
          attempt_number: 1,
          error_code: 'PIP_PACKAGE_NOT_FOUND',
          error_detail: { stderr: 'No matching distribution found' },
          capabilities: { can_retry: false },
        },
      },
    })
    const wrapper = await mountEditor()
    expect(wrapper.text()).toContain('错误码：PIP_PACKAGE_NOT_FOUND')
  })
})
