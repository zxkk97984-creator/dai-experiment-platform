<script setup>
import { ref, onMounted } from 'vue'
import { heroContent, codeLines, codeOutput } from '../../views/welcome/welcomeContent.js'

const props = defineProps({
  isVisible: { type: Boolean, default: false },
})

const emit = defineEmits(['explore', 'login'])

const revealedLines = ref(0)
const showOutput = ref(false)
const showScore = ref(false)

onMounted(() => {
  // Staggered reveal animation
  const interval = setInterval(() => {
    if (revealedLines.value < codeLines.length) {
      revealedLines.value++
    } else {
      clearInterval(interval)
      setTimeout(() => { showOutput.value = true }, 200)
      setTimeout(() => { showScore.value = true }, 600)
    }
  }, 80)
})
</script>

<template>
  <section class="hero" :class="{ 'hero--visible': isVisible }" aria-label="平台介绍">
    <div class="hero-bg" aria-hidden="true"></div>

    <div class="hero-inner">
      <div class="hero-left">
        <p class="hero-eyebrow">{{ heroContent.eyebrow }}</p>
        <h1 class="hero-title">{{ heroContent.title }}</h1>
        <p class="hero-desc">{{ heroContent.description }}</p>
        <div class="hero-actions">
          <button class="hero-btn hero-btn--primary" @click="$emit('explore')">
            {{ heroContent.primaryAction }}
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M8 3v10M3 8l5-5 5 5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
          <button class="hero-btn hero-btn--secondary" @click="$emit('login')">
            {{ heroContent.secondaryAction }}
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>
      </div>

      <div class="hero-right">
        <div class="code-window">
          <div class="code-header">
            <span class="code-dots" aria-hidden="true">
              <i></i><i></i><i></i>
            </span>
            <span class="code-file">experiment.py</span>
            <span class="code-status">RUNNING</span>
          </div>
          <div class="code-body">
            <div class="code-lines" aria-hidden="true">
              <span v-for="n in codeLines.length" :key="n">{{ n }}</span>
            </div>
            <pre class="code-content"><code v-for="(line, i) in codeLines" :key="i" :class="{ visible: i < revealedLines }" :style="{ paddingLeft: line.indent * 20 + 'px' }">{{ line.text }}</code></pre>
          </div>
        </div>

        <div class="output-strip" :class="{ visible: showOutput }">
          <div class="output-meta">
            <span class="output-item">Epochs <strong>{{ codeOutput.epochs }}</strong></span>
            <span class="output-item">Accuracy <strong class="txt-accent">{{ codeOutput.accuracy }}</strong></span>
            <span class="output-item">Tests <strong class="txt-success">{{ codeOutput.testsPassed ? '全部测试通过' : '' }}</strong></span>
          </div>
        </div>

        <div class="score-panel" :class="{ visible: showScore }">
          <div class="score-badge">AI</div>
          <div class="score-body">
            <span class="score-label">{{ codeOutput.scoreLabel }}：优秀</span>
            <span class="score-comment">{{ codeOutput.scoreComment }}</span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.hero {
  position: relative;
  overflow: hidden;
  padding: 80px 56px 60px;
  background: #F8FAFF;
}

.hero-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 80% 60% at 80% 20%, rgba(36,103,237,0.04) 0%, transparent 60%),
    radial-gradient(ellipse 50% 40% at 20% 80%, rgba(115,89,237,0.03) 0%, transparent 60%);
  pointer-events: none;
}

.hero-inner {
  position: relative;
  max-width: 1180px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 64px;
  align-items: center;
}

.hero-left {
  max-width: 520px;
}

.hero-eyebrow {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: #7359ED;
  margin: 0 0 16px;
}

.hero-title {
  font-size: clamp(34px, 4.5vw, 52px);
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.03em;
  color: #13213A;
  margin: 0 0 20px;
}

.hero-desc {
  font-size: 16px;
  line-height: 1.65;
  color: #6E7B92;
  margin: 0 0 32px;
}

