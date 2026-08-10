# Exam Management Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the teacher exam list, grade overview, and student-grade detail experience to match the supplied visual references while keeping the existing creation and grading workflows functional.

**Architecture:** Keep the current Vue 3 + Vite application and FastAPI exam domain. Enrich the existing exam list and grade endpoints with management metadata, add a read-only submission-detail endpoint, then build responsive teacher views over those APIs using the project's current design tokens and Remix/Iconify icon system.

**Tech Stack:** Vue 3 Composition API, Vue Router, Pinia, Iconify Remix icons, FastAPI, SQLAlchemy, Vitest, Pytest.

---

### Task 1: Enrich teacher exam reporting APIs

**Files:**
- Modify: `backend/app/api/exams.py`
- Test: `backend/tests/automated/test_exam_system.py`

- [ ] **Step 1: Add API regression tests**

Add tests that create a course, enrolled students, an exam, questions, submissions, answers, and grades; assert the teacher list exposes course/question/participant metadata, the grades response includes summary plus absent students, and the submission detail returns per-question scoring without exposing hidden tests or correct answers.

- [ ] **Step 2: Run focused tests and confirm the new expectations fail**

Run: `pytest backend/tests/automated/test_exam_system.py -q`

Expected: failures for the missing management metadata and detail endpoint.

- [ ] **Step 3: Implement backward-compatible reporting payloads**

Extend teacher/admin list items with `course_title`, `question_count`, `participant_count`, and timestamps. Return grade rows with `student_name`, `student_number`, `submission_id`, status, score, submit/grade times, plus `summary` and `distribution`. Add `GET /exams/{exam_id}/grades/{submission_id}` returning exam/student metadata and ordered answer scoring details.

- [ ] **Step 4: Run focused tests**

Run: `pytest backend/tests/automated/test_exam_system.py -q`

Expected: PASS.

### Task 2: Rebuild exam management and grade views

**Files:**
- Modify: `frontend/src/views/teacher/ExamManageView.vue`
- Modify: `frontend/src/views/teacher/GradesView.vue`
- Create: `frontend/src/views/teacher/GradeDetailView.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/api/exams.js`
- Modify: `frontend/src/components/ui/AppIcon.vue`
- Test: `frontend/src/views/teacher/__tests__/ExamManageView.spec.js`
- Create: `frontend/src/views/teacher/__tests__/GradesView.spec.js`
- Create: `frontend/src/views/teacher/__tests__/GradeDetailView.spec.js`

- [ ] **Step 1: Add view tests for the supplied information architecture**

Assert the exam page renders four summary metrics, searchable/filterable rows, and existing create/publish actions; assert the grade overview renders statistics, score distribution, filters, student rows, and detail navigation; assert the detail view renders student metadata and grouped question scores.

- [ ] **Step 2: Run focused Vitest specs and confirm failures**

Run: `npm.cmd test -- --run src/views/teacher/__tests__/ExamManageView.spec.js src/views/teacher/__tests__/GradesView.spec.js src/views/teacher/__tests__/GradeDetailView.spec.js`

Expected: failures for the new controls and views.

- [ ] **Step 3: Implement the views and route**

Use code-native responsive layouts matching the screenshots: compact metric cards, bordered filter/table panels, semantic status pills, simple CSS bar and conic charts, pagination, export-to-CSV, and a read-only student result detail page. Preserve the existing create/course-picker flow and publish action.

- [ ] **Step 4: Run focused Vitest specs**

Run the command from Step 2.

Expected: PASS.

### Task 3: Verify behavior and visual fidelity

**Files:**
- Modify: `design-qa.md`

- [ ] **Step 1: Run automated verification**

Run: `npm.cmd test -- --run` and `npm.cmd run build` from `frontend`; run the focused backend test from Task 1.

Expected: all tests and production build pass.

- [ ] **Step 2: Inspect the three routes in the in-app browser**

Open `/teacher/exams`, one `/teacher/exams/:id/grades`, and one `/teacher/exams/:id/grades/:submissionId`; test search, filters, pagination, export, create modal, and detail navigation at desktop and narrow widths.

- [ ] **Step 3: Compare screenshots and record QA**

Capture the implementation at the same desktop viewport as the references, compare hierarchy, spacing, typography, borders, colors, density, and interaction states, then write `design-qa.md` with `final result: passed` only after all P0/P1/P2 issues are corrected.

