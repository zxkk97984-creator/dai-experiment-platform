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
const form = ref({ username: '', student_no: '', real_name: '', role: 'student', password: '' })
const saving = ref(false)

onMounted(async () => {
  if (!isNew.value) {
    try {
      const res = await usersAPI.get(route.params.id)
      user.value = res.data
      form.value = {
        username: res.data.username,
        student_no: res.data.student_no || '',
        real_name: res.data.real_name,
        role: res.data.role,
        password: '',
      }
    } catch { app.showToast('用户不存在', 'error'); router.push('/admin/users') }
  }
})

async function handleSave() {
  if (!form.value.username) { app.showToast('请输入用户名', 'error'); return }
  if (form.value.role === 'student' && !form.value.student_no.trim()) { app.showToast('学生必须填写学号', 'error'); return }
  saving.value = true
  try {
    if (isNew.value) {
      if (!form.value.password) { app.showToast('请输入密码', 'error'); saving.value = false; return }
      await usersAPI.create(form.value)
      app.showToast('用户已创建', 'success')
    } else {
      await usersAPI.update(route.params.id, {
        real_name: form.value.real_name,
        student_no: form.value.role === 'student' ? form.value.student_no : null,
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
    <div class="page">
      <!-- ── Page Head ─────────────────────────────────────────────────── -->
      <header class="page-head">
        <div>
          <h1 class="page-title">{{ isNew ? '创建用户' : '编辑用户' }}</h1>
          <p class="page-sub">{{ isNew ? '添加新的平台用户账号' : '修改用户信息与角色权限' }}</p>
        </div>
      </header>

      <div class="card form-card">
        <div class="form-group"><label>登录用户名</label><input v-model="form.username" :disabled="!isNew" placeholder="输入用户名" /><small v-if="!isNew">登录用户名创建后不可修改</small></div>
        <div v-if="form.role === 'student'" class="form-group"><label>学号</label><input v-model="form.student_no" required placeholder="输入唯一学号" /></div>
        <div class="form-group"><label>真实姓名</label><input v-model="form.real_name" placeholder="输入真实姓名" /></div>
        <div class="form-group">
          <label>角色</label>
          <select v-model="form.role">
            <option value="student">学生</option>
            <option value="teacher">教师</option>
            <option value="admin">管理员</option>
            <option value="developer">开发者</option>
          </select>
        </div>
        <div class="form-group">
          <label>{{ isNew ? '密码' : '新密码（留空不修改）' }}</label>
          <input v-model="form.password" type="password" :placeholder="isNew ? '设置密码' : '留空则不修改密码'" />
        </div>
        <div class="form-actions">
          <button class="btn-primary" :disabled="saving" @click="handleSave">
            {{ saving ? '保存中...' : '保存' }}
          </button>
          <button class="btn-ghost" @click="router.push('/admin/users')">取消</button>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   User Edit — Code Studio
   page-head + form card
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

/* ── Form Card ─────────────────────────────────────────────────────── */
.form-card {
  max-width: 520px; padding: 28px;
}
.form-actions {
  display: flex; gap: 10px; padding-top: 8px;
}

@media (max-width: 768px) {
  .page-title { font-size: 24px; }
  .form-card { max-width: 100%; padding: 20px; }
}
</style>
