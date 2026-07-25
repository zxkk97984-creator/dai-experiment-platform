<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()
function goLogin() { router.push('/login') }
function seeExamples() {
  const el = document.getElementById('features')
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  else router.push('/login')
}

const features = [
  { icon: 'lightning', title: '在线编程',    desc: '浏览器里直接写代码，免装环境，打开即写即跑' },
  { icon: 'gear',      title: '自动判题',    desc: '提交后秒级判分，用例覆盖一目了然，错了也知道错哪' },
  { icon: 'notebook',   title: 'Jupyter Lab', desc: '交互式 Notebook 实验，边学边练，像科学家一样探索' },
  { icon: 'chart',      title: '实时反馈',    desc: '学习进度、连击记录、能力雷达全可视化，看得见进步' },
]

const steps = [
  { n: '01', title: '写代码', desc: '打开浏览器就是你的实验台，内置 Python 3 环境，写完一键运行，无需配置任何工具链。' },
  { n: '02', title: '提交判题', desc: '系统自动跑通多组用例，秒级返回结果与错误定位，错了也能立刻知道为什么。' },
  { n: '03', title: '看进步', desc: '练习记录、能力雷达、连击天数全部可视化，把每一次提交都变成可见的成长。' },
]
</script>

<template>
  <div class="welcome">
    <!-- Hero 背景装饰：极浅蓝紫渐变 + 极淡网格 -->
    <div class="bg-decor" aria-hidden="true">
      <div class="bg-grad"></div>
      <div class="bg-grid"></div>
    </div>

    <!-- ── 顶部导航 ─────────────────────────────────────────────────── -->
    <header class="nav">
      <div class="nav-brand">
        <div class="brand-mark">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="2.4" fill="currentColor"/>
            <circle cx="5" cy="6.5" r="1.6" stroke="currentColor" stroke-width="1.5"/>
            <circle cx="5" cy="17.5" r="1.6" stroke="currentColor" stroke-width="1.5"/>
            <circle cx="19" cy="6.5" r="1.6" stroke="currentColor" stroke-width="1.5"/>
            <circle cx="19" cy="17.5" r="1.6" stroke="currentColor" stroke-width="1.5"/>
            <path d="M6.3 7.5L10.1 10.5M6.3 16.5L10.1 13.5M17.7 7.5L13.9 10.5M17.7 16.5L13.9 13.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="brand-text">
          <span class="brand-name">人工智能 实验平台</span>
          <span class="brand-tag">Python Learning Studio</span>
        </div>
      </div>
      <button class="nav-login" @click="goLogin">
        登录
        <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
          <path d="M3 8h10 M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
    </header>

    <!-- ── Hero 首屏 ───────────────────────────────────────────────── -->
    <main class="hero">
      <div class="hero-text">
        <div class="hero-eyebrow">
          面向学生的 Python 实战学习平台
        </div>
        <h1 class="hero-title">
          学 Python，<br/>
          <span class="hero-accent">从动手写代码开始。</span>
        </h1>
        <p class="hero-desc">
          在线实验、自动判题、即时反馈 —— 把每一行代码都跑起来。
        </p>
        <div class="hero-tags">
          <span class="hero-tag">在线编程</span>
          <span class="hero-tag">自动判题</span>
          <span class="hero-tag">Jupyter Lab</span>
          <span class="hero-tag">实时反馈</span>
        </div>
        <div class="hero-actions">
          <button class="hero-cta" @click="goLogin">
            进入学习平台
            <svg width="15" height="15" viewBox="0 0 16 16" fill="none">
              <path d="M3 8h10 M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
          <button class="hero-ghost" @click="seeExamples">查看课程示例</button>
        </div>
      </div>

      <!-- 代码编辑器展示卡片（页面唯一深色焦点） -->
      <div class="code-window">
        <!-- 顶部 Tab 栏 -->
        <div class="cw-bar">
          <span class="cw-dots" aria-hidden="true"><i></i><i></i><i></i></span>
          <span class="cw-tab">
            <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
              <path d="M4 2h5l3 3v9a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>
            </svg>
            hello.py
          </span>
          <span class="cw-lang-badge">Python 3.11</span>
          <button class="cw-run">
            <svg width="11" height="11" viewBox="0 0 12 12" fill="currentColor">
              <path d="M3 2l7 4-7 4z"/>
            </svg>
            运行
          </button>
        </div>

        <!-- 代码主体（行号 + 高亮） -->
        <div class="cw-body">
          <div class="cw-gutter"><span>1</span><span>2</span><span>3</span><span>4</span><span>5</span><span>6</span></div>
          <pre class="cw-code"><code><span class="c-kw">def</span> <span class="c-fn">greet</span>(name):
    <span class="c-kw">return</span> <span class="c-str">f"Hello, {name}!"</span>

