<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { coursesAPI } from '../../api/courses.js'
import { useAppStore } from '../../stores/app.js'

const route = useRoute()
const app = useAppStore()
const lesson = ref(null)
const loading = ref(true)

onMounted(async () => {
  try {
    const res = await coursesAPI.getChapters(route.params.id)
    const chapters = res.data
    for (const ch of chapters) {
      if (ch.lessons) {
        const found = ch.lessons.find(l => l.id == route.params.lid)
        if (found) { lesson.value = found; break }
      }
    }
    if (!lesson.value) app.showToast('课时不存在', 'error')
  } catch { app.showToast('加载课时失败', 'error') }
  finally { loading.value = false }
})
</script>

<template>
  <AppLayout>
    <div v-if="loading" class="text-secondary">加载中...</div>
    <template v-else-if="lesson">
      <h1 class="page-title">{{ lesson.title }}</h1>
      <div class="card">
        <div v-if="lesson.content_type === 'markdown'" class="lesson-content"
          v-html="lesson.content || '暂无内容'"></div>
        <div v-else-if="lesson.content_type === 'video'">
          <p class="text-secondary mb-4">视频课时</p>
          <a v-if="lesson.video_url" :href="lesson.video_url" target="_blank"
            class="btn-primary" style="display:inline-block;padding:8px 16px;text-decoration:none;">打开视频</a>
        </div>
        <div v-else>
          <p class="text-secondary">{{ lesson.content || '暂无内容' }}</p>
        </div>
      </div>
    </template>
    <div v-else class="card" style="text-align:center;padding:32px">
      <p class="text-secondary">课时不存在</p>
    </div>
  </AppLayout>
</template>

<style scoped>
.lesson-content { line-height: 1.8; }
.lesson-content :deep(h1), .lesson-content :deep(h2), .lesson-content :deep(h3) { margin: 16px 0 8px; }
.lesson-content :deep(p) { margin: 8px 0; }
.lesson-content :deep(pre) { background: #1e2532; color: #e5e7eb; padding: 16px; border-radius: 6px; overflow-x: auto; }
.lesson-content :deep(code) { font-family: var(--font-mono); font-size: 13px; }
</style>
