# Welcome Page Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `/welcome` as a bright, animated technology gallery that presents the platform's complete learning, coding, judging, AI grading, and multi-role capabilities.

**Architecture:** Keep `WelcomeView.vue` as the route-level orchestrator and move each visual section into a focused presentational component. Centralize visible content in one static content module, use a small `useReveal` composable for one-shot viewport entry, and keep navigation/router behavior in the view.

**Tech Stack:** Vue 3 Composition API, Vue Router, scoped CSS, Vitest, Vue Test Utils, Vite, Browser plugin

---

## File Structure

Create:

- `frontend/src/views/welcome/welcomeContent.js` — exact visible copy and demo data
- `frontend/src/composables/useReveal.js` — one-shot viewport reveal with static fallback
- `frontend/src/composables/__tests__/useReveal.spec.js` — reveal and fallback coverage
- `frontend/src/components/welcome/WelcomeHero.vue` — hero copy, code execution sequence, AI score panel
- `frontend/src/components/welcome/CapabilityShowcase.vue` — capability gallery and hover micro-interactions
- `frontend/src/components/welcome/LearningFlow.vue` — five-step learning loop
- `frontend/src/components/welcome/RoleShowcase.vue` — student, teacher, administrator, developer scenes
- `frontend/src/components/welcome/__tests__/WelcomeHero.spec.js`
- `frontend/src/components/welcome/__tests__/CapabilityShowcase.spec.js`
- `frontend/src/components/welcome/__tests__/LearningFlow.spec.js`
- `frontend/src/components/welcome/__tests__/RoleShowcase.spec.js`
- `frontend/src/views/__tests__/WelcomeView.spec.js`

Modify:

- `frontend/src/views/WelcomeView.vue` — replace the existing 825-line page with the new composition, navigation, final CTA, and shared page styling

Do not modify:

- `frontend/src/router/index.js`
- authentication stores or APIs
- application dashboards
- global design tokens unless a browser-verified gap cannot be solved locally

### Task 1: Lock the Production Visual Reference

**Files:**

- Reference: `docs/superpowers/specs/2026-07-30-welcome-page-visual-redesign-design.md`
- Reference: `.superpowers/brainstorm/1380-1785379574/content/bright-gallery-system-v4.html`
- Artifact outside committed source: generated concept screenshot

- [ ] **Step 1: Capture the current page baseline**

Use the Browser plugin at `http://localhost:8080/welcome` with a 1280×720 viewport. Save a first-viewport screenshot outside the repository and record page URL, title, console warnings/errors, and the current primary interaction path.

Expected baseline flow:

```text
/welcome
  -> click “进入学习平台”
  -> /login
```

- [ ] **Step 2: Generate the production concept**

Use the `imagegen` skill to create a 1440×900 full-screen concept matching the approved bright technology gallery. The prompt must include these fixed constraints:

```text
Create a polished 1440×900 desktop UI concept for a Chinese AI experiment learning platform.
Use an ice-white background, cobalt blue primary color, restrained violet accents, and one deep navy product-demo window.
Keep every interface panel upright and aligned to a strict grid; no rotation, tilt, perspective, or diagonal cards.
Hero copy: “从代码开始，探索 AI 世界”.
Show a full 10-line Python training and evaluation example, running status, completed output, 20/20 epochs, 98.6% accuracy, all tests passed, and an AI grading result.
Below the hero, show a non-repetitive capability gallery for courses, live coding, Notebook, assignments, exams, automatic judging, AI grading, and experiment templates.
Include a dark learning-loop transition band and four role scenes for students, teachers, administrators, and developers.
Use generous whitespace, crisp Chinese typography, subtle depth, soft grid light, and production-grade product UI.
Do not add external photography, illustrations, fake logos, diagonal containers, or generic marketing badges.
```

- [ ] **Step 3: Verify concept fidelity before coding**

Inspect the concept and confirm all of the following:

```text
[ ] All panels are upright
[ ] Hero copy is exact
[ ] Code example is dense enough to fill the editor
[ ] AI score panel is visible
[ ] Capability gallery is not eight identical cards
[ ] Learning loop and four role scenes are represented
[ ] Ice white, cobalt, violet, navy, and green are the only dominant colors
[ ] No visible copy contradicts the approved specification
```

If the concept misses any checked item, regenerate it before touching source code. Record the accepted concept path for final fidelity comparison.

- [ ] **Step 4: Present the concept for final visual approval**

Show the concept to the user and state that it implements the already-approved structure, upright geometry, code density, hover language, color system, and responsive direction. Do not begin source edits until the user accepts the production concept.

### Task 2: Add the Static Content Contract

**Files:**

- Create: `frontend/src/views/welcome/welcomeContent.js`
- Test: `frontend/src/components/welcome/__tests__/WelcomeHero.spec.js`

- [ ] **Step 1: Write a failing hero content test**

Create `frontend/src/components/welcome/__tests__/WelcomeHero.spec.js`:

```js
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import WelcomeHero from '../WelcomeHero.vue'
import { heroCodeLines } from '../../../views/welcome/welcomeContent.js'

describe('WelcomeHero', () => {
  it('renders the complete code execution story', () => {
    const wrapper = mount(WelcomeHero, {
      props: { codeLines: heroCodeLines },
    })

    expect(wrapper.get('h1').text()).toContain('从代码开始')
    expect(wrapper.findAll('[data-testid="code-line"]')).toHaveLength(10)
    expect(wrapper.text()).toContain('20 / 20')
    expect(wrapper.text()).toContain('98.6%')
    expect(wrapper.text()).toContain('全部测试通过')
  })

  it('emits explore and login actions', async () => {
    const wrapper = mount(WelcomeHero, {
      props: { codeLines: heroCodeLines },
    })

    await wrapper.get('[data-testid="hero-explore"]').trigger('click')
    await wrapper.get('[data-testid="login-action"]').trigger('click')

    expect(wrapper.emitted('explore')).toHaveLength(1)
    expect(wrapper.emitted('login')).toHaveLength(1)
  })
})
```

- [ ] **Step 2: Run the test and verify the missing-module failure**

Run:

```bash
cd frontend
npm.cmd test -- src/components/welcome/__tests__/WelcomeHero.spec.js
```

Expected: FAIL because `WelcomeHero.vue` and `welcomeContent.js` do not exist.

- [ ] **Step 3: Create the exact static content module**

Create `frontend/src/views/welcome/welcomeContent.js`:

