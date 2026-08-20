import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { homeForRole } from './roleHome.js'

const routes = [
  { path: '/welcome', name: 'Welcome', component: () => import('../views/WelcomeView.vue'), meta: { guest: true } },
  { path: '/login', name: 'Login', component: () => import('../views/LoginView.vue'), meta: { guest: true } },

  // Student
  { path: '/student', name: 'StudentHome', component: () => import('../views/student/DashboardView.vue'), meta: { role: 'student' } },
  { path: '/student/courses', name: 'StudentCourses', component: () => import('../views/student/CourseListView.vue'), meta: { role: 'student' } },
  { path: '/student/courses/:id', name: 'StudentCourseDetail', component: () => import('../views/student/CourseDetailView.vue'), meta: { role: 'student' } },
  { path: '/student/courses/:id/lessons/:lid', name: 'StudentLesson', component: () => import('../views/student/LessonView.vue'), meta: { role: 'student' } },
  { path: '/student/assignments', name: 'StudentAssignments', component: () => import('../views/student/AssignmentListView.vue'), meta: { role: 'student' } },
  { path: '/student/feedback', name: 'StudentFeedback', component: () => import('../views/student/FeedbackListView.vue'), meta: { role: 'student' } },
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
  { path: '/teacher/courses/:courseId/manage', name: 'TeacherChapterManage', component: () => import('../views/teacher/ChapterManageView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/assignments', name: 'TeacherAssignments', component: () => import('../views/teacher/AssignmentManageView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/assignments/:id/edit', name: 'TeacherAssignmentQuestionEdit', component: () => import('../views/teacher/QuestionEditView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/exams', name: 'TeacherExams', component: () => import('../views/teacher/ExamManageView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/exams/:id/grades', name: 'TeacherGrades', component: () => import('../views/teacher/GradesView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/exams/:id/grades/:submissionId', name: 'TeacherGradeDetail', component: () => import('../views/teacher/GradeDetailView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/exams/:id/edit', name: 'TeacherExamQuestionEdit', component: () => import('../views/teacher/ExamQuestionEditView.vue'), meta: { role: 'teacher' } },
 { path: '/teacher/experiments', name: 'TeacherExperiments', component: () => import('../views/teacher/ExperimentManageView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/experiments/create', redirect: '/teacher/experiments' },
  { path: '/teacher/experiments/:id/edit', redirect: '/teacher/experiments' },
  { path: '/teacher/experiments/:id/studio/:lid', name: 'TeacherExperimentModuleStudio', component: () => import('../views/teacher/ExperimentModuleStudioView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/submissions', name: 'TeacherExperimentSubmissions', component: () => import('../views/teacher/ExperimentSubmissionsView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/submissions/unified', name: 'TeacherUnifiedSubmissions', component: () => import('../views/teacher/UnifiedSubmissionsView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/submissions/:id', name: 'TeacherExperimentSubmissionDetail', component: () => import('../views/teacher/ExperimentSubmissionDetailView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/judge-submissions/:id', name: 'TeacherJudgeSubmissionDetail', component: () => import('../views/teacher/JudgeSubmissionDetailView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/classes', name: 'TeacherClasses', component: () => import('../views/teacher/ClassRosterView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/grades', name: 'TeacherGradeStatistics', component: () => import('../views/teacher/GradeStatisticsView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/environments', name: 'TeacherEnvironments', component: () => import('../views/teacher/EnvironmentView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/settings', name: 'TeacherSettings', component: () => import('../views/teacher/SettingsView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/notifications', name: 'TeacherNotifications', component: () => import('../views/teacher/NotificationsView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/ai-grading', name: 'TeacherAIGrading', component: () => import('../views/teacher/AIGradingReviewView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/ai-grading/:id', name: 'TeacherAIGradingDetail', component: () => import('../views/teacher/AIGradingReviewDetailView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/courses/:courseId/lessons/:lessonId/edit', name: 'TeacherLessonEdit', component: () => import('../views/teacher/LessonEditView.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/courses/:id/studio/:lid', name: 'TeacherStudio', component: () => import('../views/teacher/StudioView.vue'), meta: { role: 'teacher' } },

  // Admin
  { path: '/admin', name: 'AdminHome', component: () => import('../views/admin/DashboardView.vue'), meta: { role: 'admin' } },
  { path: '/admin/users', name: 'AdminUsers', component: () => import('../views/admin/UserListView.vue'), meta: { role: 'admin' } },
  { path: '/admin/users/:id/edit', name: 'AdminUserEdit', component: () => import('../views/admin/UserEditView.vue'), meta: { role: 'admin' } },
  { path: '/admin/academics', name: 'AdminAcademics', component: () => import('../views/admin/AcademicManageView.vue'), meta: { role: 'admin' } },
  { path: '/admin/courses', name: 'AdminCourses', component: () => import('../views/teacher/CourseManageView.vue'), meta: { role: 'admin' } },
  { path: '/admin/courses/:courseId/manage', name: 'AdminCourseManage', component: () => import('../views/teacher/ChapterManageView.vue'), meta: { role: 'admin' } },
  { path: '/admin/courses/:courseId/lessons/:lessonId/edit', name: 'AdminLessonEdit', component: () => import('../views/teacher/LessonEditView.vue'), meta: { role: 'admin' } },
  { path: '/admin/courses/:id/studio/:lid', name: 'AdminCourseStudio', component: () => import('../views/teacher/StudioView.vue'), meta: { role: 'admin' } },
  { path: '/admin/experiments', name: 'AdminExperiments', component: () => import('../views/admin/ExperimentManageView.vue'), meta: { role: 'admin' } },
  { path: '/admin/environments', name: 'AdminEnvironments', component: () => import('../views/admin/EnvironmentManageView.vue'), meta: { role: 'admin' } },
  { path: '/admin/submissions', name: 'AdminExperimentSubmissions', component: () => import('../views/teacher/ExperimentSubmissionsView.vue'), meta: { role: 'admin' } },
  { path: '/admin/submissions/unified', name: 'AdminUnifiedSubmissions', component: () => import('../views/teacher/UnifiedSubmissionsView.vue'), meta: { role: 'admin' } },
  { path: '/admin/submissions/:id', name: 'AdminExperimentSubmissionDetail', component: () => import('../views/teacher/ExperimentSubmissionDetailView.vue'), meta: { role: 'admin' } },
  { path: '/admin/judge-submissions/:id', name: 'AdminJudgeSubmissionDetail', component: () => import('../views/teacher/JudgeSubmissionDetailView.vue'), meta: { role: 'admin' } },
  { path: '/admin/ai-grading', name: 'AdminAIGrading', component: () => import('../views/teacher/AIGradingReviewView.vue'), meta: { role: 'admin' } },
  { path: '/admin/ai-grading/:id', name: 'AdminAIGradingDetail', component: () => import('../views/teacher/AIGradingReviewDetailView.vue'), meta: { role: 'admin' } },

  { path: '/', redirect: '/welcome' },
  { path: '/:pathMatch(.*)*', redirect: '/welcome' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

let fetchMePromise = null

router.beforeEach(async (to, from, next) => {
  const auth = useAuthStore()

  // Guest-only pages (login/welcome)
  if (to.meta.guest) {
    if (auth.isAuthenticated) return next(homeForRole(auth.role))
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
    return next(homeForRole(auth.role))
  }

  next()
})

export default router