<span class="c-cm"># 试试你的第一个 Python 程序</span>
<span class="c-var">message</span> = <span class="c-fn">greet</span>(<span class="c-str">"学生"</span>)
<span class="c-fn">print</span>(<span class="c-var">message</span>)</code></pre>
        </div>

        <!-- 输出面板 -->
        <div class="cw-output">
          <div class="cw-output-head">
            <span>输出</span>
            <span class="cw-passed">
              <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
                <circle cx="6" cy="6" r="5" fill="currentColor"/>
                <path d="M4 6.1l1.4 1.4L8 4.7" stroke="#0F172A" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              测试通过
            </span>
          </div>
          <pre class="cw-output-body"><span class="c-out">&gt;&gt;&gt; Hello, 学生!</span></pre>
        </div>

        <!-- 状态栏 -->
        <div class="cw-status">
          <span class="cw-st-item">Python 3.11</span>
          <span class="cw-st-sep"></span>
          <span class="cw-st-item">UTF-8</span>
          <span class="cw-st-spacer"></span>
          <span class="cw-st-item">第 6 行，第 13 列</span>
        </div>
      </div>
    </main>

    <!-- ── 功能卡片 ───────────────────────────────────────────────── -->
    <section id="features" class="features">
      <header class="features-head">
        <span class="features-eyebrow">核心能力</span>
        <h2 class="features-title">为学习路径设计的四大工具</h2>
        <p class="features-sub">从写下第一行代码到完成完整项目，每个环节都有顺手的工具承接。</p>
      </header>
      <div class="features-grid">
        <div
          v-for="f in features" :key="f.title"
          class="feature-card"
        >
          <div class="feat-icon" :class="`feat-icon--${f.icon}`">
            <svg v-if="f.icon === 'lightning'" width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
            </svg>
            <svg v-else-if="f.icon === 'gear'" width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.6"/>
              <path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41m11.32-11.32l1.41-1.41" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
            </svg>
            <svg v-else-if="f.icon === 'notebook'" width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M4 19.5A2.5 2.5 0 016.5 17H20" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
              <path d="M9 7h7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
            </svg>
            <svg v-else-if="f.icon === 'chart'" width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M3 3v18h18" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
              <path d="M7 14l4-4 4 4 5-5" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>
            </svg>
          </div>
          <h3 class="feat-title">{{ f.title }}</h3>
          <p class="feat-desc">{{ f.desc }}</p>
          <span class="feat-arrow" aria-hidden="true">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <path d="M3 8h10 M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </span>
        </div>
      </div>
    </section>

    <!-- ── 学习方式 三步 ─────────────────────────────────────────── -->
    <section id="how" class="how">
      <header class="features-head how-head">
        <span class="features-eyebrow">学习方式</span>
        <h2 class="features-title">三步走完一次完整练习</h2>
        <p class="features-sub">写、判、看 —— 把学习闭环压到最短，让反馈来得更快。</p>
      </header>
      <div class="steps">
        <div v-for="(s, i) in steps" :key="s.n" class="step">
          <span class="step-n">{{ s.n }}</span>
          <h3 class="step-title">{{ s.title }}</h3>
          <p class="step-desc">{{ s.desc }}</p>
          <span v-if="i < steps.length - 1" class="step-line" aria-hidden="true"></span>
        </div>
      </div>
    </section>

    <!-- ── 最终 CTA ─────────────────────────────────────────────── -->
    <section class="cta-band">
      <div class="cta-inner">
        <div class="cta-glow" aria-hidden="true"></div>
        <h2 class="cta-title">准备好写下你的第一行代码了吗？</h2>
        <p class="cta-desc">登录即可进入实验环境，今天就能完成你的第一个 Python 程序。</p>
        <button class="hero-cta cta-btn" @click="goLogin">
          立即开始学习
          <svg width="15" height="15" viewBox="0 0 16 16" fill="none">
            <path d="M3 8h10 M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
    </section>

    <!-- ── 页脚 ───────────────────────────────────────────────────── -->
    <footer class="footer">
      <span>© 2026 人工智能 实验平台</span>
      <span class="foot-sep">·</span>
      <span>Built for learners</span>
    </footer>
  </div>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Welcome / Landing — 明亮轻量教育科技风
   复用全局 tokens：--paper #F8FAFC / --primary #2563EB / --ink #0F172A
   / --text-secondary #64748B / --border #E2E8F0 / --radius-xl 16px
   间距：4 / 8 / 12 / 16 / 24 / 32 / 48 / 56 / 64 (4px grid)
   ═══════════════════════════════════════════════════════════════════════ */
