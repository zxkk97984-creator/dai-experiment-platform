import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const routes = [
  { path: '/welcome', name: 'Welcome', component: () => import('../views/WelcomeView.vue'), meta: { guest: true } },
  { path: '/login', name: 'Login', component: () => import('../views/LoginView.vue'), meta: { guest: true } },

  // Student
  { path: '/student', name: 'StudentHome', component: () => import('../views/student/DashboardView.vue'), meta: { role: 'student' } },
  { path: '/student/courses', name: 'StudentCourses', component: () => import('../views/student/CourseListView.vue'), meta: { role: 'student' } },
  { path: '/student/courses/:id', name: 'StudentCourseDetail', component: () => import('../views/student/CourseDetailView.vue'), meta: { role: 'student' } },
  { path: '/student/courses/:id/lessons/:lid', name: 'StudentLesson', component: () => import('../views/student/LessonView.vue'), meta: { role: 'student' } },
  { path: '/student/assignments', name: 'StudentAssignments', component: () => import('../views/student/AssignmentListView.vue'), meta: { role: 'student' } },
  { path: '/student/assignments/:id', name: 'StudentAssignmentDetail', component: () => import('../views/student/AssignmentDetailView.vue'), meta: { role: 'student' } },
  { path: '/student/submissions/:id', name: 'StudentSubmission', component: () => import('../views/student/SubmissionView.vue'), meta: { role: 'student' } },
  { path: '/student/exams', name: 'StudentExams', component: () => import('../views/student/ExamListView.vue'), meta: { role: 'student' } },
  { path: '/student/exams/:id', name: 'StudentExam', component: () => import('../views/student/ExamView.vue'), meta: { role: 'student' } },
  { path: '/student/experiments', name: 'StudentExperiments', component: () => import('../views/student/ExperimentView.vue'), meta: { role: 'student' } },
  { path: '/student/experiments/:id', name: 'StudentExperimentDetail', component: () => import('../views/student/ExperimentDetailView.vue'), meta: { role: 'student' } },
  { path: '/student/courses/:id/notebook/:lid', name: 'StudentNotebook', component: () => import('../views/student/NotebookView.vue'), meta: { role: 'student' } },

  // Teacher
  { path: '/teacher', name: 'TeacherHome', component: () => import('../views/teacher/DashboardView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/courses', name: 'TeacherCourses', component: () => import('../views/teacher/CourseManageView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/courses/:id/manage', name: 'TeacherChapterManage', component: () => import('../views/teacher/ChapterManageView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/assignments', name: 'TeacherAssignments', component: () => import('../views/teacher/AssignmentManageView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/assignments/:id/edit', name: 'TeacherAssignmentQuestionEdit', component: () => import('../views/teacher/QuestionEditView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/exams', name: 'TeacherExams', component: () => import('../views/teacher/ExamManageView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/exams/:id/grades', name: 'TeacherGrades', component: () => import('../views/teacher/GradesView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/exams/:id/edit', name: 'TeacherExamQuestionEdit', component: () => import('../views/teacher/ExamQuestionEditView.vue'), meta: { role: 'teacher' } },
 { path: '/teacher/experiments', name: 'TeacherExperiments', component: () => import('../views/teacher/ExperimentManageView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/courses/:id/studio/:lid', name: 'TeacherStudio', component: () => import('../views/teacher/StudioView.vue'), meta: { role: 'teacher' } },

  // Admin
  { path: '/admin', name: 'AdminHome', component: () => import('../views/admin/DashboardView.vue'), meta: { role: 'admin' } },
  { path: '/admin/users', name: 'AdminUsers', component: () => import('../views/admin/UserListView.vue'), meta: { role: 'admin' } },
  { path: '/admin/users/:id/edit', name: 'AdminUserEdit', component: () => import('../views/admin/UserEditView.vue'), meta: { role: 'admin' } },
  { path: '/admin/courses', name: 'AdminCourses', component: () => import('../views/teacher/CourseManageView.vue'), meta: { role: 'admin' } },
  { path: '/admin/experiments', name: 'AdminExperiments', component: () => import('../views/admin/ExperimentManageView.vue'), meta: { role: 'admin' } },

  // Developer
  { path: '/developer/templates', name: 'DeveloperTemplates', component: () => import('../views/developer/TemplateManageView.vue'), meta: { role: 'developer' } },
  { path: '/developer/studio/:id', name: 'DeveloperStudio', component: () => import('../views/developer/StudioView.vue'), meta: { role: 'developer' } },

  { path: '/', redirect: '/welcome' },
  { path: '/:pathMatch(.*)*', redirect: '/welcome' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const roleHome = {
  student: '/student/courses',
  teacher: '/teacher/courses',
  admin: '/admin/users',
  developer: '/developer/templates',
}

let fetchMePromise = null

router.beforeEach(async (to, from, next) => {
  const auth = useAuthStore()

  // Guest-only pages (login/welcome)
  if (to.meta.guest) {
    if (auth.isAuthenticated) return next(roleHome[auth.role] || '/login')
    return next()
  }

  // Protected pages — 先尝试 cookie 恢复 session
  if (!auth.isAuthenticated) {
    const restored = await auth.tryRestoreSession()
    if (!restored) {
      return next('/login')
    }
  }

  // Restore user if page reload (deduplicate)
  if (!auth.user) {
    if (!fetchMePromise) {
      fetchMePromise = auth.fetchMe().finally(() => {
        fetchMePromise = null
      })
    }
    const u = await fetchMePromise
    if (!u) return next('/login')
  }

  // Role check
  if (to.meta.role && to.meta.role !== auth.role) {
    return next(roleHome[auth.role] || '/login')
  }

  next()
})

export default router
