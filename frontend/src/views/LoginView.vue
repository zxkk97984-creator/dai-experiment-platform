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
      <!-- Brandmark -->
      <div class="login-brand">
        <div class="brand-block">
          <span class="brand-letter">D</span>
        </div>
      </div>

      <div class="login-header">
        <h1>DAI 实验平台</h1>
        <p>面向人工智能课程的在线实验教学平台</p>
      </div>

      <form @submit.prevent="handleLogin" class="login-form">
        <!-- Error banner -->
        <transition name="error-slide">
          <div v-if="error" class="login-error" role="alert">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.2"/>
              <path d="M7 4v3.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
              <circle cx="7" cy="10" r="0.6" fill="currentColor"/>
            </svg>
            {{ error }}
          </div>
        </transition>

        <div class="input-wrap">
          <svg class="input-icon" width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
            <circle cx="7.5" cy="5" r="3" stroke="currentColor" stroke-width="1.1"/>
            <path d="M1.5 14c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/>
          </svg>
          <input
            id="login-username"
            v-model="username"
            type="text"
            placeholder="用户名"
            autocomplete="username"
          />
        </div>

        <div class="input-wrap">
          <svg class="input-icon" width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
            <rect x="2.5" y="7.5" width="10" height="5.5" rx="1" stroke="currentColor" stroke-width="1.1"/>
            <path d="M5 7.5V5a2.5 2.5 0 015 0v2.5" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/>
          </svg>
          <input
            id="login-password"
            v-model="password"
            type="password"
            placeholder="密码"
            autocomplete="current-password"
          />
        </div>

        <button type="submit" class="login-btn" :disabled="loading">
          <template v-if="loading">登录中…</template>
          <template v-else>登录</template>
        </button>
      </form>

      <p class="login-hint">
        <span class="hint-label">默认管理员</span>
        <code>admin</code><!--
        --><span class="hint-sep">/</span><!--
        --><code>Passw0rd!</code>
      </p>
    </div>
  </div>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Login — "Reading Room"
   Warm paper, white card, Prussian blue + cadmium orange accents.
   ═══════════════════════════════════════════════════════════════════════ */

/* ── Page ──────────────────────────────────── */
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--paper);
  padding: var(--space-4);
}

/* ── Card ──────────────────────────────────── */
.login-card {
  width: 400px;
  max-width: 100%;
  padding: var(--space-10) var(--space-10) var(--space-8);
  display: flex;
  flex-direction: column;
  align-items: center;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: 0 2px 16px rgba(0,0,0,0.04);
}

/* ── Brandmark ─────────────────────────────── */
.login-brand { margin-bottom: var(--space-6); }

.brand-block {
  width: 64px;
  height: 64px;
  background: var(--accent);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.brand-letter {
  font-family: var(--font-display);
  font-size: 32px;
  font-weight: 400;
  color: #fff;
  line-height: 1;
  margin-top: -2px;
}

/* ── Header ─────────────────────────────────── */
.login-header {
  text-align: center;
  margin-bottom: var(--space-8);
}

.login-header h1 {
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  font-weight: 400;
  color: var(--ink);
  margin: 0 0 6px;
  letter-spacing: -0.01em;
}

.login-header p {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
}

/* ── Form ───────────────────────────────────── */
.login-form {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* ── Input wrap ─────────────────────────────── */
.input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 14px;
  color: var(--text-secondary);
  opacity: 0.55;
  pointer-events: none;
  transition: color var(--duration-fast) var(--ease-out),
              opacity var(--duration-fast) var(--ease-out);
}

.input-wrap input {
  width: 100%;
  padding: 12px 14px 12px 40px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--ink);
  font-family: var(--font-body);
  font-size: var(--text-sm);
  transition: border-color var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-fast) var(--ease-out);
  box-shadow: none;
  outline: none;
}

.input-wrap input::placeholder {
  color: var(--text-secondary);
  opacity: 0.5;
}

.input-wrap input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(26,92,138,0.12);
}

/* Icon color on focus */
.input-wrap:focus-within .input-icon {
  color: var(--primary);
  opacity: 1;
}

/* ── Error ──────────────────────────────────── */
.login-error {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #FEF2F2;
  color: #B91C1C;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: 500;
  border: 1px solid #FECACA;
}

/* Error slide-in */
.error-slide-enter-active {
  transition: all var(--duration-normal) var(--ease-out);
}
.error-slide-leave-active {
  transition: all var(--duration-fast) var(--ease-out);
}
.error-slide-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}
.error-slide-leave-to {
  opacity: 0;
}

/* ── Button ─────────────────────────────────── */
.login-btn {
  width: 100%;
  padding: 12px;
  background: var(--accent);
  border: none;
  border-radius: var(--radius-md);
  color: #fff;
  font-family: var(--font-body);
  font-size: var(--text-sm);
  font-weight: 500;
  letter-spacing: 0.06em;
  cursor: pointer;
  margin-top: var(--space-3);
  transition: background var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-fast) var(--ease-out);
}

.login-btn:hover {
  background: var(--cta-hover);
  box-shadow: 0 4px 16px rgba(224,85,61,0.25);
}

.login-btn:active {
  transform: scale(0.985);
}

.login-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* ── Footer hint ────────────────────────────── */
.login-hint {
  margin-top: var(--space-6);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
}

.hint-label {
  color: var(--text-secondary);
  margin-right: 6px;
}

.login-hint code {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink);
  opacity: 0.7;
  background: rgba(0,0,0,0.04);
  padding: 1px 6px;
  border-radius: 3px;
}

.hint-sep {
  color: var(--border);
  margin: 0 2px;
}
</style>
