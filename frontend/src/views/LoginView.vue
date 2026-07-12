<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const router = useRouter()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

const roleHome = { student: '/student/courses', teacher: '/teacher/courses', admin: '/admin/users' }

async function handleLogin() {
  if (!username.value || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const user = await auth.login(username.value, password.value)
    router.push(roleHome[user.role] || '/login')
  } catch (e) {
    const detail = e.response?.data?.detail
    error.value = detail?.message || '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <div class="login-brand">DAI</div>
        <h1>实验平台</h1>
        <p>面向人工智能课程的在线实验教学平台</p>
      </div>

      <form @submit.prevent="handleLogin" class="login-form">
        <div class="form-group">
          <label>用户名</label>
          <input v-model="username" type="text" placeholder="输入用户名" autocomplete="username" />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input v-model="password" type="password" placeholder="输入密码" autocomplete="current-password" />
        </div>

        <div v-if="error" class="login-error">{{ error }}</div>

        <button type="submit" class="btn-primary login-btn" :disabled="loading">
          {{ loading ? '登录中...' : '登 录' }}
        </button>
      </form>

      <div class="login-hint">
        默认管理员: admin / Passw0rd!
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  height: 100vh; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #1e2532 0%, #2d3748 100%);
}
.login-card {
  background: #fff; padding: 48px 40px; border-radius: 12px;
  width: 400px; max-width: 95vw;
}
.login-header { text-align: center; margin-bottom: 32px; }
.login-brand {
  font-size: 28px; font-weight: 800; color: var(--accent); margin-bottom: 8px;
}
.login-header h1 { font-size: 22px; font-weight: 600; color: #111827; margin-bottom: 6px; }
.login-header p { font-size: 14px; color: var(--text-secondary); }

.login-form { display: flex; flex-direction: column; gap: 16px; }

.login-error {
  background: var(--danger-light); color: var(--danger);
  padding: 10px 14px; border-radius: 6px; font-size: 13px;
  border: 1px solid #fca5a5;
}

.login-btn {
  width: 100%; padding: 12px; font-size: 16px; margin-top: 8px;
}

.login-hint {
  text-align: center; margin-top: 24px;
  font-size: 12px; color: #9ca3af;
  font-family: var(--font-mono);
}
</style>