```js
export const heroCodeLines = [
  { n: '01', html: '<span class="kw">import</span> numpy <span class="kw">as</span> np' },
  { n: '02', html: '<span class="kw">from</span> sklearn.model_selection <span class="kw">import</span> train_test_split' },
  { n: '03', html: '' },
  { n: '04', html: 'dataset = <span class="fn">load_experiment_data</span>(<span class="str">"iris"</span>)' },
  { n: '05', html: 'X_train, X_test, y_train, y_test = <span class="fn">train_test_split</span>(dataset)' },
  { n: '06', html: 'model = <span class="fn">build_classifier</span>(layers=[<span class="num">64</span>, <span class="num">32</span>, <span class="num">3</span>])' },
  { n: '07', html: 'history = model.<span class="fn">fit</span>(X_train, y_train, epochs=<span class="num">20</span>)' },
  { n: '08', html: 'predictions = model.<span class="fn">predict</span>(X_test)' },
  { n: '09', html: 'accuracy = <span class="fn">evaluate</span>(predictions, y_test)' },
  { n: '10', html: '<span class="fn">print</span>(<span class="str">f"实验完成 · 准确率 {accuracy:.1%}"</span>)' },
]

export const capabilities = [
  {
    id: 'coding',
    label: 'LIVE CODING',
    title: '在线编程实验',
    description: '在浏览器中运行 Python、查看输出、提交结果，并获得即时反馈。',
    motion: 'equalizer',
    featured: true,
  },
  {
    id: 'course',
    label: 'COURSE',
    title: '课程与课时',
    description: '结构化课程内容、章节进度与学习路径统一承接。',
    motion: 'progress',
  },
  {
    id: 'notebook',
    label: 'NOTEBOOK',
    title: '交互式 Notebook',
    description: '代码、说明、运行结果与实验记录在同一工作台中完成。',
    motion: 'cursor',
  },
  {
    id: 'assessment',
    label: 'ASSESSMENT + AI REVIEW',
    title: '作业、考试、自动判题与 AI 评分',
    description: '从提交、用例判定到 AI 反馈和教师复核，形成完整评价链路。',
    motion: 'signal',
    wide: true,
  },
]

export const learningSteps = [
  { number: '01', title: '学习', caption: '课程与课时' },
  { number: '02', title: '实验', caption: '代码与 Notebook' },
  { number: '03', title: '提交', caption: '作业与考试' },
  { number: '04', title: '评测', caption: '自动判题 + AI' },
  { number: '05', title: '进步', caption: '反馈与复盘' },
]

export const roleScenes = [
  { id: 'student', label: 'STUDENT', title: '学生学习台', detail: '学习、实验、作业、考试与反馈' },
  { id: 'teacher', label: 'TEACHER', title: '教学工作台', detail: '课程建设、题目配置、成绩与 AI 复核' },
  { id: 'admin', label: 'ADMIN', title: '平台管理', detail: '用户、课程与资源管理' },
  { id: 'developer', label: 'DEVELOPER', title: '实验模板', detail: '模板编排与 Studio 工作台' },
]
```

Use `v-html` only for the hard-coded `heroCodeLines` strings from this local module. Do not accept runtime or user-provided HTML.

- [ ] **Step 4: Verify the content module and keep the red test local**

```bash
cd frontend
node -e "import('./src/views/welcome/welcomeContent.js').then((m) => { if (m.heroCodeLines.length !== 10 || m.capabilities.length !== 4 || m.learningSteps.length !== 5 || m.roleScenes.length !== 4) process.exit(1) })"
```

Expected: exit code 0. Do not commit a state where `WelcomeHero.spec.js` still fails; carry these two files into Task 4.

### Task 3: Build and Test One-Shot Reveal Behavior

**Files:**

- Create: `frontend/src/composables/useReveal.js`
- Create: `frontend/src/composables/__tests__/useReveal.spec.js`

- [ ] **Step 1: Write the failing composable tests**

Create `frontend/src/composables/__tests__/useReveal.spec.js`:

```js
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { useReveal } from '../useReveal.js'

const Host = defineComponent({
  setup() {
    const { target, isVisible } = useReveal()
    return { target, isVisible }
  },
  template: '<section ref="target" :data-visible="String(isVisible)">Content</section>',
})

describe('useReveal', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('reveals immediately when IntersectionObserver is unavailable', async () => {
    vi.stubGlobal('IntersectionObserver', undefined)
    const wrapper = mount(Host)
    await nextTick()
    expect(wrapper.get('section').attributes('data-visible')).toBe('true')
  })

  it('reveals once and disconnects after intersection', async () => {
    let callback
    const observe = vi.fn()
    const disconnect = vi.fn()

    vi.stubGlobal('IntersectionObserver', class {
      constructor(cb) {
        callback = cb
      }
      observe = observe
      disconnect = disconnect
    })

    const wrapper = mount(Host)
    await nextTick()
    expect(observe).toHaveBeenCalledTimes(1)

    callback([{ isIntersecting: true }])
    await nextTick()

    expect(wrapper.get('section').attributes('data-visible')).toBe('true')
    expect(disconnect).toHaveBeenCalledTimes(1)
  })
})
```

- [ ] **Step 2: Run the composable test and verify failure**

Run:

```bash
cd frontend
npm.cmd test -- src/composables/__tests__/useReveal.spec.js
```

Expected: FAIL because `useReveal.js` does not exist.

- [ ] **Step 3: Implement the composable**

Create `frontend/src/composables/useReveal.js`:

```js
import { onBeforeUnmount, onMounted, ref } from 'vue'

export function useReveal(options = {}) {
  const target = ref(null)
  const isVisible = ref(false)
  let observer = null

  onMounted(() => {
    if (typeof window.IntersectionObserver !== 'function') {
      isVisible.value = true
      return
    }

    observer = new window.IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return
        isVisible.value = true
        observer?.disconnect()
        observer = null
      },
      {
        threshold: options.threshold ?? 0.16,
        rootMargin: options.rootMargin ?? '0px 0px -8% 0px',
      },
    )

    if (target.value) observer.observe(target.value)
  })

  onBeforeUnmount(() => {
    observer?.disconnect()
    observer = null
  })

  return { target, isVisible }
}
```

- [ ] **Step 4: Run the composable test and commit**

Run:

```bash
cd frontend
npm.cmd test -- src/composables/__tests__/useReveal.spec.js
```

Expected: 2 tests PASS.

Commit:

```bash
git add frontend/src/composables/useReveal.js frontend/src/composables/__tests__/useReveal.spec.js
git commit -m "feat: add welcome section reveal behavior"
```

### Task 4: Implement the Animated Hero

**Files:**

- Create: `frontend/src/components/welcome/WelcomeHero.vue`
- Test: `frontend/src/components/welcome/__tests__/WelcomeHero.spec.js`

- [ ] **Step 1: Create the semantic hero component**

Create `frontend/src/components/welcome/WelcomeHero.vue` with:

