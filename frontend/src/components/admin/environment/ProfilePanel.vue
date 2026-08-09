<script setup>
// 环境档位 tab：档位列表 + 新建档位 + 版本管理（复制新版本/触发构建）
// available 版本不可编辑、不可重建；新版本从旧版本复制（source_version_id）
import { ref, onMounted } from 'vue'
import { environmentsAPI } from '../../../api/environments.js'
import { useAppStore } from '../../../stores/app.js'
import { statusBadge } from '../../../utils/status.js'

const app = useAppStore()
const profiles = ref([])
const loading = ref(true)
const showCreate = ref(false)
const createForm = ref({ slug: '', display_name: '', description: '' })

// 新版本面板：展开档位 + 版本列表 + 创建表单
const expandedProfile = ref(null)
const versions = ref([])
const versionsLoading = ref(false)
const showNewVersion = ref(false)
const versionForm = ref({ source_version_id: null, package_ids: [], minimum_memory_mb: 256 })
const packagesCatalog = ref([])

const PROFILE_STATUS_MAP = {
  active: { label: '正常', color: 'success' },
  inactive: { label: '已停用', color: 'neutral' },
}
const VERSION_STATUS_MAP = {
  draft: { label: '草稿', color: 'neutral' },
  queued: { label: '排队中', color: 'info' },
  building: { label: '构建中', color: 'warning' },
  available: { label: '可用', color: 'success' },
  failed: { label: '失败', color: 'danger' },
  inactive: { label: '已停用', color: 'neutral' },
}

function pkgSummary(version) {
  const pkgs = version?.packages || []
  return pkgs.map((p) => p.pip_name).join(' · ') || '—'
}

async function fetch() {
  loading.value = true
  try {
    const res = await environmentsAPI.listProfiles()
    profiles.value = res.data || []
  } catch {
    app.showToast('加载失败', 'error')
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!createForm.value.slug || !createForm.value.display_name) return
  try {
    await environmentsAPI.createProfile({ ...createForm.value })
    app.showToast('档位已创建', 'success')
    showCreate.value = false
    createForm.value = { slug: '', display_name: '', description: '' }
    fetch()
  } catch (e) {
    app.showToast(e.response?.data?.detail?.message || '创建失败', 'error')
  }
}

// 新版本：从旧版本复制（预选源版本与包集合）
async function openNewVersion(profile) {
  expandedProfile.value = profile.id
  showNewVersion.value = true
  versionsLoading.value = true
  try {
    const [versRes, pkgsRes] = await Promise.all([
      environmentsAPI.listVersions(profile.id),
      environmentsAPI.listPackages('active'),
    ])
    versions.value = versRes.data || []
    packagesCatalog.value = pkgsRes.data || []
    const newest = versions.value[0] || null  // 版本号倒序，首个为最新
    versionForm.value = {
      source_version_id: newest ? newest.id : null,
      package_ids: newest ? (newest.packages || []).map((p) => p.id).filter(Boolean) : [],
      minimum_memory_mb: newest ? newest.minimum_memory_mb : 256,
    }
  } catch {
    app.showToast('加载失败', 'error')
  } finally {
    versionsLoading.value = false
  }
}

function togglePackage(packageId) {
  const ids = versionForm.value.package_ids
  const idx = ids.indexOf(packageId)
  if (idx >= 0) ids.splice(idx, 1)
  else ids.push(packageId)
}

async function handleCreateVersion() {
  const profile = profiles.value.find((p) => p.id === expandedProfile.value)
  if (!profile) return
  try {
    await environmentsAPI.createVersion(profile.id, {
      source_version_id: versionForm.value.source_version_id,
      package_ids: versionForm.value.package_ids,
      minimum_memory_mb: versionForm.value.minimum_memory_mb,
    })
    app.showToast('新版本已创建（草稿）', 'success')
    showNewVersion.value = false
    const res = await environmentsAPI.listVersions(profile.id)
    versions.value = res.data || []
  } catch (e) {
    app.showToast(e.response?.data?.detail?.message || '创建失败', 'error')
  }
}

