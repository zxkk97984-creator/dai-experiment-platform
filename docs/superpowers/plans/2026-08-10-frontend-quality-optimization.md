# Frontend Quality Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the current Vue 3 redesign while removing misleading UI behavior, preventing stale list responses, consolidating repeated presentation logic, and adding repeatable frontend quality gates.

**Architecture:** Keep route views responsible for orchestration and API calls. Move reusable state transitions into small composables/utilities, and extract only repeated or independently testable view sections. Each phase remains independently shippable; this plan does not require backend redesign or a TypeScript migration.

**Tech Stack:** Vue 3 Composition API, Vue Router 4, Pinia 2, Vite 6, Vitest 4, Vue Test Utils, Playwright.

---

## Audit baseline

- Healthy baseline: 72 Vitest files and 718 tests pass; `vite build` succeeds.
- Route-level lazy loading is already used throughout `frontend/src/router/index.js`.
- Current frontend changes add roughly 3,800 lines across student experiments, teacher experiment review, exam management, and grade views.
- Concrete gaps found:
  - `ExperimentManageView.vue` has an `编辑模块` button with no handler.
  - `GradeDetailView.vue` has an `导出报告` button with no handler.
  - Course, assignment, and experiment management views show static pagination text rather than state-backed controls.
  - Teacher submission and AI-review lists can let an older slow request overwrite a newer filtered result; the student experiment list already guards against this locally.
  - Date formatting and status labels are duplicated despite existing format/status utilities.
  - `package.json` has no lint/check script.

## Target file map

- Create `frontend/src/composables/useClientPagination.js` and its unit test.
- Create `frontend/src/utils/latestRequest.js` and its unit test.
- Modify `frontend/src/utils/format.js` and `frontend/src/utils/status.js` plus utility tests.
- Modify the affected student/teacher route views and their colocated specs.
- Extract four stable presentational components from the largest changed views.
- Create `frontend/eslint.config.js`; modify package scripts and lockfile.
- Extend existing Playwright flows under `frontend/e2e/`.

### Task 1: Repair misleading controls and pagination

**Files:**
- Create: `frontend/src/composables/useClientPagination.js`
- Create: `frontend/src/composables/__tests__/useClientPagination.spec.js`
- Modify: `frontend/src/views/teacher/CourseManageView.vue`
- Modify: `frontend/src/views/teacher/AssignmentManageView.vue`
- Modify: `frontend/src/views/teacher/ExperimentManageView.vue`
- Modify: `frontend/src/views/teacher/GradeDetailView.vue`
- Test: corresponding files in `frontend/src/views/teacher/__tests__/`

- [ ] **Step 1: Write failing interaction tests**

Mount each management view with 12 records, assert 10 rows on page 1, click page 2, and assert 2 rows. Add an experiment test that edits a module and expects `updateModule`. Add a grade-detail test that asserts the inert export control is gone and the print/PDF action calls `window.print()`.

```js
it('paginates modules and edits the selected module', async () => {
  experimentsAPI.listModules.mockResolvedValue({ data: { items: makeModules(12) } })
  experimentsAPI.updateModule.mockResolvedValue({ data: { id: 1, name: '新名称' } })
  const wrapper = mountView()
  await flushPromises()
  expect(wrapper.findAll('tbody tr')).toHaveLength(10)
  await wrapper.get('[aria-label="第 2 页"]').trigger('click')
  expect(wrapper.findAll('tbody tr')).toHaveLength(2)
  await wrapper.findAll('[data-action="edit-module"]')[0].trigger('click')
  await wrapper.get('[name="module-name"]').setValue('新名称')
  await wrapper.get('[data-action="save-module"]').trigger('click')
  expect(experimentsAPI.updateModule).toHaveBeenCalledWith(1, expect.objectContaining({ name: '新名称' }))
})
```

- [ ] **Step 2: Run the focused specs and verify failure**

```bash
npm.cmd test -- src/views/teacher/__tests__/CourseManageView.spec.js src/views/teacher/__tests__/AssignmentManageView.spec.js src/views/teacher/__tests__/ExperimentManageView.spec.js src/views/teacher/__tests__/GradeDetailView.spec.js
```