.hero-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.hero-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 14px 28px;
  font-size: 15px;
  font-weight: 600;
  font-family: inherit;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.hero-btn--primary {
  background: #2467ED;
  color: #fff;
}

.hero-btn--primary:hover {
  background: #1D4ED8;
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(36,103,237,0.3);
}

.hero-btn--secondary {
  background: transparent;
  color: #13213A;
  border: 1px solid #E2E8F0;
}

.hero-btn--secondary:hover {
  border-color: #2467ED;
  color: #2467ED;
}

/* ====== Code Window ====== */
.code-window {
  background: #14213B;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(20,33,59,0.25);
}

.code-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}

.code-dots {
  display: flex;
  gap: 6px;
}

.code-dots i {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.code-dots i:nth-child(1) { background: #FF5F56; }
.code-dots i:nth-child(2) { background: #FFBD2E; }
.code-dots i:nth-child(3) { background: #27C93F; }

.code-file {
  font-family: var(--font-mono);
  font-size: 12px;
  color: rgba(255,255,255,0.4);
}

.code-status {
  margin-left: auto;
  font-size: 11px;
  font-family: var(--font-mono);
  color: #58DDA7;
  background: rgba(88,221,167,0.12);
  padding: 2px 10px;
  border-radius: 20px;
}

.code-body {
  display: flex;
  padding: 18px 0;
}

.code-lines {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  width: 42px;
  padding-right: 14px;
  border-right: 1px solid rgba(255,255,255,0.06);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.7;
  color: rgba(255,255,255,0.2);
  user-select: none;
}

.code-content {
  flex: 1;
  padding: 0 18px;
  margin: 0;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.7;
  color: #CBD5E1;
  overflow-x: auto;
}

.code-content code {
  display: block;
  opacity: 0;
  transform: translateX(8px);
  transition: all 0.3s ease;
}

.code-content code.visible {
  opacity: 1;
  transform: translateX(0);
}

/* ====== Output Strip ====== */
.output-strip {
  margin-top: 16px;
  background: #fff;
  border: 1px solid #E2E8F0;
  border-radius: 16px;
  padding: 18px 20px;
  opacity: 0;
  transform: translateY(10px);
  transition: all 0.4s ease;
}

.output-strip.visible {
  opacity: 1;
  transform: translateY(0);
}

.output-meta {
  display: flex;
  gap: 32px;
}

.output-item {
  font-size: 12px;
  color: #94A3B8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.output-item strong {
  display: block;
  margin-top: 4px;
  font-size: 20px;
  font-weight: 700;
  color: #13213A;
}

.txt-accent { color: #2467ED !important; }
.txt-success { color: #58DDA7 !important; }

/* ====== Score Panel ====== */
.score-panel {
  margin-top: 12px;
  background: #fff;
  border: 1px solid #E2E8F0;
  border-radius: 16px;
  padding: 16px 20px;
  display: flex;
  gap: 14px;
  align-items: flex-start;
  opacity: 0;
  transform: translateY(10px);
  transition: all 0.4s ease 0.15s;
}

.score-panel.visible {
  opacity: 1;
  transform: translateY(0);
}

.score-badge {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #2467ED, #7359ED);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  border-radius: 50%;
  flex-shrink: 0;
}

.score-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.score-label {
  font-size: 14px;
  font-weight: 600;
  color: #13213A;
}

.score-comment {
  font-size: 12px;
  color: #94A3B8;
  line-height: 1.4;
}

/* ====== Responsive ====== */
@media (max-width: 1024px) {
  .hero-inner {
    grid-template-columns: 1fr;
    gap: 48px;
  }
  .hero-left {
    max-width: 100%;
  }
}

@media (max-width: 768px) {
  .hero {
    padding: 48px 24px 40px;
  }
  .hero-actions {
    flex-direction: column;
  }
  .hero-btn {
    width: 100%;
    justify-content: center;
  }
}

@media (prefers-reduced-motion: reduce) {
  .code-content code {
    opacity: 1;
    transform: none;
    transition: none;
  }
  .output-strip,
  .score-panel {
    opacity: 1;
    transform: none;
    transition: none;
  }
}
</style>