async function handleBuild(version) {
  try {
    await environmentsAPI.createBuild(version.id)
    app.showToast('构建任务已入队', 'success')
    const res = await environmentsAPI.listVersions(expandedProfile.value)
    versions.value = res.data || []
  } catch (e) {
    app.showToast(e.response?.data?.detail?.message || '入队失败', 'error')
  }
}

function sourceLabel() {
  const src = versions.value.find((v) => v.id === versionForm.value.source_version_id)
  return src ? `从 v${src.version_number} 复制` : '全新版本（无包）'
}

onMounted(fetch)
</script>

<template>
  <div class="panel">
    <!-- ── 操作条 ─────────────────────────────────────────────────────── -->
    <div class="panel-bar">
      <p class="panel-hint">环境档位由管理员维护：勾选受控包组合成不可变版本，版本构建成功后教师可见。</p>
      <button class="btn-primary" @click="showCreate = !showCreate">
        {{ showCreate ? '取消' : '新建档位' }}
      </button>
    </div>

    <!-- ── 新建档位表单 ──────────────────────────────────────────────── -->
    <div v-if="showCreate" class="card profile-form">
      <div class="form-grid">
        <div class="form-group">
          <label>slug *</label>
          <input v-model="createForm.slug" name="slug" placeholder="小写字母/数字/短横线，如 torch-cpu" />
        </div>
        <div class="form-group">
          <label>展示名 *</label>
          <input v-model="createForm.display_name" name="display_name" placeholder="如 PyTorch CPU" />
        </div>
        <div class="form-group span-2">
          <label>描述</label>
          <textarea v-model="createForm.description" name="description" rows="2" placeholder="档位用途说明"></textarea>
        </div>
      </div>
      <div class="form-actions">
        <button class="btn-primary" @click="handleCreate">确认创建</button>
      </div>
    </div>

    <!-- ── 档位表格 ───────────────────────────────────────────────────── -->
    <div v-if="loading" class="card table-card">
      <div class="skeleton-row" v-for="i in 3" :key="i">
        <div class="skeleton skel-cell w-15"></div>
        <div class="skeleton skel-cell w-10"></div>
        <div class="skeleton skel-cell w-10"></div>
        <div class="skeleton skel-cell w-30"></div>
        <div class="skeleton skel-cell w-10"></div>
        <div class="skeleton skel-cell w-20"></div>
      </div>
    </div>
    <div v-else-if="profiles.length === 0" class="empty-state">
      <p>🏷 暂无环境档位，请先创建</p>
    </div>
    <div v-else class="card table-card">
      <table>
        <thead>
          <tr><th>名称</th><th>slug</th><th>最新可用版本</th><th>包摘要</th><th>资源下限</th><th>状态</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="profile in profiles" :key="profile.id">
            <td class="strong">{{ profile.display_name }}</td>
            <td class="mono">{{ profile.slug }}</td>
            <td>
              <span v-if="profile.latest_version" class="vnum">v{{ profile.latest_version.version_number }}</span>
              <span v-else class="text-tertiary text-sm">—</span>
            </td>
            <td class="text-sm text-secondary">{{ profile.latest_version ? pkgSummary(profile.latest_version) : '—' }}</td>
            <td class="mono">{{ profile.latest_version ? `${profile.latest_version.minimum_memory_mb} MB` : '—' }}</td>
            <td>
              <span class="badge" :class="'badge-' + statusBadge(PROFILE_STATUS_MAP, profile.status).color">
                {{ statusBadge(PROFILE_STATUS_MAP, profile.status).label }}
              </span>
            </td>
            <td class="actions-cell">
              <button class="btn-ghost btn-sm" @click="expandedProfile = expandedProfile === profile.id ? null : profile.id">
                {{ expandedProfile === profile.id ? '收起' : '版本' }}
              </button>
              <button class="btn-ghost btn-sm new-version-btn" @click="openNewVersion(profile)">新版本</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ── 版本区块（展开档位） ──────────────────────────────────────── -->
    <div v-if="expandedProfile !== null" class="card versions-card">
      <div class="versions-head">
        <h3 class="versions-title">版本列表</h3>
        <span class="text-secondary text-sm">available 版本不可编辑、不可重建</span>
      </div>
      <div v-if="versionsLoading" class="text-secondary text-sm">加载中…</div>
      <table v-else class="versions-table">
        <thead>
          <tr><th>版本</th><th>状态</th><th>内存</th><th>包集合</th><th>镜像</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="ver in versions" :key="ver.id">
            <td class="vnum">v{{ ver.version_number }}</td>
            <td>
              <span class="badge" :class="'badge-' + statusBadge(VERSION_STATUS_MAP, ver.status).color">
                {{ statusBadge(VERSION_STATUS_MAP, ver.status).label }}
              </span>
            </td>
            <td class="mono">{{ ver.minimum_memory_mb }} MB</td>
            <td class="text-sm text-secondary">{{ pkgSummary(ver) }}</td>
            <td>
              <span v-if="ver.image_digest" class="mono digest-short" :title="ver.image_digest">{{ ver.image_digest.slice(0, 12) }}…</span>
              <span v-else class="text-tertiary text-sm">—</span>
            </td>
            <td class="actions-cell">
              <button
                v-if="ver.status === 'draft' || ver.status === 'failed' || ver.status === 'inactive'"
                class="btn-sm build-btn"
                @click="handleBuild(ver)"
              >构建</button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- ── 新版本创建表单（从旧版本复制） ─────────────────────────── -->
      <div v-if="showNewVersion" class="new-version-form">
        <h3 class="versions-title">创建新版本</h3>
        <p class="source-hint">
          {{ sourceLabel() }}
          <span v-if="versionForm.source_version_id" class="text-tertiary">— 包集合与内存将复制自源版本</span>
        </p>
        <div class="form-grid">
          <div class="form-group">
            <label>内存下限（MB）</label>
            <input v-model.number="versionForm.minimum_memory_mb" type="number" name="minimum_memory_mb" min="64" max="65536" />
          </div>
          <div class="form-group">
            <label>包集合（勾选受控包）</label>
            <div class="pkg-checklist">
              <label v-for="pkg in packagesCatalog" :key="pkg.id" class="pkg-check">
                <input
                  type="checkbox"
                  :checked="versionForm.package_ids.includes(pkg.id)"
                  @change="togglePackage(pkg.id)"
                />
                {{ pkg.pip_name }}=={{ pkg.locked_version }}
                <span v-if="pkg.status === 'inactive'" class="text-tertiary">（停用）</span>
              </label>
            </div>
          </div>
        </div>
        <div class="form-actions">
          <button class="btn-primary" @click="handleCreateVersion">创建草稿版本</button>
          <button class="btn-ghost" @click="showNewVersion = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.panel { display: flex; flex-direction: column; gap: 16px; }
