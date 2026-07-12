<script setup>
import { ref, onMounted } from 'vue'
import AppLayout from '../../components/layout/AppLayout.vue'
import { jupyterAPI } from '../../api/jupyter.js'
import { useAppStore } from '../../stores/app.js'

const app = useAppStore()
const iframeUrl = ref('')
const loading = ref(true)
const error = ref('')

async function loadJupyter() {
  loading.value = true
  error.value = ''
  try {
    const res = await jupyterAPI.getEntry()
    iframeUrl.value = res.data.iframe_url
  } catch (e) {
    error.value = '无法获取 JupyterLab 地址'
    app.showToast(error.value, 'error')
  } finally { loading.value = false }
}

onMounted(loadJupyter)
</script>

<template>
  <AppLayout>
    <h1 class="page-title">JupyterLab</h1>
    <div v-if="loading" class="card" style="text-align:center;padding:48px">
      <p class="text-secondary">正在连接 JupyterLab...</p>
    </div>
    <div v-else-if="error" class="card" style="text-align:center;padding:48px">
      <p class="text-secondary">{{ error }}</p>
      <button class="btn-primary mt-4" @click="loadJupyter">重试</button>
    </div>
    <div v-else class="card" style="padding:0;overflow:hidden;height:calc(100vh - 160px)">
      <iframe :src="iframeUrl" style="width:100%;height:100%;border:none"></iframe>
    </div>
  </AppLayout>
</template>