```vue
<script setup>
defineProps({
  codeLines: {
    type: Array,
    required: true,
  },
})

defineEmits(['explore', 'login'])
</script>

<template>
  <main class="welcome-hero">
    <div class="hero-grid" aria-hidden="true"></div>
    <div class="hero-copy">
      <p class="hero-label">LIVE AI LAB</p>
      <h1>从代码开始，<span>探索 AI 世界</span></h1>
      <p class="hero-description">
        课程学习、在线编程、Notebook、自动判题、考试与 AI 评分，
        在一个持续运转的学习工作台里完整呈现。
      </p>
      <div class="hero-actions">
        <button data-testid="hero-explore" class="primary-action" @click="$emit('explore')">
          探索平台能力
          <span aria-hidden="true">→</span>
        </button>
        <button data-testid="login-action" class="secondary-action" @click="$emit('login')">
          立即登录
        </button>
      </div>
    </div>

    <div class="product-stage" aria-label="Python 实验运行演示">
      <section class="code-window">
        <header class="code-toolbar">
          <span>experiment.py</span>
          <span class="running-state"><i aria-hidden="true"></i> RUNNING</span>
        </header>
        <div class="code-body">
          <template v-for="line in codeLines" :key="line.n">
            <span class="line-number">{{ line.n }}</span>
            <code data-testid="code-line" class="code-line" v-html="line.html"></code>
          </template>
        </div>
        <footer class="code-output">
          <span><b>✓</b> 实验完成</span>
          <span><em>20 / 20</em> 训练轮次</span>
          <span><strong>98.6%</strong> 测试准确率</span>
          <span><b>✓</b> 全部测试通过</span>
        </footer>
      </section>

      <aside class="score-window" aria-label="AI 代码评分">
        <span>AI 代码评分</span>
        <div class="score-row"><strong>98.6</strong><b>优秀 ↑</b></div>
        <div class="score-track"><i></i></div>
        <small>结构清晰 · 测试全部通过</small>
      </aside>
    </div>
  </main>
</template>
```

- [ ] **Step 2: Add the approved hero styling and motion**

Add scoped CSS to the same component using these exact behavior rules:

```css
.welcome-hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, .92fr) minmax(520px, 1.08fr);
  align-items: center;
  gap: 56px;
  min-height: 700px;
  padding: 76px max(40px, calc((100vw - 1180px) / 2));
  overflow: hidden;
  background:
    radial-gradient(circle at 87% 12%, rgba(115, 89, 237, .17), transparent 26%),
    radial-gradient(circle at 12% 78%, rgba(54, 197, 255, .12), transparent 28%),
    #f8faff;
}

.hero-copy,
.product-stage { position: relative; z-index: 2; }

.hero-copy h1 {
  margin: 16px 0 18px;
  color: #13213a;
  font: 850 clamp(48px, 5vw, 72px) / 1.02 "Segoe UI Variable Display", "PingFang SC", "Microsoft YaHei", sans-serif;
  letter-spacing: -.06em;
}

.hero-copy h1 span {
  color: transparent;
  background: linear-gradient(90deg, #2467ed, #7359ed, #2467ed);
  background-size: 200% 100%;
  background-clip: text;
  animation: title-flow 7s linear infinite;
}

.product-stage { min-height: 440px; }
.code-window,
.score-window {
  border: 1px solid rgba(52, 82, 132, .16);
  border-radius: 16px;
  transform: translate3d(0, 0, 0);
}

.code-window {
  position: absolute;
  inset: 0 34px 42px 0;
  overflow: hidden;
  color: #c8d6ea;
  background: #14213b;
  box-shadow: 0 30px 70px rgba(20, 42, 80, .24);
  animation: panel-float 5.2s ease-in-out infinite;
}

.score-window {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 250px;
  padding: 18px;
  color: #13213a;
  background: rgba(255, 255, 255, .96);
  box-shadow: 0 22px 46px rgba(33, 65, 116, .18);
  animation: score-enter 7s ease-in-out infinite;
}

@keyframes panel-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-7px); }
}

@keyframes score-enter {
  0%, 34% { opacity: 0; transform: translateY(14px); }
  50%, 92% { opacity: 1; transform: translateY(0); }
  100% { opacity: 0; transform: translateY(6px); }
}

@keyframes title-flow {
  to { background-position: -200% 0; }
}

@media (max-width: 960px) {
  .welcome-hero {
    grid-template-columns: 1fr;
    min-height: auto;
    padding: 72px 28px 54px;
  }
  .product-stage { min-height: 430px; }
}

@media (prefers-reduced-motion: reduce) {
  .hero-copy h1 span,
  .code-window,
  .score-window { animation: none; }
  .score-window { opacity: 1; transform: none; }
}
```

Add the remaining hero selectors with these fixed values:

