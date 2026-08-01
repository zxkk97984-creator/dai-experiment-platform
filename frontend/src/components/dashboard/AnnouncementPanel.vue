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
.announcement-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.panel-title {
  margin: 0;
  font-size: var(--text-base);
  font-weight: 700;
  color: var(--ink);
}

.publish-btn {
  padding: 6px 14px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--primary);
  color: var(--surface);
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
}
.publish-btn:hover { background: var(--primary-dark); }

.panel-state {
  padding: 20px 12px;
  text-align: center;
  color: var(--text-secondary);
  font-size: var(--text-sm);
}
.state-text { margin: 0 0 8px; }

.retry-btn {
  padding: 5px 14px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--primary);
  font-size: var(--text-sm);
  cursor: pointer;
}
.retry-btn:hover { background: var(--primary-light); }

.notice-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.notice-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
}

.notice-item.unread {
  border-color: var(--primary-light);
  background: var(--surface);
}

.unread-dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 50%;
  background: var(--primary);
}

.notice-main { flex: 1; min-width: 0; }

.notice-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink);
  flex-wrap: wrap;
}

.priority-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: var(--radius-xs);
  color: var(--text-secondary);
  background: var(--surface-raised);
}
.priority-important { color: var(--warning); background: var(--warning-light); }
.priority-urgent { color: var(--danger); background: var(--danger-light); }

.notice-content {
  margin: 4px 0 6px;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.5;
  overflow-wrap: anywhere;
  /* 按设计限制两行摘要 */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.notice-meta {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.mark-read-btn {
  flex-shrink: 0;
  padding: 4px 10px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--primary);
  font-size: var(--text-xs);
  cursor: pointer;
}
.mark-read-btn:hover { background: var(--primary-light); }
</style>
