<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { examsAPI } from '../../api/exams.js'
import { useAppStore } from '../../stores/app.js'
const router = useRouter(); const app = useAppStore()
const exams = ref([]); const loading = ref(true); const showCreate = ref(false)
const form = ref({ title: '', course_id: '', duration_minutes: 60, start_at: '', end_at: '' })
function badgeClass(status) { return status === 'published' ? 'badge-success' : 'badge-neutral' }
function badgeLabel(status) { return status === 'published' ? 'published' : 'draft' }
async function fetch() { loading.value = true; try { const res = await examsAPI.list(); exams.value = res.data.items || res.data } catch { app.showToast('load err', 'error') } finally { loading.value = false } }
async function handleCreate() { if (!form.value.title) return; try { await examsAPI.create({ ...form.value, course_id: parseInt(form.value.course_id) || undefined }); app.showToast('created', 'success'); showCreate.value = false; fetch() } catch (e) { app.showToast(e.response?.data?.detail?.message || 'err', 'error') } }
async function publishExam(id) { try { await examsAPI.update(id, { status: 'published' }); app.showToast('published', 'success'); fetch() } catch (e) { app.showToast(e.response?.data?.detail?.message || 'err', 'error') } }
onMounted(fetch)
</script>
<template>
  <AppLayout>
    <div class="tb"><h1 class="t">Exams</h1><button class="btn" @click="showCreate = !showCreate">{{ showCreate ? 'cancel' : 'new' }}</button></div>
    <div v-if="showCreate" class="card"><div class="fg"><label>title</label><input v-model="form.title" /></div><div class="fg"><label>course ID</label><input v-model="form.course_id" type="number" /></div><div class="fg"><label>duration (min)</label><input v-model.number="form.duration_minutes" type="number" /></div><div class="fg"><label>start</label><input v-model="form.start_at" type="datetime-local" /></div><button class="btn" @click="handleCreate">create</button></div>
    <div v-if="loading">loading...</div>
    <table v-else-if="exams.length" class="dt"><thead><tr><th>title</th><th>status</th><th>duration</th><th>actions</th></tr></thead><tbody><tr v-for="e in exams" :key="e.id"><td>{{ e.title }}</td><td><span class="badge" :class="badgeClass(e.status)">{{ badgeLabel(e.status) }}</span></td><td>{{ e.duration_minutes }} min</td><td class="ac"><button class="b" @click="router.push('/teacher/exams/'+e.id+'/edit')">questions</button><button class="b" @click="router.push('/teacher/exams/'+e.id+'/grades')">grades</button><button v-if="e.status==='draft'" class="b ba" @click="publishExam(e.id)">publish</button></td></tr></tbody></table>
    <div v-else class="card" style="text-align:center;padding:48px"><p>no exams</p></div>
  </AppLayout>
</template>
<style scoped>
.tb{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.t{font-size:20px;font-weight:600;margin:0}
.btn{padding:8px 16px;background:var(--accent,#f97316);color:#fff;border:none;border-radius:6px;font-size:13px;font-weight:500;cursor:pointer}
.card{background:var(--surface,#fff);border:1px solid var(--border,#e5e7eb);border-radius:8px;padding:16px;margin-bottom:16px}
.fg{display:flex;flex-direction:column;gap:4px;margin-bottom:8px}
.fg label{font-size:11px;color:var(--text-secondary,#6b7280)}
.fg input{padding:6px 10px;border:1px solid var(--border,#d1d5db);border-radius:4px;font-size:13px}
.dt{width:100%;border-collapse:collapse;font-size:13px;background:var(--surface,#fff);border:1px solid var(--border,#e5e7eb);border-radius:8px;overflow:hidden}
.dt th{background:var(--surface-sunken,#f9fafb);color:var(--text-secondary,#6b7280);padding:8px 12px;text-align:left}
.dt td{padding:8px 12px;border-bottom:1px solid var(--border,#e5e7eb)}
.badge{font-size:10px;padding:2px 8px;border-radius:3px}
.badge-neutral{background:#eff6ff;color:#2563eb}
.badge-success{background:#dcfce7;color:#16a34a}
.ac{display:flex;gap:4px}
.b{padding:4px 8px;border:1px solid var(--border,#d1d5db);border-radius:4px;background:var(--surface,#fff);font-size:11px;cursor:pointer}
.b:hover{background:var(--surface-raised,#f3f4f6)}
.ba{background:var(--accent,#f97316);color:#fff;border-color:var(--accent,#f97316)}
</style>