```css
.hero-grid {
  position: absolute;
  inset: -40px;
  background-image:
    linear-gradient(rgba(58, 86, 136, .055) 1px, transparent 1px),
    linear-gradient(90deg, rgba(58, 86, 136, .055) 1px, transparent 1px);
  background-size: 28px 28px;
  mask-image: radial-gradient(circle at 62% 48%, #000, transparent 72%);
  animation: grid-drift 16s linear infinite;
}

.hero-label {
  display: flex;
  align-items: center;
  gap: 9px;
  margin: 0;
  color: #2467ed;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .16em;
}

.hero-label::before {
  content: "";
  width: 26px;
  height: 2px;
  background: currentColor;
}

.hero-description {
  max-width: 580px;
  margin: 0;
  color: #6e7b92;
  font-size: 17px;
  line-height: 1.8;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 28px;
}

.primary-action,
.secondary-action {
  min-height: 50px;
  padding: 0 20px;
  border-radius: 10px;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.primary-action {
  border: 1px solid #2467ed;
  color: #fff;
  background: #2467ed;
  box-shadow: 0 12px 28px rgba(36, 103, 237, .26);
}

.secondary-action {
  border: 1px solid rgba(42, 74, 126, .16);
  color: #13213a;
  background: rgba(255, 255, 255, .76);
}

.primary-action:hover,
.secondary-action:hover { transform: translateY(-2px); }

.primary-action:focus-visible,
.secondary-action:focus-visible {
  outline: 3px solid rgba(36, 103, 237, .28);
  outline-offset: 3px;
}

.code-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, .08);
  color: #94a8c6;
  font: 11px/1 var(--font-mono);
}

.running-state {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #58dda7;
}

.running-state i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #58dda7;
  animation: status-pulse 1.6s ease-out infinite;
}

.code-body {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  padding: 18px 22px 86px;
  font: 11px/2.05 var(--font-mono);
}

.line-number {
  padding-right: 13px;
  color: #5e708d;
  text-align: right;
}

.code-line {
  min-width: 0;
  overflow-wrap: anywhere;
  color: #aebfd7;
  animation: code-reveal 7s ease-in-out infinite;
}

.code-line:nth-of-type(2n) { animation-delay: 160ms; }
:deep(.kw) { color: #c39cff; }
:deep(.fn) { color: #68d7ff; }
:deep(.str) { color: #82dda9; }
:deep(.num) { color: #ffca7a; }

.code-output {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border-top: 1px solid rgba(255, 255, 255, .08);
  background: #0d192c;
}

.code-output span {
  padding: 14px 12px;
  border-right: 1px solid rgba(255, 255, 255, .06);
  color: #92a4be;
  font: 10px/1.35 var(--font-mono);
}

.code-output b { color: #58dda7; }
.code-output em { color: #68d7ff; font-style: normal; }
.code-output strong { color: #ffca7a; }

.score-row {
  display: flex;
  align-items: end;
  justify-content: space-between;
  margin-top: 10px;
}

.score-row strong {
  color: #2467ed;
  font-size: 36px;
  line-height: 1;
  letter-spacing: -.05em;
}

.score-row b { color: #14926e; font-size: 12px; }

.score-track {
  height: 5px;
  margin: 12px 0 10px;
  overflow: hidden;
  border-radius: 99px;
  background: #e6ecf6;
}

.score-track i {
  display: block;
  width: 88%;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2467ed, #7359ed);
  transform-origin: left;
  animation: score-fill 7s ease-in-out infinite;
}

@keyframes grid-drift { to { transform: translate3d(28px, 28px, 0); } }
@keyframes status-pulse {
  0% { box-shadow: 0 0 0 0 rgba(88, 221, 167, .5); }
  82%, 100% { box-shadow: 0 0 0 10px rgba(88, 221, 167, 0); }
}
@keyframes code-reveal {
  0%, 10% { opacity: .28; transform: translateX(-4px); }
  24%, 82% { opacity: 1; transform: translateX(0); }
  100% { opacity: .38; }
}
@keyframes score-fill {
  0%, 44% { transform: scaleX(0); }
  64%, 92% { transform: scaleX(1); }
  100% { transform: scaleX(0); }
}

@media (max-width: 600px) {
  .hero-copy h1 { font-size: clamp(42px, 14vw, 58px); }
  .product-stage { min-height: 520px; }
  .code-window { inset: 0 0 92px; }
  .score-window { right: 12px; bottom: 0; width: min(250px, calc(100% - 24px)); }
  .code-body { padding: 16px 14px 108px; font-size: 9px; }
  .code-output { grid-template-columns: 1fr 1fr; }
}

@media (prefers-reduced-motion: reduce) {
  .hero-grid,
  .running-state i,
  .code-line,
  .score-track i { animation: none; }
  .code-line { opacity: 1; transform: none; }
  .score-track i { transform: none; }
}
```

- [ ] **Step 3: Run the hero tests and verify green**

Run:

```bash
cd frontend
npm.cmd test -- src/components/welcome/__tests__/WelcomeHero.spec.js
```

Expected: 2 tests PASS.

- [ ] **Step 4: Commit the hero**

```bash
git add frontend/src/views/welcome/welcomeContent.js frontend/src/components/welcome/WelcomeHero.vue frontend/src/components/welcome/__tests__/WelcomeHero.spec.js
git commit -m "feat: build animated welcome hero"
```

### Task 5: Implement the Capability Gallery

**Files:**

- Create: `frontend/src/components/welcome/CapabilityShowcase.vue`
- Create: `frontend/src/components/welcome/__tests__/CapabilityShowcase.spec.js`

- [ ] **Step 1: Write the failing capability test**

```js
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import CapabilityShowcase from '../CapabilityShowcase.vue'
import { capabilities } from '../../../views/welcome/welcomeContent.js'

describe('CapabilityShowcase', () => {
  it('renders each capability with a distinct motion contract', () => {
    const wrapper = mount(CapabilityShowcase, {
      props: { capabilities },
    })

    const blocks = wrapper.findAll('[data-testid="capability-block"]')
    expect(blocks).toHaveLength(4)
    expect(blocks.map((block) => block.attributes('data-motion'))).toEqual([
      'equalizer',
      'progress',
      'cursor',
      'signal',
    ])
    expect(wrapper.text()).toContain('自动判题与 AI 评分')
  })
})
```

- [ ] **Step 2: Run the test and verify failure**

Run:

```bash
cd frontend
npm.cmd test -- src/components/welcome/__tests__/CapabilityShowcase.spec.js
```

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement the gallery structure**

Use the following component contract:

```vue
<script setup>
import { useReveal } from '../../composables/useReveal.js'

defineProps({
  capabilities: {
    type: Array,
    required: true,
  },
})

const { target, isVisible } = useReveal()
</script>

<template>
  <section
    id="capabilities"
    ref="target"
    class="capability-section reveal-section"
    :class="{ 'is-visible': isVisible }"
  >
    <header class="section-heading">
      <p>02 / CAPABILITIES</p>
      <h2>不止写代码，而是完整实验链路</h2>
      <span>课程、实验、Notebook、作业、考试、判题和 AI 反馈在同一平台衔接。</span>
    </header>

    <div class="capability-layout">
      <article
        v-for="capability in capabilities"
        :key="capability.id"
        data-testid="capability-block"
        class="capability-block"
        :class="{ featured: capability.featured, wide: capability.wide }"
        :data-motion="capability.motion"
        tabindex="0"
      >
        <span class="capability-label">{{ capability.label }}</span>
        <h3>{{ capability.title }}</h3>
        <p>{{ capability.description }}</p>
        <div class="micro-motion" aria-hidden="true">
          <i v-for="index in 5" :key="index"></i>
        </div>
      </article>
    </div>
  </section>
</template>
```

Add scoped CSS with this base layout:

```css
.capability-section {
  padding: 96px max(28px, calc((100vw - 1180px) / 2));
  background: #fff;
}

.section-heading {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(260px, .9fr);
  column-gap: 48px;
  align-items: end;
  margin-bottom: 38px;
}

.section-heading p {
  grid-column: 1 / -1;
  margin: 0 0 10px;
  color: #2467ed;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: .14em;
}

.section-heading h2 {
  margin: 0;
  color: #13213a;
  font-size: clamp(34px, 4vw, 52px);
  line-height: 1.08;
  letter-spacing: -.045em;
}

.section-heading > span {
  color: #6e7b92;
  font-size: 15px;
  line-height: 1.7;
}

.reveal-section {
  opacity: 0;
  transform: translateY(22px);
  transition: opacity 520ms ease, transform 520ms cubic-bezier(.2, .8, .2, 1);
}

.reveal-section.is-visible { opacity: 1; transform: none; }

.capability-layout {
  display: grid;
  grid-template-columns: 1.2fr 1fr 1fr;
  grid-template-rows: repeat(2, minmax(180px, auto));
  gap: 14px;
}

.capability-block {
  position: relative;
  overflow: hidden;
  padding: 28px;
  border: 1px solid rgba(42, 74, 126, .12);
  border-radius: 16px;
  background: rgba(255, 255, 255, .9);
  transition: transform 240ms cubic-bezier(.2, .8, .2, 1), box-shadow 240ms ease, border-color 240ms ease;
}

.capability-block.featured {
  grid-row: 1 / 3;
  color: #fff;
  background: linear-gradient(145deg, #2467ed, #7359ed);
}

.capability-block.wide { grid-column: 2 / 4; }

.capability-block:hover,
.capability-block:focus-visible {
  transform: translateY(-8px);
  border-color: rgba(36, 103, 237, .38);
  box-shadow: 0 24px 46px rgba(35, 68, 120, .14);
  outline: none;
}

@media (max-width: 760px) {
  .section-heading { grid-template-columns: 1fr; }
  .section-heading > span { margin-top: 14px; }
  .capability-layout { grid-template-columns: 1fr; grid-template-rows: auto; }
  .capability-block.featured,
  .capability-block.wide { grid-column: auto; grid-row: auto; }
}

@media (prefers-reduced-motion: reduce) {
  .reveal-section { opacity: 1; transform: none; transition: none; }
}
```

