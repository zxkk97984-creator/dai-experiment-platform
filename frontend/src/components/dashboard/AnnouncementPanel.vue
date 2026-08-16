<script setup>
// 共享公告面板：列表 + 加载/错误/空态；公告内容一律按纯文本展示

import { computed } from 'vue'

const props = defineProps({
  announcements: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  error: { type: Boolean, default: false },
  canPublish: { type: Boolean, default: false },
})

defineEmits(['retry', 'mark-read', 'publish'])

const dateFmt = new Intl.DateTimeFormat('zh-CN', {
  month: 'numeric',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

function sourceText(notice) {
  return notice.scope === 'course' ? (notice.course_title || '课程公告') : '全局公告'
}

function formatDate(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : dateFmt.format(date)
}

const hasItems = computed(() => props.announcements.length > 0)
</script>

<template>
  <section class="announcement-panel" :aria-busy="loading ? 'true' : undefined">
    <div class="panel-head">
      <h2 class="panel-title">通知公告</h2>
      <button
        v-if="canPublish"
        type="button"
        class="publish-btn"
        @click="$emit('publish')"
      >
        发布公告
      </button>
    </div>

    <div v-if="loading" class="panel-state" role="status">加载中…</div>
    <div v-else-if="error" class="panel-state" role="alert">
      <p class="state-text">公告加载失败</p>
      <button type="button" class="retry-btn" @click="$emit('retry')">重试</button>
    </div>
    <div v-else-if="!hasItems" class="panel-state">暂无公告</div>

    <ul v-else class="notice-list">
      <li
        v-for="notice in announcements"
        :key="notice.id"
        class="notice-item"
        :class="{ unread: !notice.is_read }"
      >
        <span v-if="!notice.is_read" class="unread-dot" aria-label="未读"></span>
        <div class="notice-main">
          <div class="notice-title">
            {{ notice.title }}
            <span class="priority-tag" :class="`priority-${notice.priority}`">
              {{ { normal: '普通', important: '重要', urgent: '紧急' }[notice.priority] || '普通' }}
            </span>
          </div>
          <p class="notice-content">{{ notice.content }}</p>
          <div class="notice-meta">
            {{ sourceText(notice) }} · {{ notice.author_name }} · {{ formatDate(notice.published_at) }}
          </div>
        </div>
        <button
          v-if="!notice.is_read"
          type="button"
          class="mark-read-btn"
          @click="$emit('mark-read', notice)"
        >
          标记已读
        </button>
      </li>
    </ul>
  </section>
</template>

<style scoped>
/* 公告面板（V2）：无卡片阴影，优先级用 V2 badge 语义。 */
.announcement-panel { display: flex; flex-direction: column; gap: 10px; }
.panel-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.panel-title { margin: 0; font-size: var(--text-md); font-weight: 600; color: var(--fg); }
.publish-btn { height: 28px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: var(--radius-md); background: var(--surface); color: var(--fg); font-size: var(--text-base); font-weight: 500; cursor: pointer; }
.publish-btn:hover { border-color: var(--fg); }
.panel-state { padding: 20px 12px; text-align: center; color: var(--muted); font-size: var(--text-base); }
.state-text { margin: 0 0 8px; }
.retry-btn { height: 28px; padding: 0 12px; border: 1px solid var(--border-strong); border-radius: var(--radius-md); background: var(--surface); color: var(--fg); font-size: var(--text-base); cursor: pointer; }
.retry-btn:hover { border-color: var(--fg); }
.notice-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.notice-item { display: flex; gap: 10px; align-items: flex-start; padding: 12px; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface); }
.notice-item.unread { border-color: var(--accent-soft); }
.unread-dot { flex-shrink: 0; width: 7px; height: 7px; margin-top: 6px; border-radius: 50%; background: var(--accent); }
.notice-main { flex: 1; min-width: 0; }
.notice-title { display: flex; align-items: center; gap: 6px; font-size: var(--text-md); font-weight: 500; color: var(--fg); flex-wrap: wrap; }
.priority-tag { display: inline-flex; height: 20px; align-items: center; padding: 0 7px; border-radius: var(--radius-sm); font-size: 11px; font-weight: 500; color: var(--muted); background: var(--surface-sunken); }
.priority-important { color: var(--warning); background: var(--warning-bg); }
.priority-urgent { color: var(--danger); background: var(--danger-bg); }
.notice-content { margin: 4px 0 6px; font-size: var(--text-base); color: var(--muted); line-height: 1.55; overflow-wrap: anywhere; }
.notice-meta { font-family: var(--font-mono); font-size: var(--text-sm); color: var(--faint); }
.mark-read-btn { flex-shrink: 0; height: 28px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: var(--radius-md); background: var(--surface); color: var(--muted); font-size: var(--text-xs); cursor: pointer; }
.mark-read-btn:hover { border-color: var(--fg); color: var(--fg); }
</style>
