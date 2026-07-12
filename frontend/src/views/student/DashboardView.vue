<script setup>
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { useAuthStore } from '../../stores/auth.js'

const auth = useAuthStore()
const router = useRouter()
</script>

<template>
  <AppLayout>
    <h1 class="page-title">欢迎, {{ auth.user?.real_name || auth.user?.username }}</h1>

    <div class="grid-3">
      <div class="card" style="cursor:pointer" @click="router.push('/student/courses')">
        <h3>课程学习</h3>
        <p class="text-secondary text-sm mt-4">浏览课程、查看章节和课时内容</p>
      </div>
      <div class="card" style="cursor:pointer" @click="router.push('/student/assignments')">
        <h3>作业提交</h3>
        <p class="text-secondary text-sm mt-4">在线编写 Python 代码并提交判题</p>
      </div>
      <div class="card" style="cursor:pointer" @click="router.push('/student/jupyter')">
        <h3>在线实验</h3>
        <p class="text-secondary text-sm mt-4">通过 JupyterLab 完成交互式实验</p>
      </div>
    </div>
  </AppLayout>
</template>
