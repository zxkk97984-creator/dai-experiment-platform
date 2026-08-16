<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { usersAPI } from '../../api/users.js'
import { useAppStore } from '../../stores/app.js'
import { statusBadge, ROLE_MAP, USER_STATUS_MAP } from '../../utils/status.js'

const router = useRouter()
const app = useAppStore()
const users = ref([])
const loading = ref(true)
const total = ref(0)
const page = ref(1)
const filters = ref({ role: '', status: '' })

async function fetch() {
  loading.value = true
  try {
    const res = await usersAPI.list({ page: page.value, page_size: 20, ...filters.value })
    users.value = res.data.items; total.value = res.data.total
  }
  catch { app.showToast('加载失败', 'error') }
  finally { loading.value = false }
}

async function toggleStatus(u) {
  const newStatus = u.status === 'active' ? 'disabled' : 'active'
  try { await usersAPI.updateStatus(u.id, { status: newStatus }); app.showToast('状态已更新', 'success'); fetch() }
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
          <h1 class="page-title">用户管理</h1>
          <p class="page-sub">创建、编辑、管理用户账号与角色权限</p>
        </div>
        <div class="page-meta">
          <button class="btn-primary" @click="router.push('/admin/users/new/edit')">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
            创建用户
          </button>
        </div>
      </header>

      <!-- ── Filters ───────────────────────────────────────────────────── -->
      <div class="filter-bar">
        <select v-model="filters.role" @change="page=1;fetch()">
          <option value="">全部角色</option>
          <option value="student">学生</option>
          <option value="teacher">教师</option>
          <option value="admin">管理员</option>
        </select>
        <select v-model="filters.status" @change="page=1;fetch()">
          <option value="">全部状态</option>
          <option value="active">正常</option>
          <option value="disabled">已禁用</option>
        </select>
        <div class="filter-count">
          共 {{ total }} 名用户
        </div>
      </div>

      <!-- ── Loading ────────────────────────────────────────────────────── -->
      <div v-if="loading" class="card table-card">
        <div class="skeleton-row" v-for="i in 5" :key="i">
          <div class="skeleton skel-cell w-10"></div>
          <div class="skeleton skel-cell w-20"></div>
          <div class="skeleton skel-cell w-15"></div>
          <div class="skeleton skel-cell w-15"></div>
          <div class="skeleton skel-cell w-15"></div>
          <div class="skeleton skel-cell w-20"></div>
        </div>
      </div>

      <!-- ── Empty ──────────────────────────────────────────────────────── -->
      <div v-else-if="users.length === 0" class="empty-state">
        <p>暂无匹配用户</p>
      </div>

      <!-- ── Table ──────────────────────────────────────────────────────── -->
      <div v-else class="card table-card">
        <table class="ds-table">
          <thead>
            <tr><th>ID</th><th>用户名</th><th>学号</th><th>姓名</th><th>角色</th><th>状态</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id">
              <td class="text-sm text-secondary">{{ u.id }}</td>
              <td>
                <a class="user-link" @click="router.push(`/admin/users/${u.id}/edit`)">{{ u.username }}</a>
              </td>
              <td>{{ u.student_no || '—' }}</td>
              <td>{{ u.real_name }}</td>
              <td>
                <span class="badge" :class="'badge-' + statusBadge(ROLE_MAP, u.role).color">
                  {{ statusBadge(ROLE_MAP, u.role).label }}
                </span>
              </td>
              <td>
                <span class="badge" :class="'badge-' + statusBadge(USER_STATUS_MAP, u.status).color">
                  {{ statusBadge(USER_STATUS_MAP, u.status).label }}
                </span>
              </td>
              <td class="actions-cell">
                <button class="btn-ghost btn-sm" @click="router.push(`/admin/users/${u.id}/edit`)">编辑</button>
                <button class="btn-sm" :class="u.status === 'active' ? 'btn-danger-outline' : ''" @click="toggleStatus(u)">
                  {{ u.status === 'active' ? '禁用' : '启用' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ── Pagination ─────────────────────────────────────────────────── -->
      <nav v-if="total > 20" class="pagination">
        <button class="pg-btn" :disabled="page <= 1" @click="page--;fetch()">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M10 3l-5 5 5 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
          上一页
        </button>
        <div class="pg-info">
          <span class="pg-current">{{ page }}</span>
          <span class="pg-sep">/</span>
          <span class="pg-total">{{ Math.ceil(total / 20) }}</span>
        </div>
        <button class="pg-btn" :disabled="page >= Math.ceil(total / 20)" @click="page++;fetch()">
          下一页
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M6 3l5 5-5 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
      </nav>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Admin User List — Code Studio
   page-head + filter bar + skeleton table + data table + pagination
   ═══════════════════════════════════════════════════════════════════════ */
.page { display: flex; flex-direction: column; gap: 24px; }

/* ── Page Head ─────────────────────────────────────────────────────── */
.page-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 16px;
}
.page-title {
  font-size: 28px; font-weight: 700;
  color: var(--fg); letter-spacing: -0.02em; line-height: 1.15;
  margin: 0 0 6px;
}
.page-sub {
  font-size: var(--text-sm); color: var(--muted); margin: 0;
}

/* ── Filter bar ────────────────────────────────────────────────────── */
.filter-bar {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
}
.filter-bar select {
  min-width: 120px;
}
.filter-count {
  font-size: var(--text-xs); color: var(--muted);
  margin-left: auto;
}

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
.w-10 { width: 10%; }
.w-15 { width: 15%; }
.w-20 { width: 20%; }

/* ── User link ─────────────────────────────────────────────────────── */
.user-link {
  color: var(--accent); cursor: pointer; font-weight: 500;
  transition: color var(--duration-fast) var(--ease-out);
}
.user-link:hover { color: var(--accent-hover); }

/* ── Actions ───────────────────────────────────────────────────────── */
.actions-cell {
  display: table-cell;
  vertical-align: middle;
  white-space: nowrap;
}
.actions-cell button + button { margin-left: 8px; }
.btn-danger-outline {
  color: var(--danger);
  border-color: var(--danger);
  background: transparent;
}
.btn-danger-outline:hover {
  background: var(--danger);
  color: var(--surface);
  border-color: var(--danger);
}

/* ── Pagination ────────────────────────────────────────────────────── */
.pagination {
  display: flex; align-items: center; justify-content: center;
  gap: 16px;
}
.pg-btn {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 8px 14px;
  font-size: var(--text-sm); font-weight: 500;
  color: var(--fg); cursor: pointer;
  display: inline-flex; align-items: center; gap: 6px;
  transition: background var(--duration-fast) var(--ease-out),
              border-color var(--duration-fast) var(--ease-out);
}
.pg-btn:hover:not(:disabled) {
  background: var(--surface-subtle);
  border-color: var(--border-strong);
}
.pg-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.pg-info {
  display: flex; align-items: baseline; gap: 4px;
  font-size: var(--text-sm); font-family: var(--font-mono);
  padding: 0 8px;
}
.pg-current { color: var(--accent); font-weight: 700; font-size: 15px; }
.pg-sep { color: var(--faint); }
.pg-total { color: var(--muted); }

@media (max-width: 768px) {
  .page-head { flex-direction: column; }
  .page-title { font-size: 24px; }
  .filter-bar { flex-direction: column; align-items: stretch; }
  .filter-count { margin-left: 0; }
}
</style>