.welcome {
  min-height: 100vh;
  background: var(--paper);
  display: flex;
  flex-direction: column;
  position: relative;
  overflow-x: clip;
  color: var(--ink);
  font-family: var(--font-body);
}

/* ── Hero 背景装饰（极浅，不抢内容） ─────────────────────────────── */
.bg-decor {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}
.bg-grad {
  position: absolute;
  inset: -20% -10% auto -10%;
  height: 720px;
  background:
    radial-gradient(ellipse 60% 50% at 20% 10%, rgba(124, 58, 237, 0.10) 0%, transparent 60%),
    radial-gradient(ellipse 55% 45% at 85% 20%, rgba(37, 99, 235, 0.12) 0%, transparent 60%);
  filter: blur(8px);
}
.bg-grid {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(15, 23, 42, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(15, 23, 42, 0.035) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: radial-gradient(ellipse 70% 55% at 50% 35%, #000 25%, transparent 75%);
}

/* ── 导航栏（浅色半透明 + 轻微模糊） ─────────────────────────────── */
.nav {
  position: sticky; top: 0; z-index: 20;
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 56px;
  background: rgba(248, 250, 252, 0.72);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(226, 232, 240, 0.6);
}
.nav-brand { display: flex; align-items: center; gap: 12px; }
.brand-mark {
  width: 36px; height: 36px;
  border-radius: var(--radius-md);
  background: var(--primary);
  display: flex; align-items: center; justify-content: center;
  color: #FFFFFF;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.22);
}
.brand-text { display: flex; flex-direction: column; gap: 3px; }
.brand-name {
  font-size: 15px; font-weight: 600; color: var(--ink);
  letter-spacing: -0.01em; line-height: 1;
}
.brand-tag {
  font-size: 11px; color: var(--text-tertiary);
  font-family: var(--font-mono); letter-spacing: 0.04em; line-height: 1;
}

.nav-login {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 8px 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--ink);
  font-family: var(--font-body);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: border-color var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-fast) var(--ease-out);
}
.nav-login:hover {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.10);
}

