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
    <!-- ── Left: brand / showcase ─────────────────────────────────────── -->
    <section class="showcase">
      <div class="showcase-bg"></div>
      <div class="showcase-content">
        <header class="brand">
          <div class="brand-mark">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L3 7v10l9 5 9-5V7l-9-5z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>
              <path d="M12 2v20 M3 7l9 5 9-5" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>
            </svg>
          </div>
          <div class="brand-text">
            <span class="brand-name">DAI 实验平台</span>
            <span class="brand-tag">Python Learning Studio</span>
          </div>
        </header>

        <div class="hero">
          <h1 class="hero-title">
            学 Python，<br/>
            <span class="hero-accent">从动手写代码开始。</span>
          </h1>
          <p class="hero-desc">
            在线实验、自动判题、即时反馈 —— 把每一行代码都跑起来。
          </p>
          <div class="hero-tags">
            <span class="hero-tag">
              <span class="tag-dot"></span> 在线编程
            </span>
            <span class="hero-tag">
              <span class="tag-dot"></span> 自动判题
            </span>
            <span class="hero-tag">
              <span class="tag-dot"></span> Jupyter Lab
            </span>
            <span class="hero-tag">
              <span class="tag-dot"></span> 实时反馈
            </span>
          </div>
        </div>

        <!-- Code window mockup -->
        <div class="code-window">
          <div class="cw-bar">
            <span class="cw-dot cw-dot-red"></span>
            <span class="cw-dot cw-dot-yellow"></span>
            <span class="cw-dot cw-dot-green"></span>
            <span class="cw-name">hello.py</span>
          </div>
          <pre class="cw-body"><code><span class="c-kw">def</span> <span class="c-fn">greet</span>(name):
    <span class="c-kw">return</span> <span class="c-str">f"Hello, {name}!"</span>

<span class="c-cm"># 试试你的第一个 Python 程序</span>
<span class="c-var">message</span> = <span class="c-fn">greet</span>(<span class="c-str">"学生"</span>)
<span class="c-fn">print</span>(<span class="c-var">message</span>)
<span class="c-out"># &gt;&gt;&gt; Hello, 学生!</span></code></pre>
        </div>

        <footer class="showcase-foot">
          <span>© 2026 DAI 实验平台</span>
          <span class="foot-sep">·</span>
          <span>Built for learners</span>
        </footer>
      </div>
    </section>

    <!-- ── Right: form ────────────────────────────────────────────────── -->
    <section class="form-panel">
      <div class="form-inner">
        <div class="form-header">
          <h2 class="form-title">欢迎回来 👋</h2>
          <p class="form-sub">登录你的学习账号，继续未完成的实验</p>
        </div>

        <form @submit.prevent="handleLogin" class="login-form">
          <transition name="error-slide">
            <div v-if="error" class="login-error" role="alert">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.3"/>
                <path d="M8 4.5v3.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
                <circle cx="8" cy="11" r="0.7" fill="currentColor"/>
              </svg>
              <span>{{ error }}</span>
            </div>
          </transition>

          <div class="field">
            <label for="login-username">用户名</label>
            <input
              id="login-username"
              v-model="username"
              type="text"
              placeholder="请输入用户名"
              autocomplete="username"
            />
          </div>

          <div class="field">
            <label for="login-password">密码</label>
            <input
              id="login-password"
              v-model="password"
              type="password"
              placeholder="请输入密码"
              autocomplete="current-password"
            />
          </div>

          <button type="submit" class="login-btn" :disabled="loading">
            <svg v-if="loading" width="14" height="14" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5" stroke-dasharray="20 8" stroke-linecap="round">
                <animateTransform attributeName="transform" type="rotate" from="0 8 8" to="360 8 8" dur="0.9s" repeatCount="indefinite"/>
              </circle>
            </svg>
            <span v-if="loading">登录中…</span>
            <span v-else>登 录</span>
            <svg v-if="!loading" width="14" height="14" viewBox="0 0 16 16" fill="none">
              <path d="M3 8h10 M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </form>

        <div class="form-foot"></div>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Login — Modern Python Learning Studio
   Left: deep gradient with code window mockup.
   Right: clean form panel.
   ═══════════════════════════════════════════════════════════════════════ */

.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  background: var(--paper);
}

/* ── Showcase (left) ─────────────────────────────────────────────────── */
.showcase {
  position: relative;
  overflow: hidden;
  background: #0F172A;
  display: flex;
  align-items: stretch;
}

.showcase-bg {
  position: absolute; inset: 0;
  background:
    radial-gradient(circle at 20% 20%, rgba(37, 99, 235, 0.28) 0%, transparent 45%),
    radial-gradient(circle at 80% 80%, rgba(249, 115, 22, 0.20) 0%, transparent 50%),
    radial-gradient(circle at 50% 50%, rgba(139, 92, 246, 0.10) 0%, transparent 60%),
    linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
}

.showcase-bg::before {
  content: '';
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 32px 32px;
}

.showcase-content {
  position: relative;
  z-index: 1;
  padding: 48px 56px 40px;
  display: flex;
  flex-direction: column;
  width: 100%;
  color: #FFFFFF;
}