Expected: failures for absent page controls, missing edit behavior, and the inert report control.

- [ ] **Step 3: Implement shared client pagination**

```js
import { computed, ref, unref, watch } from 'vue'

export function useClientPagination(source, initialPageSize = 10) {
  const page = ref(1)
  const pageSize = ref(initialPageSize)
  const pageCount = computed(() => Math.max(1, Math.ceil(unref(source).length / pageSize.value)))
  const pagedItems = computed(() => {
    const start = (page.value - 1) * pageSize.value
    return unref(source).slice(start, start + pageSize.value)
  })
  function goToPage(value) {
    page.value = Math.min(Math.max(Number(value) || 1, 1), pageCount.value)
  }
  function resetPage() { page.value = 1 }
  watch(pageCount, (count) => { if (page.value > count) page.value = count })
  return { page, pageSize, pageCount, pagedItems, goToPage, resetPage }
}
```

Use `pagedItems` in all three table bodies, replace static footer text with real previous/page/next buttons, and call `resetPage()` on filter changes.

- [ ] **Step 4: Make experiment editing functional**

```js
const editingId = ref(null)

function openEditModal(module) {
  editingId.value = module.id
  form.value = { name: module.name || '', description: module.description || '', entry_url: module.entry_url || '' }
  createOpen.value = true
}

async function saveModule() {
  const payload = { ...form.value, name: form.value.name.trim() }
  if (!payload.name) return app.showToast('请输入实验名称', 'error')
  if (editingId.value) await experimentsAPI.updateModule(editingId.value, payload)
  else await experimentsAPI.createModule(payload)
  closeCreateModal()
  await fetch()
}
```

In `GradeDetailView.vue`, remove the inert export button and rename the working print action to `打印 / 保存 PDF`; browser print already supports both paths.

- [ ] **Step 5: Re-run focused tests and commit**

Expected: all four focused specs pass.

```bash
git add frontend/src/composables frontend/src/views/teacher
git commit -m "fix(frontend): repair management list interactions"
```

### Task 2: Prevent stale server-list responses

**Files:**
- Create: `frontend/src/utils/latestRequest.js`
- Create: `frontend/src/utils/__tests__/latestRequest.spec.js`
- Modify: `frontend/src/views/student/ExperimentView.vue`
- Modify: `frontend/src/views/teacher/ExperimentSubmissionsView.vue`
- Modify: `frontend/src/views/teacher/AIGradingReviewView.vue`
- Test: their existing specs

- [ ] **Step 1: Write request-order tests**

```js
it('accepts only the newest request token', () => {
  const guard = createLatestRequestGuard()
  const first = guard.begin()
  const second = guard.begin()
  expect(guard.isLatest(first)).toBe(false)
  expect(guard.isLatest(second)).toBe(true)
  guard.invalidate()
  expect(guard.isLatest(second)).toBe(false)
})
```

In component specs, create two deferred API promises; resolve the newer filtered call first and the older call last, then assert the table retains the newer result.

- [ ] **Step 2: Implement the guard**

```js
export function createLatestRequestGuard() {
  let sequence = 0
  return {
    begin() { sequence += 1; return sequence },
    isLatest(token) { return token === sequence },
    invalidate() { sequence += 1 },
  }
}
```

- [ ] **Step 3: Apply it consistently**

At each `load` start, call `const token = guard.begin()`. Check `guard.isLatest(token)` before updating items, totals, error, or loading state. Call `invalidate()` during unmount. Replace the private counter in `ExperimentView.vue` with this utility.

- [ ] **Step 4: Keep AI summary requests parallel but independent of filters**

Initial load remains parallel:

```js
await Promise.all([load(), loadSummary()])
```

Filter changes call only `load()` because the summary represents global counts.

- [ ] **Step 5: Verify and commit**