.panel-bar {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
}
.panel-hint { margin: 0; font-size: var(--text-xs); color: var(--text-secondary); }
.profile-form { padding: 16px; }
.form-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px;
}
.span-2 { grid-column: span 2; }
.form-actions { display: flex; gap: 8px; margin-top: 14px; }
.mono { font-family: var(--font-mono, ui-monospace, monospace); font-size: 12px; }
.strong { font-weight: 600; }
.vnum {
  display: inline-block; padding: 1px 6px;
  font-size: 12px; border-radius: 4px;
  background: var(--primary-light, #e8f1ff); color: var(--primary, #2b6de8);
}
.digest-short { color: var(--text-secondary); }
.actions-cell { display: flex; gap: 8px; }

.versions-card { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.versions-head {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
}
.versions-title { margin: 0; font-size: 15px; }
.versions-table { margin: 0; }
.new-version-form {
  margin-top: 8px; padding-top: 14px;
  border-top: 1px solid var(--border, #dfe3e8);
}
.source-hint { margin: 6px 0 12px; font-size: var(--text-sm); color: var(--primary, #2b6de8); font-weight: 500; }
.pkg-checklist {
  display: flex; flex-wrap: wrap; gap: 6px 14px;
  max-height: 160px; overflow-y: auto;
}
.pkg-check { display: inline-flex; align-items: center; gap: 5px; font-size: var(--text-sm); }
</style>