/* Brand */
.brand {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 64px;
}
.brand-mark {
  width: 38px; height: 38px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
  display: flex; align-items: center; justify-content: center;
  color: #FFFFFF;
  flex-shrink: 0;
  box-shadow: 0 8px 20px rgba(37, 99, 235, 0.5);
}
.brand-text {
  display: flex; flex-direction: column; gap: 2px;
}
.brand-name {
  font-size: 16px;
  font-weight: 700;
  color: #FFFFFF;
  letter-spacing: -0.01em;
  line-height: 1;
}
.brand-tag {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  font-family: var(--font-mono);
  letter-spacing: 0.04em;
  line-height: 1;
}

/* Hero */
.hero {
  margin-bottom: 40px;
}
.hero-title {
  font-size: 40px;
  font-weight: 700;
  color: #FFFFFF;
  letter-spacing: -0.025em;
  line-height: 1.15;
  margin: 0 0 16px;
}
.hero-accent {
  background: linear-gradient(135deg, #60A5FA 0%, #F97316 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}
.hero-desc {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.6;
  margin: 0 0 24px;
  max-width: 460px;
}
.hero-tags {
  display: flex; flex-wrap: wrap; gap: 8px;
}
.hero-tag {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 11px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--radius-full);
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
  font-weight: 500;
}
.tag-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: #60A5FA;
}
.hero-tag:nth-child(2) .tag-dot { background: #F97316; }
.hero-tag:nth-child(3) .tag-dot { background: #10B981; }
.hero-tag:nth-child(4) .tag-dot { background: #8B5CF6; }

/* Code window mockup */
.code-window {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-lg);
  overflow: hidden;
  backdrop-filter: blur(8px);
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.35);
  margin-top: auto;
  max-width: 520px;
}
.cw-bar {
  display: flex; align-items: center; gap: 6px;
  padding: 10px 14px;
  background: rgba(0, 0, 0, 0.25);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.cw-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
}
.cw-dot-red    { background: #FF5F57; }
.cw-dot-yellow { background: #FEBC2E; }
.cw-dot-green  { background: #28C840; }
.cw-name {
  margin-left: 10px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);
  font-family: var(--font-mono);
}
.cw-body {
  padding: 18px 20px;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.7;
  color: #E2E8F0;
  margin: 0;
}
.cw-body code { background: none; border: none; padding: 0; color: inherit; font-size: inherit; }

/* Syntax colors */
.c-kw  { color: #C084FC; }   /* keyword: def, return */
.c-fn  { color: #60A5FA; }   /* function name */
.c-str { color: #FCD34D; }   /* string */
.c-cm  { color: #64748B; font-style: italic; }   /* comment */
.c-var { color: #E2E8F0; }   /* variable */
.c-out { color: #10B981; font-style: italic; }   /* output */

/* Footer */
.showcase-foot {
  margin-top: 24px;
  display: flex; align-items: center; gap: 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}
.foot-sep { color: rgba(255, 255, 255, 0.2); }

/* ── Form panel (right) ──────────────────────────────────────────────── */
.form-panel {
  background: var(--surface);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 56px;
}

.form-inner {
  width: 100%;
  max-width: 380px;
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.form-header { margin-bottom: 32px; }
.form-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.02em;
  line-height: 1.15;
  margin: 0 0 8px;
}
.form-sub {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
}

/* Form */
.login-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
  flex: 1;
}

.field { display: flex; flex-direction: column; }
.field label {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--ink);
  margin-bottom: 6px;
}
.field input {
  width: 100%;
  padding: 11px 14px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--ink);
  font-family: var(--font-body);
  font-size: 14px;
  line-height: 1.5;
  transition: border-color var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-fast) var(--ease-out);
}
.field input::placeholder { color: var(--text-tertiary); }
.field input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-glow-primary);
}

/* Error */
.login-error {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--danger-light);
  color: var(--danger);
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: 500;
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.error-slide-enter-active { transition: all var(--duration-normal) var(--ease-out); }
.error-slide-leave-active { transition: all var(--duration-fast) var(--ease-out); }
.error-slide-enter-from { opacity: 0; transform: translateY(-6px); }
.error-slide-leave-to { opacity: 0; }

/* Button */
.login-btn {
  width: 100%;
  padding: 12px;
  background: var(--primary);
  border: none;
  border-radius: var(--radius-md);
  color: #FFFFFF;
  font-family: var(--font-body);
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.02em;
  cursor: pointer;
  margin-top: 8px;
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  transition: background var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-fast) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
}
.login-btn:hover:not(:disabled) {
  background: var(--primary-dark);
  box-shadow: 0 8px 20px rgba(37, 99, 235, 0.32);
  transform: translateY(-1px);
}
.login-btn:active:not(:disabled) { transform: translateY(0); }
.login-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none; }

/* Footer */
.form-foot {
  margin-top: auto;
  padding-top: 32px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
/* ── Responsive ──────────────────────────────────────────────────────── */
@media (max-width: 960px) {
  .login-page { grid-template-columns: 1fr; }
  .showcase {
    padding: 32px 24px;
    min-height: 360px;
  }
  .showcase-content { padding: 0; }
  .brand { margin-bottom: 24px; }
  .hero-title { font-size: 28px; }
  .hero-desc { font-size: 14px; margin-bottom: 16px; }
  .code-window { display: none; }
  .form-panel { padding: 32px 24px; }
  .form-inner { min-height: auto; max-width: 100%; }
}
</style>