Add the four distinct hover/focus animations without rotation:

```css
.micro-motion {
  position: absolute;
  right: 24px;
  bottom: 22px;
  left: 24px;
  height: 36px;
}

[data-motion="equalizer"] .micro-motion {
  display: flex;
  align-items: end;
  gap: 6px;
}

[data-motion="equalizer"] .micro-motion i {
  width: 7px;
  height: 8px;
  border-radius: 99px;
  background: currentColor;
  opacity: .34;
}

[data-motion="equalizer"]:hover .micro-motion i,
[data-motion="equalizer"]:focus-visible .micro-motion i {
  animation: equalize .7s ease-in-out infinite alternate;
}

[data-motion="equalizer"] .micro-motion i:nth-child(2) { animation-delay: -140ms; }
[data-motion="equalizer"] .micro-motion i:nth-child(3) { animation-delay: -280ms; }
[data-motion="equalizer"] .micro-motion i:nth-child(4) { animation-delay: -420ms; }

[data-motion="progress"] .micro-motion {
  top: auto;
  height: 5px;
  overflow: hidden;
  border-radius: 99px;
  background: #e7edf7;
}

[data-motion="progress"] .micro-motion i:first-child {
  display: block;
  width: 42%;
  height: 100%;
  border-radius: inherit;
  background: #2467ed;
  transition: width 460ms cubic-bezier(.2, .8, .2, 1);
}

[data-motion="progress"]:hover .micro-motion i:first-child,
[data-motion="progress"]:focus-visible .micro-motion i:first-child { width: 92%; }

[data-motion="cursor"] .micro-motion i:first-child {
  position: absolute;
  right: 0;
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: #7359ed;
  transition: transform 280ms cubic-bezier(.2, .8, .2, 1);
}

[data-motion="cursor"]:hover .micro-motion i:first-child,
[data-motion="cursor"]:focus-visible .micro-motion i:first-child { transform: translateX(-24px); }

[data-motion="signal"] .micro-motion {
  top: auto;
  height: 1px;
  background: #dce4f1;
}

[data-motion="signal"] .micro-motion i:first-child {
  position: absolute;
  top: -4px;
  left: 0;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #58dda7;
  box-shadow: 0 0 14px rgba(88, 221, 167, .62);
}

[data-motion="signal"]:hover .micro-motion i:first-child,
[data-motion="signal"]:focus-visible .micro-motion i:first-child {
  animation: signal-run 1.4s ease-in-out infinite;
}

@keyframes equalize { to { height: 28px; opacity: .82; } }
@keyframes signal-run {
  0%, 100% { left: 0; }
  50% { left: calc(100% - 9px); }
}

@media (prefers-reduced-motion: reduce) {
  .capability-block,
  .micro-motion i { animation: none !important; transition: none !important; }
}
```

- [ ] **Step 4: Run the test and commit**

Run:

```bash
cd frontend
npm.cmd test -- src/components/welcome/__tests__/CapabilityShowcase.spec.js
```

Expected: 1 test PASS.

Commit:

```bash
git add frontend/src/components/welcome/CapabilityShowcase.vue frontend/src/components/welcome/__tests__/CapabilityShowcase.spec.js
git commit -m "feat: add interactive capability gallery"
```

### Task 6: Implement Learning and Role Sections

**Files:**

- Create: `frontend/src/components/welcome/LearningFlow.vue`
- Create: `frontend/src/components/welcome/RoleShowcase.vue`
- Create: `frontend/src/components/welcome/__tests__/LearningFlow.spec.js`
- Create: `frontend/src/components/welcome/__tests__/RoleShowcase.spec.js`

- [ ] **Step 1: Write both failing tests**

`LearningFlow.spec.js`:

```js
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import LearningFlow from '../LearningFlow.vue'
import { learningSteps } from '../../../views/welcome/welcomeContent.js'

describe('LearningFlow', () => {
  it('renders the complete five-step loop', () => {
    const wrapper = mount(LearningFlow, { props: { steps: learningSteps } })
    expect(wrapper.findAll('[data-testid="learning-step"]')).toHaveLength(5)
    expect(wrapper.text()).toContain('学习')
    expect(wrapper.text()).toContain('自动判题 + AI')
    expect(wrapper.text()).toContain('反馈与复盘')
  })
})
```

`RoleShowcase.spec.js`:

```js
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RoleShowcase from '../RoleShowcase.vue'
import { roleScenes } from '../../../views/welcome/welcomeContent.js'

describe('RoleShowcase', () => {
  it('renders all platform roles', () => {
    const wrapper = mount(RoleShowcase, { props: { roles: roleScenes } })
    expect(wrapper.findAll('[data-testid="role-scene"]')).toHaveLength(4)
    expect(wrapper.text()).toContain('学生学习台')
    expect(wrapper.text()).toContain('教学工作台')
    expect(wrapper.text()).toContain('平台管理')
    expect(wrapper.text()).toContain('实验模板')
  })
})
```

- [ ] **Step 2: Run both tests and verify failure**

Run:

```bash
cd frontend
npm.cmd test -- src/components/welcome/__tests__/LearningFlow.spec.js src/components/welcome/__tests__/RoleShowcase.spec.js
```

Expected: FAIL because both components do not exist.

- [ ] **Step 3: Implement `LearningFlow.vue`**

The component must:

