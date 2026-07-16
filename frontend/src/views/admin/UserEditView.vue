<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { usersAPI } from '../../api/users.js'
import { useAppStore } from '../../stores/app.js'

const route = useRoute()
const router = useRouter()
const app = useAppStore()
const isNew = ref(route.params.id === 'new')
const user = ref(null)
const form = ref({ username: '', real_name: '', role: 'student', password: '' })
const saving = ref(false)

onMounted(async () => {
  if (!isNew.value) {
    try {
      const res = await usersAPI.get(route.params.id)
      user.value = res.data
      form.value = {
        username: res.data.username,
        real_name: res.data.real_name,
        role: res.data.role,
        password: '',
      }
    } catch { app.showToast('用户不存在', 'error'); router.push('/admin/users') }
  }
})

async function handleSave() {
  if (!form.value.username) { app.showToast('请输入用户名', 'error'); return }
  saving.value = true
  try {
    if (isNew.value) {
      if (!form.value.password) { app.showToast('请输入密码', 'error'); saving.value = false; return }
      await usersAPI.create(form.value)
      app.showToast('用户已创建', 'success')
    } else {
      await usersAPI.update(route.params.id, {
        username: form.value.username,
        real_name: form.value.real_name,
        role: form.value.role,
      })
      if (form.value.password) {
        await usersAPI.updatePassword(route.params.id, { password: form.value.password })
      }
      app.showToast('用户已更新', 'success')
    }
    router.push('/admin/users')
  } catch (e) { app.showToast(e.response?.data?.detail?.message || '保存失败', 'error') }
  finally { saving.value = false }
}
</script>

<template>
  <AppLayout>
    <h1 class="page-title">{{ isNew ? '创建用户' : '编辑用户' }}</h1>
    <div class="card" style="max-width:500px">
      <div class="form-group"><label>用户名</label><input v-model="form.username" /></div>
      <div class="form-group"><label>真实姓名</label><input v-model="form.real_name" /></div>
      <div class="form-group">
        <label>角色</label>
        <select v-model="form.role">
          <option value="student">学生</option><option value="teacher">教师</option>
          <option value="admin">管理员</option><option value="developer">开发者</option>
        </select>
      </div>
      <div class="form-group">
        <label>{{ isNew ? '密码' : '新密码 (留空不修改)' }}</label>
        <input v-model="form.password" type="password" />
      </div>
      <div style="display:flex;gap:10px">
        <button class="btn-primary" :disabled="saving" @click="handleSave">
          {{ saving ? '保存中...' : '保存' }}
        </button>
        <button @click="router.push('/admin/users')">取消</button>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ── Page title ── */
.page-title { color: var(--ink); }

/* ── Form card ── */
.card {
  background: var(--surface);
  border-color: var(--border);
}

/* ── Form inputs ── */
input,
select {
  background: var(--surface);
  border-color: var(--border);
  color: var(--ink);
}

input::placeholder { color: var(--text-secondary); }

input:focus,
select:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(26, 92, 138, 0.18);
}

/* ── Labels ── */
label {
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

/* ── Save button ── */
button.btn-primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

button.btn-primary:hover {
  background: #C94A33;
  border-color: #C94A33;
}

button.btn-primary:disabled { opacity: 0.5; }

/* ── Cancel button ── */
.card button:not(.btn-primary) {
  background: transparent;
  border-color: var(--border);
  color: var(--text-secondary);
}

.card button:not(.btn-primary):hover {
  background: var(--surface-raised);
  border-color: var(--border);
  color: var(--ink);
}
</style>
