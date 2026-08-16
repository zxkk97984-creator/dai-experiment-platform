<script setup>
import { ref } from 'vue'
import { capabilities } from '../../views/welcome/welcomeContent.js'

const hoveredId = ref(null)
</script>

<template>
  <section id="capabilities" class="cap" aria-label="平台能力展示">
    <div class="cap-inner">
      <header class="cap-header">
        <p class="cap-eyebrow">平台能力</p>
        <h2 class="cap-title">覆盖完整 AI 学习与实验流程</h2>
        <p class="cap-sub">从课程到编码，从提交到 AI 评分，八大核心能力在一个平台内无缝衔接。</p>
      </header>

      <div class="cap-grid">
        <div
          v-for="(item, idx) in capabilities"
          :key="item.id"
          class="cap-card"
          :class="{
            hovered: hoveredId === item.id,
            'cap-card--courses': item.id === 'courses',
            'cap-card--coding': item.id === 'coding',
            'cap-card--notebook': item.id === 'notebook',
            'cap-card--assignments': item.id === 'assignments',
            'cap-card--exams': item.id === 'exams',
            'cap-card--judging': item.id === 'judging',
            'cap-card--aiGrading': item.id === 'aiGrading',
            'cap-card--templates': item.id === 'templates',
          }"
          @mouseenter="hoveredId = item.id"
          @mouseleave="hoveredId = null"
        >
          <span class="cap-card-index">{{ String(idx + 1).padStart(2, "0") }} · {{ item.label }}</span>
          <div class="cap-card-icon" aria-hidden="true">
            <span class="cap-card-emoji">{{ item.icon === 'courses' ? '📚' : item.icon === 'coding' ? '💻' : item.icon === 'notebook' ? '📓' : item.icon === 'assignments' ? '📋' : item.icon === 'exams' ? '📝' : item.icon === 'judging' ? '⚡' : item.icon === 'aiGrading' ? '🤖' : '🧩' }}</span>
          </div>
          <h3 class="cap-card-title">{{ item.title }}</h3>
          <p class="cap-card-summary">{{ item.summary }}</p>
          <div class="cap-card-tags">
            <span v-for="tag in item.tags" :key="tag" class="cap-card-tag">{{ tag }}</span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.cap {
  padding: 80px 56px;
  background: var(--surface);
}

.cap-inner {
  max-width: 1180px;
  margin: 0 auto;
}

.cap-header {
  text-align: center;
  margin-bottom: 48px;
}

.cap-eyebrow {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: var(--info);
  margin: 0 0 12px;
}

.cap-title {
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--fg);
  margin: 0 0 12px;
}

.cap-sub {
  font-size: 16px;
  color: var(--muted);
  max-width: 560px;
  margin: 0 auto;
  line-height: 1.5;
}

.cap-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.cap-card {
  --accent: var(--accent);
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 180px;
  padding: 20px;
  overflow: hidden;
  border: 1px solid oklch(0.2 0.01 150 / 0.13);
  border-radius: var(--radius-lg);
  color: var(--fg);
  background: oklch(0.99 0.001 95 / 0.88);
  box-shadow: var(--shadow-sm);
  cursor: default;
  transform: translateY(0);
  transition: transform 260ms cubic-bezier(0.2, 0.8, 0.2, 1), border-color 260ms ease, box-shadow 260ms ease, background 260ms ease;
}

.cap-card--courses   { --accent: var(--accent); }
.cap-card--coding    { --accent: var(--info); }
.cap-card--notebook  { --accent: var(--success); }
.cap-card--assignments { --accent: var(--warning); }
.cap-card--exams     { --accent: var(--danger); }
.cap-card--judging   { --accent: var(--warning); }
.cap-card--aiGrading { --accent: var(--info); }
.cap-card--templates { --accent: var(--accent); }

.cap-card::before {
  content: "";
  position: absolute;
  inset: 0;
  opacity: 0;
  z-index: 0;
  background: linear-gradient(115deg, transparent 24%, color-mix(in srgb, var(--accent) 9%, transparent), transparent 68%);
  transform: translateX(-70%);
  transition: opacity 220ms ease;
}

.cap-card::after {
  content: "";
  position: absolute;
  left: 18px;
  right: 18px;
  bottom: 0;
  height: 2px;
  border-radius: var(--radius-full);
  z-index: 0;
  opacity: 0;
  background: var(--accent);
  box-shadow: 0 0 16px color-mix(in srgb, var(--accent) 54%, transparent);
  transform: scaleX(0.3);
  transition: opacity 240ms ease, transform 320ms ease;
}

.cap-card:hover,
.cap-card.hovered {
  transform: translateY(-8px);
  border-color: color-mix(in srgb, var(--accent) 35%, white);
  background: var(--surface);
  box-shadow: 0 20px 38px oklch(0.2 0.01 150 / 0.13);
}

.cap-card:hover::before,
.cap-card.hovered::before {
  opacity: 1;
  animation: cardSheen 0.9s ease forwards;
}

.cap-card:hover::after,
.cap-card.hovered::after {
  opacity: 1;
  transform: scaleX(1);
}

@keyframes cardSheen {
  from { transform: translateX(-70%); }
  to { transform: translateX(70%); }
}

.cap-card-index {
  position: relative;
  z-index: 1;
  font-size: 9px;
  font-weight: 750;
  letter-spacing: 0.1em;
  color: var(--faint);
  margin-bottom: 14px;
  text-transform: uppercase;
}

