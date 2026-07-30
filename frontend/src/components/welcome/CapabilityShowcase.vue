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
          v-for="item in capabilities"
          :key="item.id"
          class="cap-card"
          :class="{ hovered: hoveredId === item.id }"
          @mouseenter="hoveredId = item.id"
          @mouseleave="hoveredId = null"
        >
          <div class="cap-card-icon" aria-hidden="true">
            <span class="cap-card-emoji">{{ item.icon === 'courses' ? '📚' : item.icon === 'coding' ? '💻' : item.icon === 'notebook' ? '📓' : item.icon === 'assignments' ? '📋' : item.icon === 'exams' ? '📝' : item.icon === 'judging' ? '⚡' : item.icon === 'aiGrading' ? '🤖' : '🧩' }}</span>
          </div>
          <h3 class="cap-card-title">{{ item.title }}</h3>
          <p class="cap-card-summary">{{ item.summary }}</p>
          <div class="cap-card-tags">
            <span v-for="tag in item.tags" :key="tag" class="cap-card-tag">{{ tag }}</span>
          </div>
          <div class="cap-card-shine" aria-hidden="true"></div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.cap {
  padding: 80px 56px;
  background: #fff;
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
  color: #7359ED;
  margin: 0 0 12px;
}

.cap-title {
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: #13213A;
  margin: 0 0 12px;
}

.cap-sub {
  font-size: 16px;
  color: #6E7B92;
  max-width: 560px;
  margin: 0 auto;
  line-height: 1.5;
}

.cap-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.cap-card {
  position: relative;
  background: #fff;
  border: 1px solid #E2E8F0;
  border-radius: 16px;
  padding: 24px 20px;
  cursor: pointer;
  transition: all 0.3s ease;
  overflow: hidden;
}

.cap-card::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 16px;
  opacity: 0;
  transition: opacity 0.3s ease;
  background: linear-gradient(135deg, rgba(36,103,237,0.03), rgba(115,89,237,0.03));
}

.cap-card:hover,
.cap-card.hovered {
  transform: translateY(-4px);
  box-shadow: 0 12px 36px rgba(0,0,0,0.08);
  border-color: #CBD5E1;
}

.cap-card:hover::before,
.cap-card.hovered::before {
  opacity: 1;
}

.cap-card-icon {
  font-size: 28px;
  margin-bottom: 12px;
  position: relative;
}

.cap-card-title {
  font-size: 16px;
  font-weight: 600;
  color: #13213A;
  margin: 0 0 8px;
  position: relative;
}

.cap-card-summary {
  font-size: 13px;
  line-height: 1.55;
  color: #6E7B92;
  margin: 0 0 14px;
  position: relative;
}

.cap-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  position: relative;
}

.cap-card-tag {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 20px;
  background: #F1F5F9;
  color: #64748B;
  font-weight: 500;
}

.cap-card-shine {
  position: absolute;
  top: 0;
  left: -100%;
  width: 60%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
  transform: skewX(-15deg);
  transition: left 0.6s ease;
  pointer-events: none;
}

.cap-card:hover .cap-card-shine,
.cap-card.hovered .cap-card-shine {
  left: 120%;
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
  .cap-card-shine {
    display: none;
  }
}
</style>