```bash
npm.cmd test -- src/utils/__tests__/latestRequest.spec.js src/views/student/__tests__/ExperimentView.spec.js src/views/teacher/__tests__/ExperimentSubmissionsView.spec.js src/views/teacher/__tests__/AIGradingReview.spec.js
npm.cmd test
git add frontend/src/utils/latestRequest.js frontend/src/utils/__tests__/latestRequest.spec.js frontend/src/views
git commit -m "fix(frontend): ignore stale list responses"
```

Expected: stale-response cases pass and the full suite remains green.

### Task 3: Consolidate dates and statuses

**Files:**
- Modify: `frontend/src/utils/format.js`
- Modify: `frontend/src/utils/status.js`
- Create: `frontend/src/utils/__tests__/format.spec.js`
- Modify: `frontend/src/views/teacher/ExamManageView.vue`
- Modify: `frontend/src/views/teacher/ExperimentManageView.vue`
- Modify: `frontend/src/views/teacher/GradesView.vue`
- Modify: `frontend/src/views/teacher/GradeDetailView.vue`
- Modify: `frontend/src/views/teacher/AIGradingReviewView.vue`

- [ ] **Step 1: Add failing formatter tests**

```js
it('handles empty, invalid, and second-precision values', () => {
  expect(formatDateTime()).toBe('—')
  expect(formatDateTime('not-a-date')).toBe('—')
  expect(formatDateTime('2026-08-10T08:00:30+08:00', { seconds: true })).toMatch(/30/)
})
```

- [ ] **Step 2: Implement one safe formatter**

```js
export function formatDateTime(value, { seconds = false } = {}) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
    ...(seconds ? { second: '2-digit' } : {}),
    hour12: false,
  }).format(date).replaceAll('/', '-')
}
```

- [ ] **Step 3: Add and consume canonical grade statuses**

```js
export const EXAM_GRADE_STATUS_MAP = {
  graded: { label: '已评分', color: 'success' },
  review_required: { label: '待复核', color: 'warning' },
  grading: { label: '评分中', color: 'info' },
  submitted: { label: '已交卷', color: 'info' },
  started: { label: '进行中', color: 'info' },
  absent: { label: '缺考', color: 'neutral' },
}
```

Replace local formatter/status functions with imports from `format.js` and `status.js`; preserve the rendered labels and tones.

- [ ] **Step 4: Verify and commit**

```bash
npm.cmd test -- src/utils src/views/teacher/__tests__
git add frontend/src/utils frontend/src/views/teacher
git commit -m "refactor(frontend): centralize display formatting"
```

### Task 4: Split large views at stable component boundaries

**Files:**
- Create: `frontend/src/components/student/ExperimentCatalog.vue`
- Create: `frontend/src/components/teacher/exam/ExamCreateDialog.vue`
- Create: `frontend/src/components/teacher/exam/ExamAnswerGroups.vue`
- Create: `frontend/src/components/teacher/SubmissionReviewPanel.vue`
- Modify: `frontend/src/views/student/ExperimentView.vue`
- Modify: `frontend/src/views/teacher/ExamManageView.vue`
- Modify: `frontend/src/views/teacher/GradeDetailView.vue`
- Modify: `frontend/src/views/teacher/ExperimentSubmissionDetailView.vue`
- Test: colocated component specs

- [ ] **Step 1: Write component contract tests**

Test props and emitted events rather than internal refs. The catalog emits `retry`, `page`, and `open`; the exam dialog emits `save` and `close`; answer groups emit `toggle`; the review panel emits `submit`.

```js
it('emits a normalized exam payload', async () => {
  const wrapper = mount(ExamCreateDialog, { props: { open: true, courses: [] } })
  await wrapper.get('[name="title"]').setValue('期末考试')
  await wrapper.get('[name="course-id"]').setValue('2')
  await wrapper.get('form').trigger('submit')
  expect(wrapper.emitted('save')[0][0]).toEqual(expect.objectContaining({
    title: '期末考试', course_id: 2, duration_minutes: 60,
  }))
})
```

- [ ] **Step 2: Extract presentation without moving API ownership**

Use explicit prop/event contracts like this:

```js
defineProps({
  items: { type: Array, required: true },
  loading: Boolean,
  failed: Boolean,
  total: { type: Number, required: true },
  page: { type: Number, required: true },
  pageCount: { type: Number, required: true },
})
defineEmits(['retry', 'page', 'open'])
```

