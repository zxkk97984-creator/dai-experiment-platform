<script setup>
import AppLayout from '../../components/layout/AppLayout.vue'
import { useRouter } from 'vue-router'
const router = useRouter()
</script>
<template>
  <AppLayout>
    <h1 class="page-title">管理后台</h1>
    <div class="grid-3">
      <div class="card" style="cursor:pointer" @click="router.push('/admin/users')">
        <h3>用户管理</h3><p class="text-sm text-secondary mt-4">创建、编辑、管理用户账号</p>
      </div>
      <div class="card" style="cursor:pointer" @click="router.push('/admin/courses')">
        <h3>课程管理</h3><p class="text-sm text-secondary mt-4">管理全部课程</p>
      </div>
      <div class="card" style="cursor:pointer" @click="router.push('/admin/experiments')">
        <h3>实验模块</h3><p class="text-sm text-secondary mt-4">配置实验模块</p>
      </div>
    </div>
  </AppLayout>
</template>
