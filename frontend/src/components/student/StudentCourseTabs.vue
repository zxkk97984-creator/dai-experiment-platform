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
  <nav class="tabs course-tabs" role="tablist" aria-label="课程栏目">
    <button
      v-for="t in TABS"
      :key="t.key"
      type="button"
      class="tab course-tab"
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
  height: 42px;
  background: transparent;
  border: 0;
  border-radius: 0;
  box-shadow: none;
  overflow-x: auto;
}
.course-tab { flex-shrink: 0; }
</style>