```vue
<script setup>
import { useReveal } from '../../composables/useReveal.js'

defineProps({
  steps: {
    type: Array,
    required: true,
  },
})

const { target, isVisible } = useReveal({ threshold: 0.24 })
</script>

<template>
  <section
    id="learning-flow"
    ref="target"
    class="learning-flow reveal-section"
    :class="{ 'is-visible': isVisible }"
  >
    <header class="section-heading inverse">
      <p>03 / LEARNING LOOP</p>
      <h2>让成长过程像一条运行中的数据流</h2>
    </header>
    <div class="flow-track">
      <article v-for="step in steps" :key="step.number" data-testid="learning-step" class="flow-step">
        <i>{{ step.number }}</i>
        <h3>{{ step.title }}</h3>
        <p>{{ step.caption }}</p>
      </article>
    </div>
  </section>
</template>
```

Add this scoped styling for the dark transition band and responsive track:

```css
.learning-flow {
  padding: 92px max(28px, calc((100vw - 1180px) / 2));
  color: #eef5ff;
  background:
    radial-gradient(circle at 50% 100%, rgba(36, 103, 237, .18), transparent 38%),
    #14213b;
}

.learning-flow.reveal-section {
  opacity: 0;
  transform: translateY(22px);
  transition: opacity 520ms ease, transform 520ms cubic-bezier(.2, .8, .2, 1);
}

.learning-flow.reveal-section.is-visible { opacity: 1; transform: none; }

.section-heading.inverse p { color: #68d7ff; }
.section-heading.inverse h2 { margin: 10px 0 0; font-size: clamp(34px, 4vw, 52px); letter-spacing: -.045em; }

.flow-track {
  position: relative;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin-top: 54px;
}

.flow-track::before {
  content: "";
  position: absolute;
  top: 22px;
  right: 10%;
  left: 10%;
  height: 2px;
  background: linear-gradient(90deg, #68d7ff, #7359ed, #68d7ff);
  box-shadow: 0 0 16px rgba(104, 215, 255, .46);
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 900ms cubic-bezier(.2, .8, .2, 1);
}

.learning-flow.is-visible .flow-track::before { transform: scaleX(1); }

.flow-step { position: relative; z-index: 1; text-align: center; }
.flow-step i {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  margin: 0 auto;
  border: 1px solid rgba(104, 215, 255, .42);
  border-radius: 50%;
  color: #68d7ff;
  background: #14213b;
  font: 11px var(--font-mono);
}
.flow-step h3 { margin: 14px 0 4px; font-size: 16px; }
.flow-step p { margin: 0; color: #8fa0ba; font-size: 12px; }

@media (max-width: 680px) {
  .flow-track { grid-template-columns: 1fr; gap: 24px; margin-top: 38px; }
  .flow-track::before {
    top: 22px;
    bottom: 22px;
    left: 21px;
    width: 2px;
    height: auto;
    transform: scaleY(0);
    transform-origin: top;
  }
  .learning-flow.is-visible .flow-track::before { transform: scaleY(1); }
  .flow-step {
    display: grid;
    grid-template-columns: 44px 1fr;
    column-gap: 14px;
    text-align: left;
  }
  .flow-step i { grid-row: 1 / 3; margin: 0; }
  .flow-step h3 { margin: 2px 0 3px; }
}

@media (prefers-reduced-motion: reduce) {
  .learning-flow.reveal-section { opacity: 1; transform: none; transition: none; }
  .flow-track::before { transition: none; transform: none; }
}
```

- [ ] **Step 4: Implement `RoleShowcase.vue`**

The component must:

```vue
<script setup>
import { useReveal } from '../../composables/useReveal.js'

defineProps({
  roles: {
    type: Array,
    required: true,
  },
})

const { target, isVisible } = useReveal()
</script>

<template>
  <section
    id="role-scenes"
    ref="target"
    class="role-section reveal-section"
    :class="{ 'is-visible': isVisible }"
  >
    <header class="section-heading">
      <p>04 / EVERY ROLE</p>
      <h2>学生在这里成长，团队在这里构建实验</h2>
      <span>从学习端到教学、管理和模板开发，平台为每个角色提供清晰工作台。</span>
    </header>
    <div class="role-grid">
      <article v-for="role in roles" :key="role.id" data-testid="role-scene" class="role-scene">
        <span>{{ role.label }}</span>
        <h3>{{ role.title }}</h3>
        <p>{{ role.detail }}</p>
        <div class="role-preview" :data-role="role.id" aria-hidden="true">
          <i></i><i></i><i></i>
        </div>
      </article>
    </div>
  </section>
</template>
```

Add this scoped styling for four product-scene previews:

```css
.role-section {
  padding: 96px max(28px, calc((100vw - 1180px) / 2));
  background: #f8faff;
}

.role-section.reveal-section {
  opacity: 0;
  transform: translateY(22px);
  transition: opacity 520ms ease, transform 520ms cubic-bezier(.2, .8, .2, 1);
}

.role-section.reveal-section.is-visible { opacity: 1; transform: none; }

.role-section .section-heading p {
  margin: 0 0 10px;
  color: #2467ed;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: .14em;
}

.role-section .section-heading h2 {
  margin: 0;
  color: #13213a;
  font-size: clamp(34px, 4vw, 52px);
  line-height: 1.08;
  letter-spacing: -.045em;
}

.role-section .section-heading > span {
  display: block;
  max-width: 680px;
  margin-top: 14px;
  color: #6e7b92;
  font-size: 15px;
  line-height: 1.7;
}

.role-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-top: 38px;
}

.role-scene {
  min-width: 0;
  padding: 24px;
  border: 1px solid rgba(42, 74, 126, .12);
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 16px 34px rgba(40, 70, 120, .07);
}

.role-scene > span { color: #2467ed; font-size: 10px; font-weight: 800; letter-spacing: .12em; }
.role-scene h3 { margin: 10px 0 7px; color: #13213a; font-size: 18px; }
.role-scene p { min-height: 46px; margin: 0; color: #6e7b92; font-size: 12px; line-height: 1.6; }

.role-preview {
  position: relative;
  height: 128px;
  margin-top: 22px;
  overflow: hidden;
  border: 1px solid #dde5f1;
  border-radius: 11px;
  background: #f5f8fd;
}

.role-preview::before {
  content: "";
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 28%;
  background: #14213b;
}

.role-preview i {
  position: absolute;
  right: 10px;
  left: calc(28% + 10px);
  height: 12px;
  border-radius: 4px;
  background: #dfe7f3;
}

.role-preview i:nth-child(1) { top: 18px; background: rgba(36, 103, 237, .24); }
.role-preview i:nth-child(2) { top: 42px; width: 45%; }
.role-preview i:nth-child(3) { top: 72px; height: 36px; background: #fff; box-shadow: inset 0 0 0 1px #dfe7f3; }

.role-preview[data-role="teacher"] i:nth-child(1) { background: rgba(115, 89, 237, .25); }
.role-preview[data-role="admin"] i:nth-child(1) { background: rgba(88, 221, 167, .28); }
.role-preview[data-role="developer"] i:nth-child(3) { background: #14213b; box-shadow: none; }

@media (max-width: 920px) {
  .role-grid { grid-template-columns: 1fr 1fr; }
}

@media (max-width: 560px) {
  .role-grid { grid-template-columns: 1fr; }
  .role-scene p { min-height: auto; }
}

@media (prefers-reduced-motion: reduce) {
  .role-section.reveal-section { opacity: 1; transform: none; transition: none; }
}
```