.cap-card-icon {
  position: relative;
  z-index: 1;
  font-size: 26px;
  margin-bottom: 10px;
}

.cap-card-title {
  position: relative;
  z-index: 1;
  font-size: 15px;
  font-weight: 650;
  color: var(--fg);
  margin: 0 0 6px;
  letter-spacing: -0.01em;
}

.cap-card-summary {
  position: relative;
  z-index: 1;
  font-size: 12px;
  line-height: 1.55;
  color: var(--muted);
  margin: 0 0 12px;
}

.cap-card-tags {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.cap-card-tag {
  font-size: 10px;
  padding: 3px 9px;
  border-radius: var(--radius-lg);
  background: var(--surface-subtle);
  color: var(--muted);
  font-weight: 500;
}

.cap-card-visual {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  margin-top: auto;
  padding-top: 14px;
  min-height: 32px;
  opacity: 0.4;
  transition: opacity 0.28s ease 0.1s;
}

.cap-card:hover .cap-card-visual,
.cap-card.hovered .cap-card-visual {
  opacity: 1;
}

.vis-dot {
  width: 4px; height: 4px;
  border-radius: 50%;
  background: var(--accent);
  opacity: 0.5;
}
.cap-card:hover .vis-dot,
.cap-card.hovered .vis-dot {
  animation: visDotBounce 0.65s ease-in-out infinite alternate;
}
@keyframes visDotBounce {
  0% { transform: translateY(0); opacity: 0.3; }
  100% { transform: translateY(-6px); opacity: 1; }
}

.vis-bar {
  width: 22px;
  height: calc(var(--h) * 1px);
  border-radius: var(--radius-sm);
  background: oklch(0.2 0.01 150 / 0.1);
  display: flex;
  align-items: flex-end;
  overflow: hidden;
}
.vis-bar i {
  display: block;
  width: 100%;
  height: 0;
  border-radius: inherit;
  background: var(--accent);
  transition: height 0.4s ease;
}
.cap-card:hover .vis-bar i,
.cap-card.hovered .vis-bar i {
  height: 100%;
  transition: height 0.45s ease calc(var(--h) * 0.02s);
}

.vis-wave {
  width: 16px; height: 2px;
  border-radius: var(--radius-sm);
  background: var(--accent);
  opacity: 0.4;
}
.cap-card:hover .vis-wave,
.cap-card.hovered .vis-wave {
  animation: visWaveDrift 0.7s ease-in-out infinite alternate;
}
@keyframes visWaveDrift {
  0% { transform: translateX(-3px); opacity: 0.25; }
  100% { transform: translateX(3px); opacity: 0.8; }
}

.vis-arrow {
  font-size: 14px;
  color: var(--accent);
  opacity: 0.4;
}
.cap-card:hover .vis-arrow,
.cap-card.hovered .vis-arrow {
  animation: visArrowSlide 0.55s ease-in-out infinite alternate;
}
@keyframes visArrowSlide {
  0% { transform: translateX(-3px); opacity: 0.2; }
  100% { transform: translateX(4px); opacity: 0.9; }
}

.vis-ring {
  width: 7px; height: 7px;
  border-radius: 50%;
  border: 1.5px solid var(--accent);
  opacity: 0.4;
}
.cap-card:hover .vis-ring,
.cap-card.hovered .vis-ring {
  animation: visRingExpand 0.65s ease-in-out infinite alternate;
}
@keyframes visRingExpand {
  0% { transform: scale(0.6); opacity: 0.2; }
  100% { transform: scale(1); opacity: 0.85; }
}

.vis-bolt {
  font-size: 13px;
  opacity: 0.35;
}
.cap-card:hover .vis-bolt,
.cap-card.hovered .vis-bolt {
  animation: visBoltFlash 0.45s ease-in-out infinite alternate;
}
@keyframes visBoltFlash {
  0% { transform: scale(0.7); opacity: 0.2; filter: brightness(1); }
  100% { transform: scale(1.25); opacity: 1; filter: brightness(1.6); }
}

.vis-pulse {
  position: absolute;
  width: 10px; height: 10px;
  border-radius: 50%;
  border: 2px solid var(--accent);
  opacity: 0;
}
.cap-card:hover .vis-pulse,
.cap-card.hovered .vis-pulse {
  animation: visPulse 1.1s ease-out infinite;
}
@keyframes visPulse {
  0% { width: 6px; height: 6px; opacity: 0.7; }
  100% { width: 22px; height: 22px; opacity: 0; }
}

.vis-cell {
  width: 5px; height: 5px;
  border-radius: var(--radius-sm);
  background: var(--accent);
  opacity: 0;
}
.cap-card:hover .vis-cell,
.cap-card.hovered .vis-cell {
  animation: visGridFlicker 1s ease-in-out infinite;
  animation-delay: calc(var(--x) * 0.1s + var(--y) * 0.15s);
}
@keyframes visGridFlicker {
  0%, 100% { opacity: 0.1; }
  50% { opacity: 0.7; }
}

@media (max-width: 1024px) {
  .cap-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .cap {
    padding: 48px 24px;
  }
  .cap-grid {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .cap-card:hover,
  .cap-card.hovered {
    transform: none;
  }
  .cap-card::before,
  .cap-card::after {
    display: none;
  }
  .cap-card-visual {
    opacity: 0;
  }
  .vis-dot, .vis-bar i, .vis-wave, .vis-arrow, .vis-ring, .vis-bolt, .vis-pulse, .vis-cell {
    animation: none !important;
  }
}
</style>