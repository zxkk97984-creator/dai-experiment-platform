<script setup>
// StudentCourseTabs：52px 水平标签条；激活项蓝色 2px 下划线，无 pill 背景。
// 原生 button，键盘可操作；切换仅改变内容区，不改变认证或课程身份。

defineProps({
  active: { type: String, default: 'overview' },
})

defineEmits(['change'])

const TABS = [
  { key: 'overview', label: '概览' },
  { key: 'chapters', label: '章节内容' },
  { key: 'assignments', label: '作业' },
  { key: 'experiments', label: '实验' },
  { key: 'exams', label: '考试' },
  { key: 'announcements', label: '公告' },
  { key: 'grades', label: '成绩' },
]
</script>

<template>
  <nav class="course-tabs" role="tablist" aria-label="课程栏目">
    <button
      v-for="t in TABS"
      :key="t.key"
      type="button"
      class="course-tab"
      :class="{ active: active === t.key }"
      role="tab"
      :aria-selected="active === t.key"
      @click="$emit('change', t.key)"
    >
      {{ t.label }}
    </button>
  </nav>
</template>

<style scoped>
.course-tabs {
  display: flex;
  align-items: stretch;
  height: 52px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  overflow-x: auto;
}

.course-tab {
  position: relative;
  flex-shrink: 0;
  padding: 0 22px;
  background: transparent;
  border: none;
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: color var(--duration-fast) var(--ease-out);
}

.course-tab:hover { color: var(--primary); }

.course-tab.active {
  color: var(--primary);
  font-weight: 600;
}
.course-tab.active::after {
  content: '';
  position: absolute;
  left: 18px;
  right: 18px;
  bottom: 0;
  height: 2px;
  background: var(--primary);
  border-radius: 2px 2px 0 0;
}
</style>