- [ ] **Step 5: Run both tests and commit**

Run:

```bash
cd frontend
npm.cmd test -- src/components/welcome/__tests__/LearningFlow.spec.js src/components/welcome/__tests__/RoleShowcase.spec.js
```

Expected: 2 tests PASS.

Commit:

```bash
git add frontend/src/components/welcome/LearningFlow.vue frontend/src/components/welcome/RoleShowcase.vue frontend/src/components/welcome/__tests__/LearningFlow.spec.js frontend/src/components/welcome/__tests__/RoleShowcase.spec.js
git commit -m "feat: add learning loop and role scenes"
```

### Task 7: Compose the Route Page and Navigation

**Files:**

- Modify: `frontend/src/views/WelcomeView.vue`
- Create: `frontend/src/views/__tests__/WelcomeView.spec.js`

- [ ] **Step 1: Write failing route-page interaction tests**

Create `frontend/src/views/__tests__/WelcomeView.spec.js`:

```js
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import WelcomeView from '../WelcomeView.vue'

const routerState = vi.hoisted(() => ({
  push: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: routerState.push }),
}))

describe('WelcomeView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.HTMLElement.prototype.scrollIntoView = vi.fn()
  })

  it('routes every login action to /login', async () => {
    const wrapper = mount(WelcomeView)
    const loginButtons = wrapper.findAll('[data-testid="login-action"]')
    expect(loginButtons.length).toBeGreaterThanOrEqual(2)

    for (const button of loginButtons) {
      await button.trigger('click')
    }

    for (let index = 0; index < loginButtons.length; index += 1) {
      expect(routerState.push).toHaveBeenNthCalledWith(index + 1, '/login')
    }
  })

  it('scrolls to the capability section from the hero', async () => {
    const wrapper = mount(WelcomeView, { attachTo: document.body })
    await wrapper.get('[data-testid="hero-explore"]').trigger('click')

    const target = wrapper.get('#capabilities').element
    expect(target.scrollIntoView).toHaveBeenCalledWith({
      behavior: 'smooth',
      block: 'start',
    })

    wrapper.unmount()
  })
})
```

- [ ] **Step 2: Run the view test and verify red**

Run:

```bash
cd frontend
npm.cmd test -- src/views/__tests__/WelcomeView.spec.js
```

Expected: FAIL because the existing page does not expose the new test contracts.

- [ ] **Step 3: Replace `WelcomeView.vue` with the new composition**

Use this script and component order:

```vue
<script setup>
import { useRouter } from 'vue-router'
import WelcomeHero from '../components/welcome/WelcomeHero.vue'
import CapabilityShowcase from '../components/welcome/CapabilityShowcase.vue'
import LearningFlow from '../components/welcome/LearningFlow.vue'
import RoleShowcase from '../components/welcome/RoleShowcase.vue'
import {
  capabilities,
  heroCodeLines,
  learningSteps,
  roleScenes,
} from './welcome/welcomeContent.js'

const router = useRouter()

function goLogin() {
  router.push('/login')
}

function scrollToSection(id) {
  document.getElementById(id)?.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  })
}
</script>

<template>
  <div class="welcome-page">
    <header class="welcome-nav">
      <button class="brand" type="button" @click="scrollToSection('top')">
        <span class="brand-mark" aria-hidden="true">DAI</span>
        <span><b>人工智能实验平台</b><small>AI Experiment Studio</small></span>
      </button>
      <nav aria-label="欢迎页导航">
        <button @click="scrollToSection('capabilities')">平台能力</button>
        <button @click="scrollToSection('learning-flow')">学习闭环</button>
        <button @click="scrollToSection('role-scenes')">角色场景</button>
      </nav>
      <button data-testid="login-action" class="nav-login" @click="goLogin">进入平台 →</button>
    </header>

    <div id="top"></div>
    <WelcomeHero
      :code-lines="heroCodeLines"
      @explore="scrollToSection('capabilities')"
      @login="goLogin"
    />
    <CapabilityShowcase :capabilities="capabilities" />
    <LearningFlow :steps="learningSteps" />
    <RoleShowcase :roles="roleScenes" />

    <section class="final-cta">
      <h2>让每一次实验，都成为看得见的成长</h2>
      <p>从课程学习到 AI 评分，在一个平台完成完整实验闭环。</p>
      <button data-testid="login-action" @click="goLogin">进入实验平台 →</button>
    </section>

    <footer class="welcome-footer">
      <span>© 2026 人工智能实验平台</span>
      <span>Built for learners, teachers and builders.</span>
    </footer>
  </div>
</template>
```

- [ ] **Step 4: Add route-page shared styling**

Use local scoped CSS in `WelcomeView.vue`:

```css
.welcome-page {
  min-height: 100vh;
  overflow-x: clip;
  color: #13213a;
  background: #f8faff;
  font-family: "Segoe UI Variable Text", "PingFang SC", "Microsoft YaHei", sans-serif;
}

.welcome-nav {
  position: sticky;
  top: 0;
  z-index: 30;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  min-height: 72px;
  padding: 0 max(28px, calc((100vw - 1180px) / 2));
  border-bottom: 1px solid rgba(42, 74, 126, .1);
  background: rgba(248, 250, 255, .82);
  backdrop-filter: blur(18px);
}

.nav-login { justify-self: end; }

.final-cta {
  padding: 92px 28px;
  text-align: center;
  color: #fff;
  background:
    radial-gradient(circle at 50% 100%, rgba(88, 221, 167, .2), transparent 36%),
    linear-gradient(130deg, #2467ed, #7359ed);
}

.final-cta h2 {
  margin: 0;
  font: 850 clamp(34px, 4vw, 56px) / 1.08 "Segoe UI Variable Display", "PingFang SC", "Microsoft YaHei", sans-serif;
  letter-spacing: -.05em;
}

@supports not (backdrop-filter: blur(18px)) {
  .welcome-nav { background: #f8faff; }
}

@media (max-width: 760px) {
  .welcome-nav {
    grid-template-columns: 1fr auto;
    min-height: 64px;
    padding: 0 18px;
  }
  .welcome-nav nav { display: none; }
  .welcome-footer { align-items: flex-start; flex-direction: column; }
}
```

Add these exact button, brand, footer, focus, and hover selectors. Do not change `frontend/src/style.css`.