/* ── Hero ────────────────────────────────────────────────────────────── */
.hero {
  position: relative; z-index: 1;
  display: grid;
  grid-template-columns: 1.05fr 1fr;
  gap: 56px;
  align-items: center;
  max-width: 1180px;
  width: 100%;
  margin: 0 auto;
  padding: 64px 56px 72px;
}
.hero-text {
  display: flex; flex-direction: column;
  animation: fade-up 480ms var(--ease-out) both;
}
@keyframes fade-up {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
.hero-eyebrow {
  display: inline-flex; align-items: center;
  padding: 6px 14px;
  background: rgba(37, 99, 235, 0.06);
  border: 1px solid rgba(37, 99, 235, 0.14);
  border-radius: var(--radius-full);
  font-size: 12px;
  color: var(--primary);
  font-weight: 600;
  letter-spacing: 0.02em;
  margin-bottom: 24px;
  width: fit-content;
}
.hero-title {
  font-size: clamp(32px, 4.4vw, 48px);
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.03em;
  line-height: 1.12;
  margin: 0 0 18px;
}
.hero-accent {
  background: linear-gradient(90deg, #2563EB 0%, #7C3AED 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}
.hero-desc {
  font-size: 16px;
  color: var(--text-secondary);
  line-height: 1.7;
  margin: 0 0 24px;
  max-width: 500px;
}
.hero-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 32px; }
.hero-tag {
  display: inline-flex; align-items: center;
  padding: 6px 12px;
  background: rgba(37, 99, 235, 0.06);
  border: 1px solid rgba(37, 99, 235, 0.12);
  border-radius: var(--radius-full);
  font-size: 12px;
  color: #1D4ED8;
  font-weight: 500;
}

.hero-actions { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
.hero-cta {
  display: inline-flex; align-items: center; gap: 8px;
  height: 52px;
  padding: 0 24px;
  background: var(--primary);
  border: none;
  border-radius: var(--radius-lg);
  color: #FFFFFF;
  font-family: var(--font-body);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.22);
  transition: background var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out),
              transform var(--duration-normal) var(--ease-out);
}
.hero-cta:hover {
  background: var(--primary-dark);
  box-shadow: 0 8px 20px rgba(37, 99, 235, 0.30);
  transform: translateY(-2px);
}
.hero-cta:active { transform: translateY(0); box-shadow: 0 2px 6px rgba(37, 99, 235, 0.20); }
.hero-ghost {
  height: 52px;
  padding: 0 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  color: var(--ink);
  font-family: var(--font-body);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: border-color var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out);
}
.hero-ghost:hover {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.08);
}

/* ── 代码编辑器（页面唯一深色焦点） ───────────────────────────────── */
.code-window {
  background: #1E293B;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: var(--radius-xl);
  overflow: hidden;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.6),
    0 12px 32px rgba(37, 99, 235, 0.10),
    0 8px 20px rgba(15, 23, 42, 0.08);
  align-self: center;
  width: 100%;
  max-width: 520px;
  animation: fade-up 560ms var(--ease-out) 80ms both;
  transition: transform var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out);
}
.code-window:hover {
  transform: translateY(-3px);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.6),
    0 18px 40px rgba(37, 99, 235, 0.14),
    0 10px 24px rgba(15, 23, 42, 0.10);
}
.cw-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px;
  background: #0F172A;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.cw-dots { display: inline-flex; gap: 6px; margin-right: 4px; }
