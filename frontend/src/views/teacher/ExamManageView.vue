<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { examsAPI } from '../../api/exams.js'
import { useAppStore } from '../../stores/app.js'
const router = useRouter(); const app = useAppStore()
const exams = ref([]); const loading = ref(true); const showCreate = ref(false)
const form = ref({ title: '', course_id: '', duration_minutes: 60, start_at: '', end_at: '' })
function badgeClass(status) { return status === 'published' ? 'badge-success' : 'badge-neutral' }
function badgeLabel(status) { return status === 'published' ? '已发布' : '草稿' }
async function fetch() { loading.value = true; try { const res = await examsAPI.list(); exams.value = res.data.items || res.data } catch { app.showToast('加载失败', 'error') } finally { loading.value = false } }
async function handleCreate() { if (!form.value.title) return; try { await examsAPI.create({ ...form.value, course_id: parseInt(form.value.course_id) || undefined }); app.showToast('创建成功', 'success'); showCreate.value = false; fetch() } catch (e) { app.showToast(e.response?.data?.detail?.message || '创建失败', 'error') } }
async function publishExam(id) { try { await examsAPI.update(id, { status: 'published' }); app.showToast('已发布', 'success'); fetch() } catch (e) { app.showToast(e.response?.data?.detail?.message || '操作失败', 'error') } }
onMounted(fetch)
</script>

<template>
  <AppLayout>
    <div class="page">
      <!-- ── Page Head ─────────────────────────────────────────────────── -->
      <header class="page-head">
        <div>
          <h1 class="page-title">考试管理</h1>
          <p class="page-sub">创建考试、配置题目、查看成绩单与统计</p>
        </div>
        <div class="page-meta">
          <button class="btn-primary" @click="showCreate = !showCreate">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
            {{ showCreate ? '取消' : '创建考试' }}
          </button>
        </div>
      </header>

      <!-- ── Create Form ───────────────────────────────────────────────── -->
      <div v-if="showCreate" class="card create-form">
        <div class="form-group"><label>考试名称</label><input v-model="form.title" placeholder="输入考试名称" /></div>
        <div class="grid-2">
          <div class="form-group"><label>课程 ID</label><input v-model="form.course_id" type="number" placeholder="关联课程 ID" /></div>
          <div class="form-group"><label>时长（分钟）</label><input v-model.number="form.duration_minutes" type="number" placeholder="60" /></div>
        </div>
        <div class="form-group"><label>开始时间</label><input v-model="form.start_at" type="datetime-local" /></div>
        <button class="btn-primary" @click="handleCreate">确认创建</button>
      </div>

      <!-- ── Loading ────────────────────────────────────────────────────── -->
      <div v-if="loading" class="card table-card">
        <div class="skeleton-row" v-for="i in 4" :key="i">
          <div class="skeleton skel-cell w-35"></div>
          <div class="skeleton skel-cell w-15"></div>
          <div class="skeleton skel-cell w-20"></div>
          <div class="skeleton skel-cell w-25"></div>
        </div>
      </div>

      <!-- ── Empty ──────────────────────────────────────────────────────── -->
      <div v-else-if="exams.length === 0" class="empty-state">
        <p>📝 暂无考试，点击「创建考试」开始</p>
      </div>

      <!-- ── Table ──────────────────────────────────────────────────────── -->
      <div v-else class="card table-card">
        <table>
          <thead>
            <tr><th>名称</th><th>状态</th><th>时长</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="e in exams" :key="e.id">
              <td class="title-cell">{{ e.title }}</td>
              <td>
                <span class="badge" :class="badgeClass(e.status)">{{ badgeLabel(e.status) }}</span>
              </td>
              <td class="text-sm text-secondary">{{ e.duration_minutes }} 分钟</td>
              <td class="actions-cell">
                <button class="btn-ghost btn-sm" @click="router.push('/teacher/exams/' + e.id + '/edit')">编辑题目</button>
                <button class="btn-ghost btn-sm" @click="router.push('/teacher/exams/' + e.id + '/grades')">成绩</button>
                <button v-if="e.status === 'draft'" class="btn-sm btn-publish" @click="publishExam(e.id)">发布</button>
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
   Teacher Exam Manage — Code Studio
   page-head + create form + skeleton table + data table
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
.create-form .form-group { margin-bottom: var(--space-3); }

/* ── Table card ────────────────────────────────────────────────────── */
.table-card {
  padding: 0; overflow: hidden;
}
.table-card table { margin: 0; }

/* ── Skeleton ──────────────────────────────────────────────────────── */
.skeleton-row {
  display: flex; gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}
.skeleton-row:last-child { border-bottom: none; }
.skel-cell { height: 16px; border-radius: var(--radius-sm); }
.w-15 { width: 15%; }
.w-20 { width: 20%; }
.w-25 { width: 25%; }
.w-35 { width: 35%; }

/* ── Cells ─────────────────────────────────────────────────────────── */
.title-cell { font-weight: 500; color: var(--ink); }

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
}
</style>