```css
.brand {
  display: inline-flex;
  align-items: center;
  justify-self: start;
  gap: 10px;
  padding: 0;
  border: 0;
  color: #13213a;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 10px;
  color: #fff;
  background: linear-gradient(135deg, #2467ed, #7359ed);
  box-shadow: 0 8px 18px rgba(36, 103, 237, .24);
  font-size: 11px;
  font-weight: 850;
}

.brand span:last-child { display: grid; gap: 2px; }
.brand b { font-size: 14px; }
.brand small { color: #8190a6; font-size: 10px; }

.welcome-nav nav { display: flex; gap: 8px; }

.welcome-nav nav button,
.nav-login,
.final-cta button {
  border: 0;
  border-radius: 10px;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.welcome-nav nav button {
  padding: 9px 11px;
  color: #65738a;
  background: transparent;
}

.welcome-nav nav button:hover { color: #2467ed; background: rgba(36, 103, 237, .07); }

.nav-login {
  padding: 10px 15px;
  color: #fff;
  background: #2467ed;
  box-shadow: 0 9px 20px rgba(36, 103, 237, .22);
}

.final-cta p {
  margin: 16px auto 26px;
  max-width: 620px;
  color: rgba(255, 255, 255, .76);
  font-size: 16px;
}

.final-cta button {
  min-height: 50px;
  padding: 0 20px;
  color: #204cae;
  background: #fff;
  box-shadow: 0 14px 30px rgba(13, 34, 90, .2);
}

.brand:focus-visible,
.welcome-nav button:focus-visible,
.final-cta button:focus-visible {
  outline: 3px solid rgba(36, 103, 237, .28);
  outline-offset: 3px;
}

.welcome-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 24px max(28px, calc((100vw - 1180px) / 2));
  color: #78869c;
  background: #f8faff;
  font-size: 12px;
}
```

- [ ] **Step 5: Run the route-page test and commit**

Run:

```bash
cd frontend
npm.cmd test -- src/views/__tests__/WelcomeView.spec.js
```

Expected: 2 tests PASS.

Commit:

```bash
git add frontend/src/views/WelcomeView.vue frontend/src/views/__tests__/WelcomeView.spec.js
git commit -m "feat: compose redesigned welcome page"
```

### Task 8: Run Automated Verification

**Files:**

- Modify only if verification reveals a scoped welcome-page issue

- [ ] **Step 1: Run all welcome-page tests**

```bash
cd frontend
npm.cmd test -- src/composables/__tests__/useReveal.spec.js src/components/welcome/__tests__/WelcomeHero.spec.js src/components/welcome/__tests__/CapabilityShowcase.spec.js src/components/welcome/__tests__/LearningFlow.spec.js src/components/welcome/__tests__/RoleShowcase.spec.js src/views/__tests__/WelcomeView.spec.js
```

Expected: all welcome-page tests PASS.

- [ ] **Step 2: Run the complete frontend suite**

```bash
cd frontend
npm.cmd test
```

Expected: complete Vitest suite PASS.

- [ ] **Step 3: Build the production bundle**

```bash
cd frontend
npm.cmd run build
```

Expected: Vite build completes with exit code 0 and no Vue template or CSS syntax errors.

- [ ] **Step 4: Inspect the final diff**

```bash
git diff --check
git status --short
```

Expected:

```text
No whitespace errors.
Only welcome-page implementation and test files are modified or newly created.
Existing unrelated untracked files remain unstaged.
```

- [ ] **Step 5: Commit any verification-only fixes**

If Task 8 required a scoped fix:

```bash
git add frontend/src/views/WelcomeView.vue frontend/src/components/welcome frontend/src/composables/useReveal.js frontend/src/views/welcome/welcomeContent.js frontend/src/views/__tests__/WelcomeView.spec.js frontend/src/composables/__tests__/useReveal.spec.js
git commit -m "fix: complete welcome page verification"
```

If no source changes were needed, do not create an empty commit.

### Task 9: Browser Fidelity and Interaction QA

**Files:**

- Artifact outside committed source: desktop, long-page, hover, and mobile screenshots
- Reference: accepted ImageGen concept from Task 1

- [ ] **Step 1: Verify desktop page identity and health**

Using the Browser plugin, load `http://localhost:8080/welcome` at 1280×720 and check:

```text
[ ] URL is /welcome
[ ] Title is DAI 实验平台 · Python Learning Studio
[ ] DOM contains the hero, capability section, learning loop, role scenes, and final CTA
[ ] No Vite/Vue error overlay
[ ] No relevant console error or warning
```

- [ ] **Step 2: Verify the primary interactions**

Exercise:

```text
/welcome
  -> click “探索平台能力”
  -> capability section aligns near the top
  -> move pointer over each of the four capability blocks
  -> each block lifts without rotating and shows a distinct micro-motion
  -> click “立即登录”
  -> /login
```

Return to `/welcome` after confirming the login route.

- [ ] **Step 3: Verify responsive layouts**

Capture:

```text
1280×720 first viewport
1440×900 full-page
390×844 first viewport and full-page
```

At 390×844 confirm:

```text
[ ] No horizontal scrolling
[ ] Hero copy appears before the code window
[ ] Code content is readable and not clipped
[ ] Score panel remains visible
[ ] Capability blocks stack cleanly
[ ] Learning flow becomes vertical
[ ] Four role scenes keep their intended order
[ ] Navigation login action remains accessible
```

- [ ] **Step 4: Verify reduced motion**

Enable reduced-motion emulation or inspect the reduced-motion media state and confirm:

```text
[ ] Background drift stops
[ ] Code lines remain visible
[ ] AI score panel remains visible
[ ] Capability content does not depend on hover animation
[ ] Learning flow path and nodes remain visible
```

- [ ] **Step 5: Complete the fidelity ledger**

Compare the accepted concept and implementation with at least these points:

```text
1. Exact hero copy and CTA order
2. Upright product-window geometry
3. Ten-line code density and output strip
4. Ice-white, cobalt, violet, navy, and green palette
5. Capability gallery container model
6. Learning-loop dark transition band
7. Four-role scene coverage
8. Desktop and mobile spacing
9. Typography scale and Chinese line breaks
10. Motion timing and reduced-motion fallback
```

Fix every agency-review-level mismatch that remains practical. Record only intentional deviations with a concrete reason.

- [ ] **Step 6: Run final verification and commit browser-driven fixes**

Run again:

```bash
cd frontend
npm.cmd test
npm.cmd run build
```

Expected: tests and build PASS after the final browser fixes.

If browser QA changed welcome-page source, commit the exact changed welcome files:

```bash
git add frontend/src/views/WelcomeView.vue frontend/src/components/welcome frontend/src/composables frontend/src/views/welcome frontend/src/views/__tests__/WelcomeView.spec.js
git commit -m "feat: finish welcome page visual redesign"
```

If browser QA required no source change, do not create an empty commit. Do not stage `.superpowers/brainstorm`, screenshots, generated concept files, or unrelated working-tree changes.