Keep route access, API clients, stores, and toast calls in route views. Move scoped styles with their markup and format only the touched selectors.

- [ ] **Step 3: Verify and commit**

```bash
npm.cmd test -- src/components/student src/components/teacher src/views/student/__tests__/ExperimentView.spec.js src/views/teacher/__tests__
npm.cmd run build
git add frontend/src/components frontend/src/views
git commit -m "refactor(frontend): split large workflow views"
```

Expected: component and route tests pass; production chunks remain route-lazy.

### Task 5: Add lint and a single verification command

**Files:**
- Create: `frontend/eslint.config.js`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`

- [ ] **Step 1: Install the Vue ESLint toolchain**

```bash
npm.cmd install --save-dev eslint eslint-plugin-vue globals
```

- [ ] **Step 2: Add the flat ESLint config**

```js
import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'

export default [
  { ignores: ['dist/**', 'coverage/**', 'node_modules/**'] },
  js.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  {
    files: ['src/**/*.{js,vue}', 'e2e/**/*.js'],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: {
      'no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      'vue/multi-word-component-names': 'off',
      'vue/no-v-html': 'error',
    },
  },
]
```

- [ ] **Step 3: Add package scripts**

```json
{
  "scripts": {
    "lint": "eslint src e2e",
    "lint:fix": "eslint src e2e --fix",
    "check": "npm run lint && npm test && npm run build"
  }
}
```

- [ ] **Step 4: Fix lint errors in touched files and run the gate**

```bash
npm.cmd run check
```

Expected: lint, all unit tests, and production build pass. Do not mix a repository-wide formatting rewrite into this branch.

- [ ] **Step 5: Commit the quality gate**

```bash
git add frontend/package.json frontend/package-lock.json frontend/eslint.config.js frontend/src frontend/e2e
git commit -m "chore(frontend): add lint and verification gate"
```

### Task 6: Verify repaired workflows end to end

**Files:**
- Modify: `frontend/e2e/exam-flow.spec.js`
- Modify: `frontend/e2e/experiment-flow.spec.js`
- Modify: `frontend/e2e/student-reference-ui.spec.js`

- [ ] **Step 1: Add focused E2E assertions**

Cover editing an experiment and seeing it after reload, real management pagination, rapid submission filtering retaining the newest result, and grade-detail print/PDF behavior.

```js
test('teacher edits a module and sees the persisted name', async ({ page }) => {
  await page.goto('/teacher/experiments')
  await page.getByRole('button', { name: '编辑模块' }).first().click()
  await page.getByLabel('实验名称').fill('E2E 实验模块')
  await page.getByRole('button', { name: '保存' }).click()
  await expect(page.getByText('E2E 实验模块')).toBeVisible()
  await page.reload()
  await expect(page.getByText('E2E 实验模块')).toBeVisible()
})
```

- [ ] **Step 2: Run focused and full gates**

```bash
npm.cmd run e2e -- e2e/exam-flow.spec.js e2e/experiment-flow.spec.js e2e/student-reference-ui.spec.js
npm.cmd run check
npm.cmd run e2e
```

Expected: all unit, build, lint, and E2E checks pass without retries masking failures.

- [ ] **Step 3: Commit E2E coverage**

```bash
git add frontend/e2e
git commit -m "test(frontend): cover redesigned management workflows"
```

## Recommended execution order

1. Tasks 1-3 first: real interaction and data-consistency fixes with small diffs.
2. Task 4 separately: a maintainability refactor that should not obscure functional repairs.
3. Tasks 5-6 last: stabilize behavior, then make the new gate mandatory.

## Self-review result

- Spec coverage: behavior, request ordering, maintainability, unit tests, build, lint, and E2E are covered.
- Placeholder scan: every implementation step contains a concrete action, command, or code contract.
- Type/name consistency: proposed composable exports and event names are consistent.
- Deliberate non-goals: no TypeScript migration, state-library replacement, design-system rewrite, or backend pagination redesign.
