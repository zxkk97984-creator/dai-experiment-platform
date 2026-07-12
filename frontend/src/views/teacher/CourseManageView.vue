<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { coursesAPI } from '../../api/courses.js'
import { useAppStore } from '../../stores/app.js'
import { statusBadge, PUBLISH_STATUS_MAP } from '../../utils/status.js'

const router = useRouter()
const app = useAppStore()
const courses = ref([])
const loading = ref(true)
const showCreate = ref(false)
const form = ref({ title: '', description: '' })
const creating = ref(false)

async function fetch() {
  loading.value = true
  try { const res = await coursesAPI.list(); courses.value = res.data.items || res.data }
  catch { app.showToast('加载失败', 'error') }
  finally { loading.value = false }
}

async function handleCreate() {
  if (!form.value.title) return
  creating.value = true
  try {
    await coursesAPI.create(form.value)
    app.showToast('创建成功', 'success')
    showCreate.value = false
    form.value = { title: '', description: '' }
    fetch()
  } catch (e) {
    app.showToast(e.response?.data?.detail?.message || '创建失败', 'error')
  } finally { creating.value = false }
}

async function handlePublish(c) {
  try { await coursesAPI.update(c.id, { status: 'published' }); app.showToast('已发布', 'success'); fetch() }
  catch { app.showToast('操作失败', 'error') }
}

onMounted(fetch)
</script>

<template>
  <AppLayout>
    <div class="flex-between mb-4">
      <h1 class="page-title" style="margin-bottom:0">课程管理</h1>
      <button class="btn-primary" @click="showCreate = !showCreate">
        {{ showCreate ? '取消' : '创建课程' }}
      </button>
    </div>

    <div v-if="showCreate" class="card mb-4">
      <div class="form-group">
        <label>课程名称</label><input v-model="form.title" placeholder="输入课程名称" />
      </div>
      <div class="form-group">
        <label>课程简介</label><textarea v-model="form.description" rows="3" placeholder="输入课程简介"></textarea>
      </div>
      <button class="btn-primary" :disabled="creating" @click="handleCreate">
        {{ creating ? '创建中...' : '确认创建' }}
      </button>
    </div>

    <div v-if="loading" class="text-secondary">加载中...</div>
    <div v-else-if="courses.length === 0" class="card" style="text-align:center;padding:48px">
      <p class="text-secondary">暂无课程</p>
    </div>
    <table v-else class="card" style="padding:0">
      <thead><tr><th>名称</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="c in courses" :key="c.id">
          <td>
            <a @click="router.push(`/teacher/courses/${c.id}/manage`)" style="cursor:pointer">{{ c.title }}</a>
          </td>
          <td>
            <span class="badge" :class="'badge-' + statusBadge(PUBLISH_STATUS_MAP, c.status).color">
              {{ statusBadge(PUBLISH_STATUS_MAP, c.status).label }}
            </span>
          </td>
          <td>
            <button class="btn-sm" @click="router.push(`/teacher/courses/${c.id}/manage`)">章节课时</button>
            <button class="btn-sm btn-primary" v-if="c.status === 'draft'"
              @click="handlePublish(c)" style="margin-left:6px">发布</button>
          </td>
        </tr>
      </tbody>
    </table>
  </AppLayout>
</template>