.cw-dots i {
  width: 10px; height: 10px; border-radius: 50%;
  background: rgba(255, 255, 255, 0.14);
  display: block;
}
.cw-dots i:nth-child(1) { background: #FF5F57; }
.cw-dots i:nth-child(2) { background: #FEBC2E; }
.cw-dots i:nth-child(3) { background: #28C840; }
.cw-tab {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.82);
  font-family: var(--font-mono);
  padding: 4px 10px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: var(--radius-sm);
}
.cw-lang-badge {
  font-size: 10px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(96, 165, 250, 0.8);
  padding: 2px 7px;
  background: rgba(96, 165, 250, 0.1);
  border: 1px solid rgba(96, 165, 250, 0.2);
  border-radius: var(--radius-xs);
  letter-spacing: 0.02em;
}
.cw-run {
  margin-left: auto;
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px;
  background: rgba(16, 185, 129, 0.14);
  border: 1px solid rgba(16, 185, 129, 0.28);
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-family: var(--font-mono);
  color: #34D399;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out);
}
.cw-run:hover { background: rgba(16, 185, 129, 0.22); }

.cw-body {
  display: flex;
  font-family: var(--font-mono), 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 13px;
  line-height: 1.75;
  color: #E2E8F0;
}
.cw-gutter {
  flex-shrink: 0;
  display: flex; flex-direction: column;
  padding: 16px 10px 16px 16px;
  text-align: right;
  color: rgba(255, 255, 255, 0.28);
  user-select: none;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
}
.cw-gutter span { display: block; }
.cw-code {
  flex: 1;
  padding: 16px;
  margin: 0;
  white-space: pre;
  overflow-x: auto;
}
.cw-code code { background: none; border: none; padding: 0; color: inherit; font-size: inherit; }
.c-kw  { color: #A78BFA; }
.c-fn  { color: #60A5FA; }
.c-str { color: #FCD34D; }
.c-cm  { color: #64748B; font-style: italic; }
.c-var { color: #E2E8F0; }

.cw-output {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  background: #0F172A;
}
.cw-output-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 16px 4px;
  font-size: 11px;
  font-family: var(--font-mono);
  color: rgba(255, 255, 255, 0.4);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.cw-passed {
  display: inline-flex; align-items: center; gap: 5px;
  color: #34D399;
  text-transform: none;
  letter-spacing: 0;
  font-weight: 600;
}
.cw-output-body {
  padding: 0 16px 12px;
  margin: 0;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.7;
}
.c-out { color: #34D399; }

.cw-status {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 16px;
  background: #0F172A;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 11px;
  font-family: var(--font-mono);
  color: rgba(255, 255, 255, 0.4);
}
.cw-st-item { display: inline-flex; }
.cw-st-sep { width: 1px; height: 10px; background: rgba(255, 255, 255, 0.12); }
.cw-st-spacer { flex: 1; }

/* ── 功能卡片（统一白色，蓝色体系） ─────────────────────────────── */
.features {
  position: relative; z-index: 1;
  max-width: 1180px;
  width: 100%;
  margin: 0 auto;
  padding: 0 56px 64px;
}
.features-head { margin-bottom: 28px; }
.features-eyebrow {
  display: inline-block;
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.features-title {
  font-size: clamp(22px, 2.6vw, 28px);
  font-weight: 600;
  color: var(--ink);
  letter-spacing: -0.02em;
  line-height: 1.25;
  margin: 0;
}
.features-sub {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 10px 0 0;
  max-width: 540px;
}
.features-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}
.feature-card {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: 24px;
  display: flex; flex-direction: column;
  transition: border-color var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out),
              transform var(--duration-normal) var(--ease-out);
}
.feature-card:hover {
  border-color: rgba(37, 99, 235, 0.4);
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.06), 0 2px 6px rgba(37, 99, 235, 0.06);
  transform: translateY(-4px);
}
.feat-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 40px; height: 40px;
  border-radius: var(--radius-md);
  background: rgba(37, 99, 235, 0.08);
  color: var(--primary);
  margin-bottom: 16px;
}
/* 微妙的图标色相区分，仍属蓝色体系 */
.feat-icon--lightning { background: rgba(37, 99, 235, 0.09);  color: #2563EB; }
.feat-icon--gear      { background: rgba(99, 102, 241, 0.09); color: #6366F1; }
.feat-icon--notebook  { background: rgba(124, 58, 237, 0.09); color: #7C3AED; }
.feat-icon--chart     { background: rgba(14, 165, 233, 0.09); color: #0EA5E9; }
.feat-title {
  font-size: 15px; font-weight: 600;
  color: var(--ink); letter-spacing: -0.01em;
  margin: 0 0 8px;
  line-height: 1.3;
}
.feat-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
  flex: 1;
}
.feat-arrow {
  display: inline-flex; align-items: center;
  margin-top: 14px;
  color: var(--text-tertiary);
  opacity: 0;
  transform: translateX(-4px);
  transition: opacity var(--duration-normal) var(--ease-out),
              transform var(--duration-normal) var(--ease-out),
              color var(--duration-normal) var(--ease-out);
}
.feature-card:hover .feat-arrow {
  opacity: 1;
  transform: translateX(0);
  color: var(--primary);
}

/* ── 学习方式 三步 ─────────────────────────────────────────────── */
.how {
  position: relative; z-index: 1;
  max-width: 1180px;
  width: 100%;
  margin: 0 auto;
  padding: 0 56px 64px;
}
.how-head { text-align: center; margin-bottom: 36px; }
.how-head .features-eyebrow,
.how-head .features-title { display: block; }
.how-head .features-sub { margin-left: auto; margin-right: auto; }
.steps {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}
.step {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: 28px 24px;
}
.step-n {
  display: inline-flex; align-items: center; justify-content: center;
  width: 40px; height: 40px;
  border-radius: var(--radius-md);
  background: rgba(37, 99, 235, 0.08);
  color: var(--primary);
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 16px;
}
.step-title {
  font-size: 17px; font-weight: 600;
  color: var(--ink); letter-spacing: -0.01em;
  margin: 0 0 8px;
}
.step-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.65;
  margin: 0;
}
.step-line {
  position: absolute;
  top: 48px; right: -16px;
  width: 32px; height: 1px;
  background: linear-gradient(90deg, var(--border), transparent);
}
.step-line::after {
  content: '';
  position: absolute;
  right: 0; top: -3px;
  width: 7px; height: 7px;
  border-top: 1px solid var(--border);
  border-right: 1px solid var(--border);
  transform: rotate(45deg);
}

/* ── 最终 CTA ─────────────────────────────────────────────────── */
.cta-band {
  position: relative; z-index: 1;
  max-width: 1180px;
  width: 100%;
  margin: 0 auto 64px;
  padding: 0 56px;
}
.cta-inner {
  position: relative;
  overflow: hidden;
  text-align: center;
  padding: 56px 32px;
  background:
    linear-gradient(135deg, rgba(37, 99, 235, 0.05) 0%, rgba(124, 58, 237, 0.05) 100%),
    var(--surface);
  border: 1px solid rgba(37, 99, 235, 0.16);
  border-radius: var(--radius-2xl);
}
.cta-glow {
  position: absolute;
  inset: -40% 20% auto 20%;
  height: 320px;
  background: radial-gradient(ellipse 50% 50% at 50% 50%, rgba(124, 58, 237, 0.12) 0%, transparent 70%);
  filter: blur(20px);
  pointer-events: none;
}
.cta-title {
  position: relative;
  font-size: clamp(22px, 2.8vw, 30px);
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.025em;
  line-height: 1.2;
  margin: 0 0 12px;
}
.cta-desc {
  position: relative;
  font-size: 15px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0 0 28px;
}
.cta-btn { position: relative; margin: 0 auto; }

/* ── 页脚 ───────────────────────────────────────────────────────────── */
.footer {
  position: relative; z-index: 1;
  display: flex; align-items: center; gap: 8px;
  padding: 24px 56px 32px;
  font-size: 12px;
  color: var(--text-tertiary);
  max-width: 1180px;
  margin: 0 auto;
  width: 100%;
  border-top: 1px solid var(--border);
}
.foot-sep { color: rgba(100, 116, 139, 0.5); }

/* ── 响应式 ─────────────────────────────────────────────────────────── */
@media (max-width: 1024px) {
  .features-grid { grid-template-columns: repeat(2, 1fr); }
  .steps { grid-template-columns: 1fr; }
  .step-line { display: none; }
}
@media (max-width: 768px) {
  .nav { padding: 14px 24px; }
  .nav-links { display: none; }
  .hero {
    grid-template-columns: 1fr;
    padding: 32px 24px 40px;
    gap: 32px;
  }
  .hero-title { font-size: 30px; }
  .hero-actions { flex-direction: column; align-items: stretch; }
  .hero-cta, .hero-ghost { width: 100%; justify-content: center; }
  .code-window { max-width: 100%; }
  .features,
  .how,
  .cta-band { padding-left: 24px; padding-right: 24px; }
  .features-grid { grid-template-columns: 1fr; }
  .cta-inner { padding: 40px 24px; }
  .footer { padding: 20px 24px 24px; }
}

@media (prefers-reduced-motion: reduce) {
  .hero-text, .code-window { animation: none; }
  .hero-cta:hover, .feature-card:hover, .code-window:hover { transform: none; }
}
</style>
