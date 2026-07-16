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
/* ═══════════════════════════════════════════════════════════
   User List — Pythonista Dark Theme
   ═══════════════════════════════════════════════════════════ */

/* ── Page title ──────────────────────────────────────────── */
.page-title { color: #D6DEEB; }

/* ── Table card ──────────────────────────────────────────── */
table.card {
  background: #1A1E2B;
  border-color: #2A3040;
}

/* ── Table header ────────────────────────────────────────── */
thead th {
  background: #11141D;
  color: #6A7086;
  border-bottom-color: #2A3040;
}

/* ── Table body ──────────────────────────────────────────── */
tbody td {
  color: #D6DEEB;
  border-bottom-color: #2A3040;
}

tbody tr:hover td { background: rgba(224, 85, 61, 0.04); }

/* Secondary text (ID column / pagination / loading) */
td .text-secondary,
.text-secondary { color: #6A7086; }

/* ── Username link ───────────────────────────────────────── */
td a {
  color: #D6DEEB;
  cursor: pointer;
}

td a:hover { color: #E0553D; }

/* ── Dark-adapted badges ─────────────────────────────────── */
.badge-success { background: rgba(15, 123, 94, 0.18); color: #34D3A5; }
.badge-warning { background: rgba(181, 118, 14, 0.18); color: #F5BC4E; }
.badge-danger  { background: rgba(209, 46, 62, 0.18); color: #F06A78; }
.badge-info    { background: rgba(88, 102, 196, 0.18); color: #A0A6F6; }
.badge-neutral { background: rgba(106, 112, 134, 0.15); color: #8891A4; }

/* ── Select dropdowns ────────────────────────────────────── */
select {
  background: #151821;
  border-color: #2A3040;
  color: #D6DEEB;
}

select:focus {
  outline: none;
  border-color: #E0553D;
  box-shadow: 0 0 0 3px rgba(224, 85, 61, 0.18);
}

/* ── Buttons (dark base) ─────────────────────────────────── */
button {
  background: #1A1E2B;
  border-color: #2A3040;
  color: #8891A4;
}

button:hover:not(:disabled) {
  background: rgba(224, 85, 61, 0.08);
  border-color: #3A4050;
  color: #D6DEEB;
}

button:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* ── Accent orange primary button ────────────────────────── */
button.btn-primary {
  background: #E0553D;
  border-color: #E0553D;
  color: #fff;
}

button.btn-primary:hover {
  background: #C94A33;
  border-color: #C94A33;
}

/* ── Danger button ───────────────────────────────────────── */
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
