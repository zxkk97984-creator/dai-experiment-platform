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
    <div class="flex-between mb-4">
      <h1 class="page-title" style="margin-bottom:0">用户管理</h1>
      <button class="btn-primary" @click="router.push('/admin/users/new/edit')">创建用户</button>
    </div>

    <div class="flex gap-2 mb-4">
      <select v-model="filters.role" @change="page=1;fetch()">
        <option value="">全部角色</option>
        <option value="student">学生</option><option value="teacher">教师</option>
        <option value="admin">管理员</option>
      </select>
      <select v-model="filters.status" @change="page=1;fetch()">
        <option value="">全部状态</option>
        <option value="active">正常</option><option value="disabled">已禁用</option>
      </select>
    </div>

    <div v-if="loading" class="text-secondary">加载中...</div>
    <table v-else class="card" style="padding:0">
      <thead><tr><th>ID</th><th>用户名</th><th>姓名</th><th>角色</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="u in users" :key="u.id">
          <td class="text-sm text-secondary">{{ u.id }}</td>
          <td><a @click="router.push(`/admin/users/${u.id}/edit`)" style="cursor:pointer">{{ u.username }}</a></td>
          <td>{{ u.real_name }}</td>
          <td><span class="badge" :class="'badge-' + statusBadge(ROLE_MAP, u.role).color">{{ statusBadge(ROLE_MAP, u.role).label }}</span></td>
          <td><span class="badge" :class="'badge-' + statusBadge(USER_STATUS_MAP, u.status).color">{{ statusBadge(USER_STATUS_MAP, u.status).label }}</span></td>
          <td>
            <button class="btn-sm" @click="router.push(`/admin/users/${u.id}/edit`)">编辑</button>
            <button class="btn-sm" :class="u.status === 'active' ? 'btn-danger' : ''" style="margin-left:6px" @click="toggleStatus(u)">{{ u.status === 'active' ? '禁用' : '启用' }}</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="total > 20" class="flex-center mt-4" style="justify-content:center">
      <button :disabled="page<=1" @click="page--;fetch()">上一页</button>
      <span class="text-sm text-secondary mx-3">第 {{ page }} 页 / 共 {{ Math.ceil(total/20) }} 页</span>
      <button :disabled="page>=Math.ceil(total/20)" @click="page++;fetch()">下一页</button>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ── Page title ── */
.page-title { color: var(--ink); }

/* ── Table card ── */
table.card {
  background: var(--surface);
  border-color: var(--border);
}

/* ── Table header ── */
thead th {
  background: var(--surface-raised);
  color: var(--text-secondary);
  border-bottom-color: var(--border);
}

/* ── Table body ── */
tbody td {
  color: var(--ink);
  border-bottom-color: var(--border);
}

tbody tr:hover td { background: var(--surface-raised); }

/* Secondary text */
.text-secondary { color: var(--text-secondary); }

/* ── Username link ── */
td a {
  color: var(--primary);
  cursor: pointer;
}

td a:hover { color: var(--accent); }

/* ── Select dropdowns ── */
select {
  background: var(--surface);
  border-color: var(--border);
  color: var(--ink);
}

select:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(26, 92, 138, 0.18);
}

/* ── Buttons ── */
button {
  background: var(--surface);
  border-color: var(--border);
  color: var(--text-secondary);
}

button:hover:not(:disabled) {
  background: var(--surface-raised);
  border-color: var(--border);
  color: var(--ink);
}

button:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* ── Primary button ── */
button.btn-primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

button.btn-primary:hover {
  background: #C94A33;
  border-color: #C94A33;
}

/* ── Danger button ── */
button.btn-danger {
  background: #D12E3E;
  border-color: #D12E3E;
  color: #fff;
}

button.btn-danger:hover {
  background: #B82634;
  border-color: #B82634;
}
</style>
