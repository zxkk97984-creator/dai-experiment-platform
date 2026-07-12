<script setup>
import AppLayout from '../../components/layout/AppLayout.vue'
import { useRouter } from 'vue-router'
const router = useRouter()
</script>
<template>
  <AppLayout>
    <h1 class="page-title">教师工作台</h1>
    <div class="grid-3">
      <div class="card" style="cursor:pointer" @click="router.push('/teacher/courses')">
        <h3>课程管理</h3>
        <p class="text-sm text-secondary mt-4">创建和管理课程、章节、课时</p>
      </div>
      <div class="card" style="cursor:pointer" @click="router.push('/teacher/assignments')">
        <h3>作业管理</h3>
        <p class="text-sm text-secondary mt-4">布置作业、创建判题题目</p>
      </div>
      <div class="card" style="cursor:pointer" @click="router.push('/teacher/exams')">
        <h3>考试管理</h3>
        <p class="text-sm text-secondary mt-4">创建考试、查看成绩</p>
      </div>
    </div>
  </AppLayout>
</template>
