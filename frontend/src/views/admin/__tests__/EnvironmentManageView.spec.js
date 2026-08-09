/** 环境档位管理页测试（Phase 2）：
 * 三 tab（环境档位/构建任务/库清单）交互、构建轮询与卸载停止、
 * 日志 <pre> 纯文本渲染、失败重试、库清单表单无 Dockerfile/requirements 输入。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../../../api/environments', () => ({
  environmentsAPI: {
    listPackages: vi.fn(),
    createPackage: vi.fn(),
    updatePackage: vi.fn(),
    deactivatePackage: vi.fn(),
    listProfiles: vi.fn(),
    createProfile: vi.fn(),
    updateProfile: vi.fn(),
    listVersions: vi.fn(),
    createVersion: vi.fn(),
    createBuild: vi.fn(),
    listBuilds: vi.fn(),
    getBuild: vi.fn(),
    getBuildLog: vi.fn(),
    retryBuild: vi.fn(),
    listAvailable: vi.fn(),
  },
}))

vi.mock('../../../stores/app', () => ({
  useAppStore: () => ({ showToast: vi.fn() }),
}))

import { environmentsAPI } from '../../../api/environments.js'
import EnvironmentManageView from '../EnvironmentManageView.vue'

const profileData = [
  {
    id: 1, slug: 'basic', display_name: 'Python 基础', description: '基础',
    status: 'active', created_at: '2026-01-01T00:00:00',
    latest_version: {
      id: 10, profile_id: 1, version_number: 1, status: 'available',
      base_image_ref: 'python:3.12-slim', image_tag: null, image_digest: null,
      python_version: '3.12', minimum_memory_mb: 256,
      manifest_sha256: 'm'.repeat(64), dockerfile_sha256: null,
      resolved_packages: null, available_at: null, created_at: '2026-01-01T00:00:00',
    },
  },
]

const versionData = [
  { ...profileData[0].latest_version },
  {
    id: 11, profile_id: 1, version_number: 2, status: 'draft',
    base_image_ref: 'python:3.12-slim', image_tag: null, image_digest: null,
    python_version: null, minimum_memory_mb: 768,
    manifest_sha256: 'n'.repeat(64), dockerfile_sha256: null,
    resolved_packages: null, available_at: null, created_at: '2026-01-02T00:00:00',
  },
]

const buildData = [
  {
    id: 100, environment_version_id: 10, status: 'succeeded', attempt_number: 1,
    retry_of_id: null, worker_id: 'w1', error_code: null, error_message: null,
    started_at: '2026-01-01T00:00:00', finished_at: '2026-01-01T00:01:00',
    created_at: '2026-01-01T00:00:00',
  },
  {
    id: 101, environment_version_id: 11, status: 'failed', attempt_number: 1,
    retry_of_id: null, worker_id: 'w1', error_code: 'BUILD_FAILED',
    error_message: '构建失败（exit=1）', started_at: '2026-01-02T00:00:00',
    finished_at: '2026-01-02T00:00:05', created_at: '2026-01-02T00:00:00',
  },
]

const packageData = [
  {
    id: 1, normalized_name: 'numpy', pip_name: 'numpy', locked_version: '2.1.3',
    import_names: ['numpy'], category_tags: ['data'], source_key: 'pypi',
    status: 'active', supersedes_id: null, referenced: true,
    created_at: '2026-01-01T00:00:00', updated_at: '2026-01-01T00:00:00',
  },
  {
    id: 2, normalized_name: 'torch', pip_name: 'torch', locked_version: '2.6.0+cpu',
    import_names: ['torch'], category_tags: ['machine-learning'], source_key: 'pytorch_cpu',
    status: 'active', supersedes_id: null, referenced: false,
    created_at: '2026-01-01T00:00:00', updated_at: '2026-01-01T00:00:00',
  },
]

function mockAll() {
  environmentsAPI.listProfiles.mockResolvedValue({ data: profileData })
  environmentsAPI.listVersions.mockResolvedValue({ data: versionData })
  environmentsAPI.listBuilds.mockResolvedValue({ data: buildData })
  environmentsAPI.listPackages.mockResolvedValue({ data: packageData })
  environmentsAPI.getBuildLog.mockResolvedValue({
    data: { job_id: 101, status: 'failed', log_text: 'STEP 1\n<secret> 输出' },
  })
}

async function mountPage() {
  const wrapper = mount(EnvironmentManageView, {
    global: {
      stubs: {
        transition: false,
        teleport: true,
        AppLayout: { template: '<div><slot /></div>' },
      },
    },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.resetAllMocks()
  mockAll()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('EnvironmentManageView 三 tab 结构', () => {
  it('默认显示环境档位 tab 并加载档位列表', async () => {
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('环境档位')
    expect(wrapper.text()).toContain('构建任务')
    expect(wrapper.text()).toContain('库清单')
    expect(environmentsAPI.listProfiles).toHaveBeenCalled()
    expect(wrapper.text()).toContain('Python 基础')
    expect(wrapper.text()).toContain('basic')
  })

  it('切换到构建任务 tab 并展示任务列表', async () => {
    const wrapper = await mountPage()
    const tabs = wrapper.findAll('.tab-btn')
    const buildTab = tabs.find((t) => t.text().includes('构建任务'))
    await buildTab.trigger('click')
    expect(environmentsAPI.listBuilds).toHaveBeenCalled()
    expect(wrapper.text()).toContain('成功')
    expect(wrapper.text()).toContain('失败')
  })

  it('切换到库清单 tab 并展示包列表', async () => {
    const wrapper = await mountPage()
    const tabs = wrapper.findAll('.tab-btn')
    const pkgTab = tabs.find((t) => t.text().includes('库清单'))
    await pkgTab.trigger('click')
    expect(environmentsAPI.listPackages).toHaveBeenCalled()
    expect(wrapper.text()).toContain('numpy')
    expect(wrapper.text()).toContain('2.1.3')
  })
})

describe('EnvironmentManageView 构建任务交互', () => {
  it('queued/building 任务每 2 秒轮询，组件卸载后停止', async () => {
    vi.useFakeTimers()
    environmentsAPI.listBuilds.mockResolvedValue({
      data: [{ ...buildData[1], status: 'queued' }],
    })
    const wrapper = await mountPage()
    const buildTab = wrapper.findAll('.tab-btn').find((t) => t.text().includes('构建任务'))
    await buildTab.trigger('click')
    const initialCalls = environmentsAPI.listBuilds.mock.calls.length
    await vi.advanceTimersByTimeAsync(2100)
    expect(environmentsAPI.listBuilds.mock.calls.length).toBeGreaterThan(initialCalls)
    const afterPoll = environmentsAPI.listBuilds.mock.calls.length
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(4200)
    expect(environmentsAPI.listBuilds.mock.calls.length).toBe(afterPoll)
  })

  it('日志以 <pre> 纯文本渲染（禁止 v-html）', async () => {
    const wrapper = await mountPage()
    const buildTab = wrapper.findAll('.tab-btn').find((t) => t.text().includes('构建任务'))
    await buildTab.trigger('click')
    const logButtons = wrapper.findAll('.log-btn')
    expect(logButtons.length).toBeGreaterThan(0)
    await logButtons[1].trigger('click')  // 第二个任务（failed，有日志）
    expect(environmentsAPI.getBuildLog).toHaveBeenCalledWith(101)
    const pre = wrapper.find('pre.log-text')
    expect(pre.exists()).toBe(true)
    expect(pre.text()).toContain('STEP 1')
    // 注入的 HTML 被转义为纯文本，不执行
    expect(pre.html()).toContain('&lt;secret&gt;')
  })

  it('failed/timed_out 任务显示重试按钮并调用 retryBuild', async () => {
    const wrapper = await mountPage()
    const buildTab = wrapper.findAll('.tab-btn').find((t) => t.text().includes('构建任务'))
    await buildTab.trigger('click')
    const retryBtn = wrapper.findAll('.retry-btn').find((b) => b.text().includes('重试'))
    expect(retryBtn).toBeTruthy()
    await retryBtn.trigger('click')
    expect(environmentsAPI.retryBuild).toHaveBeenCalledWith(101)
  })

  it('succeeded 任务显示短 digest 且不显示重试', async () => {
    environmentsAPI.listBuilds.mockResolvedValue({
      data: [{ ...buildData[0], status: 'succeeded' }],
    })
    const wrapper = await mountPage()
    const buildTab = wrapper.findAll('.tab-btn').find((t) => t.text().includes('构建任务'))
    await buildTab.trigger('click')
    expect(wrapper.findAll('.retry-btn').length).toBe(0)
  })
})

describe('EnvironmentManageView 库清单交互', () => {
  it('新建包表单只有元数据字段，无 Dockerfile/requirements 输入', async () => {
    const wrapper = await mountPage()
    const pkgTab = wrapper.findAll('.tab-btn').find((t) => t.text().includes('库清单'))
    await pkgTab.trigger('click')
    await wrapper.find('.create-pkg-btn').trigger('click')
    const formText = wrapper.find('.pkg-form').text()
    for (const label of ['包名', '版本', 'import 名', '分类', '来源']) {
      expect(formText).toContain(label)
    }
    expect(formText).not.toContain('Dockerfile')
    expect(formText).not.toContain('requirements')
    expect(formText).not.toContain('pip 参数')
  })

  it('提交新建包调用 createPackage', async () => {
    environmentsAPI.createPackage.mockResolvedValue({ data: { id: 9 } })
    const wrapper = await mountPage()
    const pkgTab = wrapper.findAll('.tab-btn').find((t) => t.text().includes('库清单'))
    await pkgTab.trigger('click')
    await wrapper.find('.create-pkg-btn').trigger('click')
    const form = wrapper.find('.pkg-form')
    await form.find('input[name="pip_name"]').setValue('scipy')
    await form.find('input[name="locked_version"]').setValue('1.14.1')
    await form.find('input[name="import_names"]').setValue('scipy')
    await wrapper.find('.pkg-form .submit-btn').trigger('click')
    expect(environmentsAPI.createPackage).toHaveBeenCalledWith(expect.objectContaining({
      pip_name: 'scipy',
      locked_version: '1.14.1',
      import_names: ['scipy'],
    }))
  })

  it('编辑被引用包时提示将创建新目录版本', async () => {
    const wrapper = await mountPage()
    const pkgTab = wrapper.findAll('.tab-btn').find((t) => t.text().includes('库清单'))
    await pkgTab.trigger('click')
    await wrapper.find('.edit-pkg-btn').trigger('click')
    expect(wrapper.text()).toContain('将创建新目录版本')
    expect(wrapper.text()).toContain('历史环境不变')
  })

  it('删除按钮执行停用（deactivatePackage）', async () => {
    const wrapper = await mountPage()
    const pkgTab = wrapper.findAll('.tab-btn').find((t) => t.text().includes('库清单'))
    await pkgTab.trigger('click')
    await wrapper.findAll('.deactivate-btn')[1].trigger('click')  // torch 未被引用
    expect(environmentsAPI.deactivatePackage).toHaveBeenCalledWith(2)
  })
})

describe('EnvironmentManageView 环境档位交互', () => {
  it('新版本从旧版本复制（source_version_id + 预选包）', async () => {
    const wrapper = await mountPage()
    await wrapper.find('.new-version-btn').trigger('click')
    await flushPromises()
    expect(environmentsAPI.listVersions).toHaveBeenCalledWith(1)
    expect(wrapper.text()).toContain('从 v1 复制')
  })

  it('draft 版本显示构建按钮并触发 createBuild', async () => {
    const environmentsAPI2 = environmentsAPI
    environmentsAPI2.createBuild.mockResolvedValue({ data: { id: 200, status: 'queued' } })
    const wrapper = await mountPage()
    await wrapper.find('.new-version-btn').trigger('click')
    await flushPromises()
    const buildBtns = wrapper.findAll('.build-btn')
    expect(buildBtns.length).toBeGreaterThan(0)
    await buildBtns[0].trigger('click')
    expect(environmentsAPI2.createBuild).toHaveBeenCalled()
  })
})
