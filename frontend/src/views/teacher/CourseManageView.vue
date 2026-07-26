<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { coursesAPI } from '../../api/courses.js'
import { useAppStore } from '../../stores/app.js'
import { statusBadge, PUBLISH_STATUS_MAP } from '../../utils/status.js'

const router = useRouter()
const app = useAppStore()
const courses = ref([])
const loading = ref(true)
const showCreate = ref(false)
const form = ref({ title: '', description: '' })
const creating = ref(false)

async function fetch() {
  loading.value = true
  try { const res = await coursesAPI.list(); courses.value = res.data.items || res.data }
  catch { app.showToast('加载失败', 'error') }
  finally { loading.value = false }
}

async function handleCreate() {
  if (!form.value.title) return
  creating.value = true
  try {
    await coursesAPI.create(form.value)
    app.showToast('创建成功', 'success')
    showCreate.value = false
    form.value = { title: '', description: '' }
    fetch()
  } catch (e) {
    app.showToast(e.response?.data?.detail?.message || '创建失败', 'error')
  } finally { creating.value = false }
}

async function handlePublish(c) {
  try { await coursesAPI.update(c.id, { status: 'published' }); app.showToast('已发布', 'success'); fetch() }
  catch { app.showToast('操作失败', 'error') }
}

onMounted(fetch)
</script>

<template>
  <AppLayout>
    <div class="page">
      <!-- ── Page Head ─────────────────────────────────────────────────── -->
      <header class="page-head">
        <div>
          <h1 class="page-title">课程管理</h1>
          <p class="page-sub">创建与维护课程，管理章节和课时安排</p>
        </div>
        <div class="page-meta">
          <button class="btn-primary" @click="showCreate = !showCreate">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
            {{ showCreate ? '取消' : '创建课程' }}
          </button>
        </div>
      </header>

      <!-- ── Create Form ───────────────────────────────────────────────── -->
      <div v-if="showCreate" class="card create-form">
        <div class="form-group">
          <label>课程名称</label>
          <input v-model="form.title" placeholder="输入课程名称" />
        </div>
        <div class="form-group">
          <label>课程简介</label>
          <textarea v-model="form.description" rows="3" placeholder="输入课程简介"></textarea>
        </div>
        <button class="btn-primary" :disabled="creating" @click="handleCreate">
          {{ creating ? '创建中...' : '确认创建' }}
        </button>
      </div>

      <!-- ── Loading ────────────────────────────────────────────────────── -->
      <div v-if="loading" class="card table-card">
        <div class="skeleton-row" v-for="i in 4" :key="i">
          <div class="skeleton skel-cell w-40"></div>
          <div class="skeleton skel-cell w-20"></div>
          <div class="skeleton skel-cell w-35"></div>
        </div>
      </div>

      <!-- ── Empty ──────────────────────────────────────────────────────── -->
      <div v-else-if="courses.length === 0" class="empty-state">
        <p>📚 暂无课程，点击上方按钮创建第一个课程</p>
      </div>

      <!-- ── Table ──────────────────────────────────────────────────────── -->
      <div v-else class="card table-card">
        <table>
          <thead>
            <tr>
              <th>名称</th><th>状态</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in courses" :key="c.id">
              <td>
                <a class="course-link" @click="router.push(`/teacher/courses/${c.id}/manage`)">{{ c.title }}</a>
              </td>
              <td>
                <span class="badge" :class="'badge-' + statusBadge(PUBLISH_STATUS_MAP, c.status).color">
                  {{ statusBadge(PUBLISH_STATUS_MAP, c.status).label }}
                </span>
              </td>
              <td class="actions-cell">
                <button class="btn-ghost btn-sm" @click="router.push(`/teacher/courses/${c.id}/manage`)">章节课时</button>
                <button v-if="c.status === 'draft'" class="btn-sm btn-publish" @click="handlePublish(c)">发布</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Teacher Course Manage — Code Studio
   page-head + create form card + skeleton table + data table
   ═══════════════════════════════════════════════════════════════════════ */
.page { display: flex; flex-direction: column; gap: 24px; }

/* ── Page Head ─────────────────────────────────────────────────────── */
.page-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 16px;
}
.page-title {
  font-size: 28px; font-weight: 700;
  color: var(--ink); letter-spacing: -0.02em; line-height: 1.15;
  margin: 0 0 6px;
}
.page-sub {
  font-size: var(--text-sm); color: var(--text-secondary); margin: 0;
}

/* ── Create Form ───────────────────────────────────────────────────── */
.create-form {
  padding: 24px;
  display: flex; flex-direction: column; gap: 4px;
}
.create-form .form-group { margin-bottom: var(--space-4); }

/* ── Table card ────────────────────────────────────────────────────── */
.table-card {
  padding: 0; overflow: hidden;
}
.table-card table { margin: 0; }

/* ── Skeleton rows ─────────────────────────────────────────────────── */
.skeleton-row {
  display: flex; gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}
.skeleton-row:last-child { border-bottom: none; }
.skel-cell { height: 16px; border-radius: var(--radius-sm); }
.w-20 { width: 20%; }
.w-35 { width: 35%; }
.w-40 { width: 40%; }

/* ── Course link ───────────────────────────────────────────────────── */
.course-link {
  color: var(--primary); cursor: pointer; font-weight: 500;
  transition: color var(--duration-fast) var(--ease-out);
}
.course-link:hover { color: var(--primary-dark); }

/* ── Actions ───────────────────────────────────────────────────────── */
.actions-cell { display: flex; gap: 8px; }
.btn-publish {
  color: var(--accent);
  border-color: var(--accent);
  background: transparent;
}
.btn-publish:hover {
  background: var(--accent);
  color: var(--surface);
  border-color: var(--accent);
}

@media (max-width: 768px) {
  .page-head { flex-direction: column; }
  .page-title { font-size: 24px; }
  .create-form { padding: 18px; }
}
</style>
