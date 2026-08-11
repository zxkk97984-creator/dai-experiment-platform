<script setup>
import AppIcon from '../ui/AppIcon.vue'

defineProps({
  items: { type: Array, required: true },
  ariaLabel: { type: String, required: true },
})
</script>

<template>
  <section class="teacher-metric-grid" :class="`columns-${items.length}`" :aria-label="ariaLabel">
    <article v-for="item in items" :key="item.key" class="teacher-metric-card">
      <span class="teacher-metric-icon" :class="item.tone || 'blue'">
        <AppIcon :name="item.icon" :size="24" />
      </span>
      <span class="teacher-metric-copy">
        <small>{{ item.label }}</small>
        <span class="teacher-metric-value">
          <strong :class="{ emphasized: item.emphasis }">{{ item.value }}</strong>
          <em v-if="item.unit">{{ item.unit }}</em>
        </span>
      </span>
    </article>
  </section>
</template>

<style scoped>
.teacher-metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px;
}

.teacher-metric-grid.columns-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }

.teacher-metric-card {
  display: flex;
  align-items: center;
  gap: 18px;
  min-width: 0;
  min-height: 106px;
  padding: 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  background: var(--surface);
  box-shadow: var(--shadow-card);
}

.teacher-metric-icon {
  display: grid;
  place-items: center;
  width: 54px;
  height: 54px;
  flex: 0 0 auto;
  border-radius: 15px;
}

.teacher-metric-icon.blue { color: var(--primary); background: var(--primary-light); }
.teacher-metric-icon.green { color: var(--success); background: var(--success-light); }
.teacher-metric-icon.orange { color: var(--warning); background: var(--warning-light); }
.teacher-metric-icon.purple { color: var(--purple); background: var(--purple-light); }

.teacher-metric-copy { display: grid; min-width: 0; gap: 4px; }
.teacher-metric-copy small { color: var(--text-secondary); font-size: 14px; line-height: 1.35; }
.teacher-metric-value { display: flex; align-items: baseline; gap: 7px; }
.teacher-metric-value strong { color: var(--ink); font-size: 27px; font-weight: 700; line-height: 1; }
.teacher-metric-icon.green + .teacher-metric-copy strong.emphasized { color: var(--success); }
.teacher-metric-icon.orange + .teacher-metric-copy strong.emphasized { color: var(--warning); }
.teacher-metric-icon.purple + .teacher-metric-copy strong.emphasized { color: var(--purple); }
.teacher-metric-value em { color: var(--text-tertiary); font-size: 12px; font-style: normal; }

@media (max-width: 1100px) {
  .teacher-metric-grid,
  .teacher-metric-grid.columns-3 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .teacher-metric-grid.columns-3 .teacher-metric-card:last-child { grid-column: 1 / -1; }
}

@media (max-width: 720px) {
  .teacher-metric-grid,
  .teacher-metric-grid.columns-3 { grid-template-columns: 1fr; gap: 10px; }
  .teacher-metric-grid.columns-3 .teacher-metric-card:last-child { grid-column: auto; }
  .teacher-metric-card { min-height: 88px; padding: 15px 17px; gap: 14px; }
  .teacher-metric-icon { width: 46px; height: 46px; border-radius: 13px; }
  .teacher-metric-value strong { font-size: 24px; }
}
</style>
