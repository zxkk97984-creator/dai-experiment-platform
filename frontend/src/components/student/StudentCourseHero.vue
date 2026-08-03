<script setup>
// StudentCourseHero：课程概览英雄卡（164–168px 高）。
// 面包屑 + 课程身份 + 低对比元数据 chips + 进度 + CTA。

import { computed } from 'vue'
import AppIcon from '../ui/AppIcon.vue'
import UiProgress from '../ui/UiProgress.vue'
import { clampProgress } from '../../utils/studentUi.js'

const props = defineProps({
  course: { type: Object, required: true },
  progress: { type: Number, default: 0 },
  totalLessons: { type: Number, default: 0 },
  completedLessons: { type: Number, default: 0 },
  totalChapters: { type: Number, default: 0 },
  enrolled: { type: Boolean, default: false },
})

defineEmits(['continue', 'enroll', 'back'])

const safeProgress = computed(() => clampProgress(props.progress))
</script>

<template>
  <section class="course-hero">
    <div class="hero-breadcrumb">
      <button type="button" class="breadcrumb-link" @click="$emit('back')">我的课程</button>
      <AppIcon name="chevron-right" :size="14" />
      <span class="breadcrumb-current">{{ course.title }}</span>
    </div>

    <div class="hero-body">
      <div class="hero-identity">
        <h1 class="hero-title">{{ course.title }}</h1>
        <p class="hero-desc" v-if="course.description">{{ course.description }}</p>
      </div>

      <div class="hero-meta">
        <span class="hero-chip">{{ totalChapters }} 章节</span>
        <span class="hero-chip">{{ totalLessons }} 课时</span>
        <div class="hero-progress">
          <span class="hero-progress-text">
            已学 {{ safeProgress }}% · {{ completedLessons }}/{{ totalLessons }} 课时
          </span>
          <UiProgress :value="safeProgress" />
        </div>
      </div>

      <div class="hero-cta">
        <button
          v-if="enrolled"
          type="button"
          class="btn-primary hero-continue-btn"
          @click="$emit('continue')"
        >
          继续学习
        </button>
        <button v-else type="button" class="btn-primary hero-enroll-btn" @click="$emit('enroll')">
          立即选课
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.course-hero {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 166px;
  padding: 18px 24px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
}

/* ── 面包屑 ─────────────────────────────────────────────────────── */
.hero-breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}
.breadcrumb-link {
  background: none;
  border: none;
  padding: 0;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  cursor: pointer;
}
.breadcrumb-link:hover { color: var(--primary); }
.breadcrumb-current {
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── 主体 ───────────────────────────────────────────────────────── */
.hero-body {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 24px;
  min-width: 0;
}

.hero-identity {
  flex: 1.2;
  min-width: 0;
}
.hero-title {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.015em;
  line-height: 1.25;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hero-desc {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.hero-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
/* 低对比边框控件，非重填充徽章 */
.hero-chip {
  padding: 4px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--surface);
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-weight: 500;
  white-space: nowrap;
}
.hero-progress {
  flex: 1 1 100%;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 160px;
}
.hero-progress-text {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-secondary);
}

.hero-cta {
  flex-shrink: 0;
}
.hero-cta .btn-primary {
  height: 44px;
  padding: 0 26px;
  border-radius: var(--radius-control);
  font-weight: 600;
}

@media (max-width: 767.98px) {
  .course-hero { height: auto; padding: 16px; }
  .hero-body { flex-direction: column; align-items: stretch; gap: 14px; }
  .hero-cta { align-self: stretch; }
  .hero-cta .btn-primary { width: 100%; }
}
</style>
