<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { coursesAPI } from '../../api/courses.js'
import { useAppStore } from '../../stores/app.js'

const route = useRoute()
const app = useAppStore()
const course = ref(null)
const chapters = ref([])
const loading = ref(true)
const showChForm = ref(false)
const showLesForm = ref({})
const chForm = ref({ title: '' })
const lesForm = ref({ title: '', content_type: 'markdown', content: '' })

async function fetch() {
  loading.value = true
  try {
    const [cRes, chRes] = await Promise.all([
      coursesAPI.get(route.params.id),
      coursesAPI.getChapters(route.params.id),
    ])
    course.value = cRes.data
    chapters.value = chRes.data
  } catch { app.showToast('加载失败', 'error') }
  finally { loading.value = false }
}

async function createChapter() {
  if (!chForm.value.title) return
  try {
    await coursesAPI.createChapter(route.params.id, {
      title: chForm.value.title,
      order_index: chapters.value.length,
    })
    chForm.value.title = ''
    showChForm.value = false
    fetch()
    app.showToast('章节已创建', 'success')
  } catch { app.showToast('创建失败', 'error') }
}

async function createLesson(chId) {
  const f = lesForm.value
  if (!f.title) return
  try {
    await coursesAPI.createLesson(chId, { ...f, order_index: 0 })
    lesForm.value = { title: '', content_type: 'markdown', content: '' }
    showLesForm.value[chId] = false
    fetch()
    app.showToast('课时已创建', 'success')
  } catch { app.showToast('创建失败', 'error') }
}

onMounted(fetch)
</script>

<template>
  <AppLayout>
    <div class="flex-between mb-4">
      <h1 class="page-title" style="margin-bottom:0">{{ course?.title || '课程详情' }}</h1>
      <button class="btn-primary" @click="showChForm = !showChForm">
        {{ showChForm ? '取消' : '添加章节' }}
      </button>
    </div>

    <div v-if="showChForm" class="card mb-4">
      <div class="form-group">
        <label>章节名称</label>
        <input v-model="chForm.title" placeholder="如: 第一章 Python基础" />
      </div>
      <button class="btn-primary" @click="createChapter">确认添加</button>
    </div>

    <div v-if="loading" class="text-secondary">加载中...</div>

    <div v-for="(ch, chi) in chapters" :key="ch.id" class="card mb-4">
      <div class="flex-between mb-3">
        <h3 style="font-size:15px;color:#111827">第{{ chi + 1 }}章 {{ ch.title }}</h3>
        <button class="btn-sm" @click="showLesForm[ch.id] = !showLesForm[ch.id]">添加课时</button>
      </div>

      <div v-if="showLesForm[ch.id]" class="mb-4" style="padding:12px;background:#f9fafb;border-radius:6px">
        <div class="form-group">
          <label>课时名称</label><input v-model="lesForm.title" placeholder="课时名称" />
        </div>
        <div class="form-group">
          <label>内容类型</label>
          <select v-model="lesForm.content_type">
            <option value="markdown">Markdown 讲义</option>
            <option value="video">视频</option>
            <option value="notebook">Notebook</option>
          </select>
        </div>
        <div class="form-group" v-if="lesForm.content_type === 'markdown'">
          <label>内容</label><textarea v-model="lesForm.content" rows="4" placeholder="Markdown 内容"></textarea>
        </div>
        <button class="btn-primary" @click="createLesson(ch.id)">确认添加</button>
      </div>

      <div v-if="ch.lessons && ch.lessons.length">
        <div v-for="l in ch.lessons" :key="l.id"
          class="flex-between" style="padding:6px 8px;border-radius:4px">
          <span>
            <span class="badge badge-neutral text-sm">{{ l.content_type }}</span>
            <span style="margin-left:8px">{{ l.title }}</span>
          </span>
        </div>
      </div>
      <p v-else class="text-sm text-secondary">暂无课时</p>
    </div>
  </AppLayout>
</template>
