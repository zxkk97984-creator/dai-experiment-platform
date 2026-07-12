<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { assignmentsAPI } from '../../api/assignments.js'
import { useAppStore } from '../../stores/app.js'
import { statusBadge, PUBLISH_STATUS_MAP } from '../../utils/status.js'
import { formatDateTime } from '../../utils/format.js'

const router = useRouter()
const app = useAppStore()
const assignments = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    const res = await assignmentsAPI.list()
    assignments.value = res.data.items || res.data
  } catch { app.showToast('加载作业列表失败', 'error') }
  finally { loading.value = false }
})
</script>

<template>
  <AppLayout>
    <h1 class="page-title">我的作业</h1>
    <div v-if="loading" class="text-secondary">加载中...</div>
    <div v-else-if="assignments.length === 0" class="card" style="text-align:center;padding:48px">
      <p class="text-secondary">暂无作业</p>
    </div>
    <div v-else class="grid-2">
      <div v-for="a in assignments" :key="a.id" class="card"
        style="cursor:pointer" @click="router.push(`/student/assignments/${a.id}`)">
        <div class="flex-between mb-3">
          <h3 style="margin:0;font-size:15px;color:var(--accent)">{{ a.title }}</h3>
          <span class="badge" :class="'badge-' + statusBadge(PUBLISH_STATUS_MAP, a.status).color">
            {{ statusBadge(PUBLISH_STATUS_MAP, a.status).label }}
          </span>
        </div>
        <p class="text-sm text-secondary">截止: {{ formatDateTime(a.due_at) }}</p>
      </div>
    </div>
  </AppLayout>
</template>
