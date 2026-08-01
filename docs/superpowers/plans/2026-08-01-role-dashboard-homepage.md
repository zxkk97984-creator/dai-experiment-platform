# Student and Teacher Home Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/student` and `/teacher` the real post-login homepages, backed by role-scoped live data and a shared announcement system where admins publish global notices, teachers publish notices to courses they own, and students can mark visible notices read.

**Architecture:** Add announcement persistence and a thin permissioned announcement API, then add one role-aware dashboard service exposed through separate student and teacher endpoints. The Vue dashboards consume one aggregate request each, reuse a shared announcement panel/composer, and preserve the repository's existing light design tokens and application shell. Login, guard fallback, logo navigation, and sidebar home entries all use one shared role-home mapping.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Pydantic, pytest, Vue 3 Composition API, Pinia, Vue Router, Axios, Vitest, Vue Test Utils, Vite.

---

## Scope and safety constraints

- Work in the existing checkout. Do not create a worktree, reset files, or clean untracked files.
- The worktree already contains unrelated user changes, including AI grading work and Welcome page work. Never overwrite, revert, reformat, stage, or commit those changes.
- Do not touch `frontend/src/views/WelcomeView.vue` or `frontend/src/components/welcome/**`.
- Avoid editing the currently dirty `backend/app/api/assignments.py`, `backend/app/services/ai_prompts.py`, `backend/app/services/exam_service.py`, and AI-result frontend files. Dashboard aggregation must read existing models rather than modify those flows.
- Do not make git commits in this shared dirty checkout. Use the task-level tests and `git diff --check` as checkpoints.
- Do not add a charting or icon dependency. Use typography, status dots, CSS, and the existing production-quality inline SVG treatment only where a directional control needs it.
- Do not render announcement content as HTML. Treat it as plain text.
- V1 intentionally excludes announcement attachments, comments, rich text, scheduling, editing, deleting, and an admin management page.

## Product behavior locked by the approved design

### Shared layout

- Replace the large decorative hero with a compact greeting row containing the role-appropriate greeting, current date, and one context-sensitive primary action.
- The first content row is task-first: the main work list occupies roughly two-thirds of desktop width and announcements occupy roughly one-third.
- Summary metrics are a restrained horizontal strip, not a grid of decorative cards.
- Existing sidebar/header shell and global tokens remain the visual source of truth.
- At `<= 1024px`, the two-column content becomes one column. At `<= 768px`, summaries wrap to two columns and all content remains readable without horizontal scrolling.
- Every async region has loading, retryable error, populated, and truthful empty states.

### Student homepage

- Primary list: incomplete assignments ordered by due date, upcoming exams ordered by start time, then active experiments ordered by last activity.
- One “continue learning” action returns to the most recently updated lesson experiment, module experiment, or enrolled course.
- Show enrolled-course snapshots using real counts (`pending_assignments`, `upcoming_exams`) instead of inventing a lesson-completion percentage that the current data model cannot support.
- Show the latest real feedback from graded assignment question submissions, graded exams, and reviewed experiment submissions.
- Show visible global and enrolled-course announcements and allow idempotent mark-as-read.

### Teacher homepage

- Primary work queue: AI grades needing review, unreviewed experiment submissions, and assignment deadlines with incomplete student participation.
- Summary: managed courses, distinct enrolled students, pending review items, and deadlines in the next seven days.
- Show course health rows with enrolled student count, pending review count, and imminent-deadline count.
- Show recent real submissions/activity, not seeded constants.
- Show global notices plus notices for owned courses. A teacher can publish a plain-text notice to one owned course from the panel.

### Announcement permissions

- `admin`: may publish `scope="global"` only.
- `teacher`: may publish `scope="course"` only, and only for a course whose `teacher_id` matches the current user.
- `student`: cannot publish.
- Visibility: global announcements are visible to students and teachers; course announcements are visible only to the owning teacher, admins, and students with an `enrolled` enrollment in that course.
- Archived announcements and announcements whose `expires_at <= now` are hidden.
- Mark-read is idempotent and only succeeds for an announcement currently visible to the caller.

## API contracts

`POST /api/v1/announcements`

```json
{
  "title": "实验课机房调整",
  "content": "本周实验课调整到 A302。",
  "priority": "important",
  "scope": "course",
  "course_id": 12,
  "expires_at": "2026-08-08T00:00:00Z"
}
```

`POST /api/v1/announcements/{announcement_id}/read` returns `204` and is idempotent.

`GET /api/v1/dashboard/student` returns:

```json
{
  "summary": {
    "course_count": 2,
    "pending_assignment_count": 1,
    "upcoming_exam_count": 1,
    "unread_announcement_count": 2
  },
  "priority_items": [
    {
      "kind": "assignment",
      "id": 4,
      "title": "特征工程",
      "course_title": "机器学习导论",
      "time_at": "2026-08-02T15:59:00Z",
      "urgency": "urgent",
      "route": "/student/assignments/4"
    }
  ],
  "continue_learning": {
    "kind": "lesson_experiment",
    "title": "决策树实验",
    "subtitle": "机器学习导论",
    "updated_at": "2026-08-01T05:10:00Z",
    "route": "/student/courses/2/notebook/8"
  },
  "courses": [
    {
      "id": 2,
      "title": "机器学习导论",
      "pending_assignment_count": 1,
      "upcoming_exam_count": 1,
      "last_activity_at": "2026-08-01T05:10:00Z",
      "route": "/student/courses/2"
    }
  ],
  "recent_feedback": [],
  "announcements": []
}
```

`GET /api/v1/dashboard/teacher` returns:

```json
{
  "summary": {
    "course_count": 2,
    "student_count": 46,
    "pending_review_count": 7,
    "upcoming_deadline_count": 3
  },
  "work_items": [],
  "course_health": [],
  "recent_activity": [],
  "managed_courses": [{"id": 2, "title": "机器学习导论"}],
  "announcements": []
}
```

Dashboard collection items use these exact field sets:

```json
{
  "student_feedback": {
    "kind": "experiment",
    "id": 21,
    "title": "决策树实验反馈",
    "course_title": "机器学习导论",
    "score": 92.0,
    "feedback": "特征选择解释清晰。",
    "graded_at": "2026-08-01T06:00:00Z",
    "route": "/student/experiments/7"
  },
  "teacher_work_item": {
    "kind": "experiment_review",
    "id": 21,
    "title": "张同学提交了决策树实验",
    "course_id": 2,
    "course_title": "机器学习导论",
    "detail": "等待教师反馈",
    "time_at": "2026-08-01T05:40:00Z",
    "urgency": "soon",
    "route": "/teacher/submissions/21"
  },
  "course_health": {
    "course_id": 2,
    "title": "机器学习导论",
    "student_count": 24,
    "pending_review_count": 3,
    "upcoming_deadline_count": 1,
    "at_risk_submitted_count": 18,
    "at_risk_expected_count": 24,
    "route": "/teacher/courses/2/manage"
  },
  "teacher_activity": {
    "kind": "experiment_submission",
    "id": 21,
    "title": "张同学提交了决策树实验",
    "course_title": "机器学习导论",
    "actor_name": "张同学",
    "happened_at": "2026-08-01T05:40:00Z",
    "route": "/teacher/submissions/21"
  }
}
```

Every announcement item has this stable shape:

```json
{
  "id": 9,
  "title": "实验课机房调整",
  "content": "本周实验课调整到 A302。",
  "priority": "important",
  "scope": "course",
  "course_id": 2,
  "course_title": "机器学习导论",
  "author_name": "王老师",
  "published_at": "2026-08-01T04:00:00Z",
  "expires_at": null,
  "is_read": false
}
```

## File map

**Backend create:**

- `backend/alembic/versions/b8c9d0e1f234_add_announcements.py` — announcement and read-receipt tables.
- `backend/app/schemas/announcements.py` — create/read response models.
- `backend/app/schemas/dashboard.py` — stable role-dashboard response models.
- `backend/app/api/announcements.py` — publish and mark-read endpoints plus visibility helper.
- `backend/app/api/dashboard.py` — two thin dashboard endpoints.
- `backend/app/services/dashboard_service.py` — all aggregation and ordering logic.
- `backend/tests/automated/test_announcements.py` — permission, visibility, expiry, and read tests.
- `backend/tests/automated/test_dashboard.py` — student/teacher aggregation tests.

**Backend modify:**

- `backend/app/models/__init__.py` — `Announcement` and `AnnouncementRead` SQLAlchemy models.
- `backend/app/api/__init__.py` — register announcement and dashboard routers.

**Frontend create:**

- `frontend/src/api/dashboard.js` — aggregate dashboard requests.
- `frontend/src/api/announcements.js` — publish and mark-read requests.
- `frontend/src/router/roleHome.js` — single role-to-home mapping.
- `frontend/src/components/dashboard/AnnouncementPanel.vue` — shared notice list and read action.
- `frontend/src/components/dashboard/AnnouncementComposer.vue` — teacher course-notice modal.
- `frontend/src/components/dashboard/DashboardAsyncState.vue` — loading/error/empty presentation.
- `frontend/src/components/dashboard/__tests__/AnnouncementPanel.spec.js`.
- `frontend/src/views/student/__tests__/DashboardView.spec.js`.
- `frontend/src/views/teacher/__tests__/DashboardView.spec.js`.
- `frontend/src/router/__tests__/role-home.spec.js`.

**Frontend modify:**

- `frontend/src/views/student/DashboardView.vue` — replace mocked homepage with task-first live view.
- `frontend/src/views/teacher/DashboardView.vue` — replace mixed mock/count calls with aggregate live view and composer.
- `frontend/src/views/LoginView.vue` — redirect student and teacher to their dashboard routes.
- `frontend/src/router/index.js` — use the shared role-home mapping for guest/role redirects.
- `frontend/src/components/layout/AppSidebar.vue` — add role-specific Home item and exact-match root activity; logo returns home.
- `frontend/src/components/layout/__tests__/AppSidebar.spec.js` — cover Home entries and logo behavior.

### Task 1: Persist announcements and read receipts

**Files:**

- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/b8c9d0e1f234_add_announcements.py`
- Test: `backend/tests/automated/test_announcements.py`

- [ ] **Step 1: Write the failing model test**

Add a test that creates one global announcement and one read receipt, verifies the unique `(announcement_id, user_id)` constraint, and verifies nullable `course_id`/`expires_at` work on SQLite.

```python
def test_announcement_models_persist_read_receipt(db_session_factory):
    from sqlalchemy.exc import IntegrityError
    from app.models import Announcement, AnnouncementRead
    from conftest import create_user

    admin = create_user(db_session_factory, "notice-admin", "admin")
    student = create_user(db_session_factory, "notice-student", "student")
    with db_session_factory() as db:
        notice = Announcement(
            title="平台维护",
            content="今晚 22:00 维护。",
            priority="important",
            scope="global",
            author_id=admin.id,
        )
        db.add(notice)
        db.flush()
        db.add(AnnouncementRead(announcement_id=notice.id, user_id=student.id))
        db.commit()
        assert notice.course_id is None
        assert notice.expires_at is None

        db.add(AnnouncementRead(announcement_id=notice.id, user_id=student.id))
        with pytest.raises(IntegrityError):
            db.commit()
```

- [ ] **Step 2: Run the model test and confirm it fails before the model exists**

Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\automated\test_announcements.py -q`

Expected: collection/import failure naming `Announcement` or `AnnouncementRead`.

- [ ] **Step 3: Add the two SQLAlchemy models**

Use string columns rather than database enums so MySQL and SQLite behave consistently:

```python
class Announcement(TimestampMixin, Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    content: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), default="normal", index=True)
    scope: Mapped[str] = mapped_column(String(20), index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), nullable=True, index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    course: Mapped[Course | None] = relationship()
    author: Mapped[User] = relationship()


class AnnouncementRead(Base):
    __tablename__ = "announcement_reads"
    __table_args__ = (
        UniqueConstraint("announcement_id", "user_id", name="uq_announcement_read_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    announcement_id: Mapped[int] = mapped_column(ForeignKey("announcements.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 4: Add the Alembic migration**

Set `revision = "b8c9d0e1f234"` and `down_revision = "a7b8c9d0e112"`. Create indexes matching the model and both foreign-key cascades. The downgrade drops `announcement_reads` before `announcements`.

- [ ] **Step 5: Run the model test and migration syntax check**

Run:

```bat
backend\.venv\Scripts\python.exe -m pytest backend\tests\automated\test_announcements.py -q
backend\.venv\Scripts\python.exe -m py_compile backend\alembic\versions\b8c9d0e1f234_add_announcements.py
```

Expected: model test passes; `py_compile` exits `0`.

### Task 2: Implement announcement permissions, visibility, publishing, and read state

**Files:**

- Create: `backend/app/schemas/announcements.py`
- Create: `backend/app/api/announcements.py`
- Modify: `backend/app/api/__init__.py`
- Test: `backend/tests/automated/test_announcements.py`

- [ ] **Step 1: Add failing API tests**

Cover all of these assertions in separate tests:

```python
assert client.post("/api/v1/announcements", json=course_payload, headers=student_headers).status_code == 403
assert client.post("/api/v1/announcements", json=global_payload, headers=teacher_headers).status_code == 403
assert client.post("/api/v1/announcements", json=other_teacher_course_payload, headers=teacher_headers).status_code == 403
assert client.post("/api/v1/announcements", json=course_payload, headers=teacher_headers).status_code == 201
assert client.post("/api/v1/announcements", json=global_payload, headers=admin_headers).status_code == 201
```

Also verify: enrolled students see the owned-course notice; non-enrolled students do not; teachers do not see another teacher's course notice; expired notices are hidden; marking visible notice read twice returns `204`; marking an invisible notice returns `404` to avoid leaking its existence.

- [ ] **Step 2: Define strict request and response schemas**

```python
class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=2000)
    priority: Literal["normal", "important", "urgent"] = "normal"
    scope: Literal["global", "course"]
    course_id: int | None = None
    expires_at: datetime | None = None


class AnnouncementRead(BaseModel):
    id: int
    title: str
    content: str
    priority: str
    scope: str
    course_id: int | None
    course_title: str | None
    author_name: str
    published_at: datetime
    expires_at: datetime | None
    is_read: bool
```

Add a model validator requiring `course_id` exactly when `scope == "course"`.

- [ ] **Step 3: Implement one reusable visibility query**

`visible_announcements_query(user, now)` must filter `archived_at IS NULL`, filter unexpired rows, include global rows, and include course rows according to the approved role matrix. Order by priority (`urgent`, `important`, `normal`) and then newest `published_at`; cap dashboard consumption at 8 items.

- [ ] **Step 4: Implement publish and mark-read endpoints**

Publishing trims title/content, rejects `expires_at <= now`, enforces the exact role/scope matrix, and sets `author_id` from the authenticated user. Mark-read first resolves the announcement through the visibility query, then inserts only when no receipt exists; catch a unique-constraint `IntegrityError`, roll back, and still return `204` so concurrent duplicate read requests remain idempotent.

- [ ] **Step 5: Register the router and run tests**

Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\automated\test_announcements.py -q`

Expected: all announcement tests pass.

### Task 3: Build the role-scoped dashboard aggregate service

**Files:**

- Create: `backend/app/schemas/dashboard.py`
- Create: `backend/app/services/dashboard_service.py`
- Create: `backend/app/api/dashboard.py`
- Modify: `backend/app/api/__init__.py`
- Test: `backend/tests/automated/test_dashboard.py`

- [ ] **Step 1: Seed a minimal mixed-role test graph**

The test fixture must create: two teachers, one student enrolled only in teacher A's published course, one unowned course, one pending and one completed assignment, one upcoming exam, one latest experiment record, one reviewed experiment submission, one AI grade requiring teacher review, one visible course notice, and one invisible notice. Use explicit UTC datetimes relative to one frozen `now` passed into service helpers where ordering is tested.

- [ ] **Step 2: Write failing student endpoint assertions**

Assert exact role isolation, summary counts, ordering, routes, and absence of fabricated data:

```python
response = client.get("/api/v1/dashboard/student", headers=student_headers)
assert response.status_code == 200
body = response.json()
assert body["summary"]["course_count"] == 1
assert body["summary"]["pending_assignment_count"] == 1
assert body["priority_items"][0]["route"] == f"/student/assignments/{pending_assignment.id}"
assert body["continue_learning"]["route"] == f"/student/courses/{course.id}/notebook/{lesson.id}"
assert {item["id"] for item in body["announcements"]} == {visible_notice.id}
```

- [ ] **Step 3: Write failing teacher endpoint assertions**

```python
response = client.get("/api/v1/dashboard/teacher", headers=teacher_headers)
assert response.status_code == 200
body = response.json()
assert body["summary"]["course_count"] == 1
assert body["summary"]["student_count"] == 1
assert body["summary"]["pending_review_count"] >= 1
assert body["managed_courses"] == [{"id": course.id, "title": course.title}]
assert all(item["course_id"] == course.id for item in body["course_health"])
```

Also assert student tokens receive `403` from `/dashboard/teacher`, teacher tokens receive `403` from `/dashboard/student`, and unsupported roles receive `403`.

- [ ] **Step 4: Define response schemas before service code**

Create focused models for summary, action/work item, continuation, course snapshot/health, feedback/activity, and the two top-level responses. Every list uses `Field(default_factory=list)`; every URL is a server-created relative route; datetime values remain timezone-aware.

- [ ] **Step 5: Implement student aggregation without N+1 loops**

Use joins/subqueries to scope all data through `CourseEnrollment(status="enrolled")` and `Course(status="published")`. An assignment is pending when at least one of its questions lacks any submission by the current student. An exam is upcoming when published, enrolled, not already submitted/graded, and its effective time (`start_at` then `end_at`) is in the future. Urgency is `urgent` within 24 hours, `soon` within 72 hours, otherwise `normal`.

For continuation, prefer the most recently updated accessible `ExperimentRecord`; build lesson routes as `/student/courses/{course_id}/notebook/{lesson_id}` and module routes as `/student/experiments/{module_id}`. Fall back to the first enrolled course route. Return no continuation object if the student has neither records nor courses.

- [ ] **Step 6: Implement teacher aggregation without global leakage**

Every teacher query starts from `Course.teacher_id == current_user.id`. Count distinct enrolled students. Count pending reviews from owned-course experiment submissions where `reviewed_at IS NULL` and `CodeGrade.needs_teacher_review IS TRUE` reached through owned assignments/exams. Deadline-risk items include published assignments due in the next 72 hours and report `submitted_student_count / enrolled_student_count`; do not divide by zero.

Work items are sorted by urgency/time and capped at 8. Course health is sorted by imminent deadlines, then pending reviews, then title. Recent activity is capped at 8 and is drawn only from real submissions in owned courses.

- [ ] **Step 7: Keep API endpoints thin and role-locked**

```python
@router.get("/student", response_model=StudentDashboardRead)
def student_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    return build_student_dashboard(db, current_user)


@router.get("/teacher", response_model=TeacherDashboardRead)
def teacher_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher")),
):
    return build_teacher_dashboard(db, current_user)
```

- [ ] **Step 8: Run the focused backend suite**

Run:

```bat
backend\.venv\Scripts\python.exe -m pytest backend\tests\automated\test_announcements.py backend\tests\automated\test_dashboard.py -q
```

Expected: all focused backend tests pass.

### Task 4: Centralize role-home routing and add real Home navigation

**Files:**

- Create: `frontend/src/router/roleHome.js`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/views/LoginView.vue`
- Modify: `frontend/src/components/layout/AppSidebar.vue`
- Modify: `frontend/src/components/layout/__tests__/AppSidebar.spec.js`
- Create: `frontend/src/router/__tests__/role-home.spec.js`

- [ ] **Step 1: Write failing mapping and sidebar tests**

```js
expect(homeForRole('student')).toBe('/student')
expect(homeForRole('teacher')).toBe('/teacher')
expect(homeForRole('admin')).toBe('/admin/users')
expect(homeForRole('developer')).toBe('/developer/templates')
expect(homeForRole('unknown')).toBe('/login')
```

Mount the sidebar once as student and once as teacher. Assert the first visible navigation item is `首页`, its path is the exact role root, it is active only on the exact root, and clicking the logo pushes the same root. Keep the existing developer-only navigation test passing.

- [ ] **Step 2: Implement one shared mapping**

```js
export const ROLE_HOME = Object.freeze({
  student: '/student',
  teacher: '/teacher',
  admin: '/admin/users',
  developer: '/developer/templates',
})

export function homeForRole(role) {
  return ROLE_HOME[role] || '/login'
}
```

- [ ] **Step 3: Replace duplicate maps in router and login**

Use `homeForRole(auth.role)` for guest redirects and role mismatch fallbacks. Login uses `homeForRole(user.role)` after success. Preserve the existing `/student` and `/teacher` route definitions.

- [ ] **Step 4: Add Home items and exact root matching**

Student and teacher menu arrays start with their root Home item. For `/student` and `/teacher`, `isActive` uses equality; child pages continue using `startsWith`. Logo navigation uses `homeForRole(auth.role)` rather than the first menu item.

- [ ] **Step 5: Run focused frontend tests**

Run:

```bat
cd frontend
npm.cmd test -- src/router/__tests__/role-home.spec.js src/components/layout/__tests__/AppSidebar.spec.js
```

Expected: all mapping/sidebar tests pass.

### Task 5: Build shared dashboard networking and announcement UI

**Files:**

- Create: `frontend/src/api/dashboard.js`
- Create: `frontend/src/api/announcements.js`
- Create: `frontend/src/components/dashboard/DashboardAsyncState.vue`
- Create: `frontend/src/components/dashboard/AnnouncementPanel.vue`
- Create: `frontend/src/components/dashboard/AnnouncementComposer.vue`
- Create: `frontend/src/components/dashboard/__tests__/AnnouncementPanel.spec.js`

- [ ] **Step 1: Write failing announcement-panel tests**

Test four visible states: loading, retryable error, empty, populated. In the populated state, unread items have an unread marker, course/global source text is visible, content is rendered as text, and clicking an unread notice emits `mark-read` exactly once. When `canPublish` is true, the publish control opens the composer; when false it is absent.

- [ ] **Step 2: Implement the two API wrappers**

```js
import client from './client.js'

export const dashboardAPI = {
  student() { return client.get('/dashboard/student') },
  teacher() { return client.get('/dashboard/teacher') },
}
```

```js
import client from './client.js'

export const announcementsAPI = {
  create(payload) { return client.post('/announcements', payload) },
  markRead(id) { return client.post(`/announcements/${id}/read`) },
}
```

- [ ] **Step 3: Implement truthful shared async states**

`DashboardAsyncState.vue` accepts `loading`, `error`, `empty`, `emptyTitle`, and `emptyBody`; it emits `retry`. Loading skeletons use `aria-busy="true"`; errors use `role="alert"`; retry is a real button; empty state has no celebratory claim when data simply does not exist.

- [ ] **Step 4: Implement the announcement panel**

Use a compact list with title, two-line plain-text excerpt, source, author, date, priority, and unread state. Do not use emoji. Use `Intl.DateTimeFormat('zh-CN', ...)` for dates. The component never mutates props; the parent replaces `is_read` after the API succeeds.

- [ ] **Step 5: Implement the teacher composer**

The modal contains course select, title, plain-text content, priority, and optional expiry datetime. It validates course/title/content locally, disables submission while pending, keeps the dialog open on server error, emits `published` with the returned notice, resets after success, closes on Escape, restores focus, has labelled controls, and traps accidental background clicks by requiring an explicit close button or backdrop click.

- [ ] **Step 6: Run the component test**

Run: `cd frontend && npm.cmd test -- src/components/dashboard/__tests__/AnnouncementPanel.spec.js`

Expected: all states and events pass.

### Task 6: Replace the student mock dashboard with live task-first UI

**Files:**

- Modify: `frontend/src/views/student/DashboardView.vue`
- Create: `frontend/src/views/student/__tests__/DashboardView.spec.js`

- [ ] **Step 1: Write failing view tests with mocked APIs**

Mock `dashboardAPI.student` and `announcementsAPI.markRead`. Assert one request on mount, summary labels, priority order, continuation route, course routes, feedback section, announcement rendering, mark-read local update, retry behavior after a rejected request, and genuine empty states. Assert the old hard-coded titles and numbers are absent.

- [ ] **Step 2: Implement state and request lifecycle**

Use `ref` state for `loading`, `error`, and `dashboard`. `loadDashboard()` clears error, awaits one aggregate request, and never substitutes sample values. `markRead(id)` calls the API and replaces the matching notice with `{...notice, is_read: true}` only after success. Navigation uses only server-provided relative routes after verifying they start with `/student/` or equal `/student`.

- [ ] **Step 3: Implement the approved information hierarchy**

Order the DOM as: compact greeting/action, summary strip, primary two-column row (`今日重点`, `通知公告`), then `课程动态` and `最新反馈`. Use semantic headings and lists. Urgent times are text plus semantic color, never color alone. Feedback without text displays `暂无文字反馈` while preserving score/date.

- [ ] **Step 4: Implement responsive scoped styles from existing tokens**

Use `var(--paper)`, `var(--surface)`, `var(--border)`, `var(--ink)`, existing semantic colors, and the established radius/spacing scale. Avoid a giant gradient hero, nested cards, decorative metrics, and duplicated shortcut grids. Add visible `:focus-visible` states and `prefers-reduced-motion` handling.

- [ ] **Step 5: Run the student view test**

Run: `cd frontend && npm.cmd test -- src/views/student/__tests__/DashboardView.spec.js`

Expected: all student homepage tests pass.

### Task 7: Replace the teacher mixed mock dashboard with live workbench UI

**Files:**

- Modify: `frontend/src/views/teacher/DashboardView.vue`
- Create: `frontend/src/views/teacher/__tests__/DashboardView.spec.js`

- [ ] **Step 1: Write failing view tests with mocked APIs**

Assert one aggregate dashboard request, summary values, work queue ordering, managed-course health, recent activity, empty/error/retry states, and absence of old hard-coded timeline entries. For publishing, select a managed course, submit a notice, assert the exact `announcementsAPI.create` payload (`scope: 'course'`), then assert the view refreshes and the new notice is visible.

- [ ] **Step 2: Implement state and request lifecycle**

Use the same state names and load/retry behavior as the student view. Publishing calls the announcement API, closes/reset the composer only on success, and reloads the aggregate endpoint so unread counts and ordering come from the server.

- [ ] **Step 3: Implement the approved information hierarchy**

Order the DOM as: compact greeting/primary action, summary strip, primary two-column row (`待处理工作`, `通知公告`), then `课程概览` and `最近动态`. The primary action routes to the first work item when present, otherwise `/teacher/courses`. Course health rows show denominator-aware counts such as `18/24 已提交`; use `—` when a denominator is unavailable rather than inventing a percentage.

- [ ] **Step 4: Reuse visual rules from the student view without copy-pasting a second design system**

Keep shared primitives in the new dashboard components; keep only role-specific layout rules inside the views. No emoji, no fake English subtitles, no non-functional shortcut tiles.

- [ ] **Step 5: Run the teacher view test**

Run: `cd frontend && npm.cmd test -- src/views/teacher/__tests__/DashboardView.spec.js`

Expected: all teacher homepage tests pass.

### Task 8: Full regression, migration, build, and visual acceptance

**Files:**

- Verify all files above; do not modify unrelated dirty files.

- [ ] **Step 1: Run focused backend and frontend suites**

```bat
backend\.venv\Scripts\python.exe -m pytest backend\tests\automated\test_announcements.py backend\tests\automated\test_dashboard.py backend\tests\automated\test_permissions.py -q
cd frontend
npm.cmd test -- src/router/__tests__/role-home.spec.js src/components/layout/__tests__/AppSidebar.spec.js src/components/dashboard/__tests__/AnnouncementPanel.spec.js src/views/student/__tests__/DashboardView.spec.js src/views/teacher/__tests__/DashboardView.spec.js
npm.cmd run build
```

Expected: all tests pass and Vite completes without warnings introduced by this feature.

- [ ] **Step 2: Run the broader relevant regression suites**

```bat
backend\.venv\Scripts\python.exe -m pytest backend\tests\automated\test_auth_and_users.py backend\tests\automated\test_courses_assignments_judge.py backend\tests\automated\test_exams_experiments_jupyter.py backend\tests\automated\test_experiment_reviews.py -q
cd frontend
npm.cmd test
```

Expected: all tests pass. If an existing unrelated dirty-worktree test fails, capture the exact failing test and prove it is unrelated before continuing; do not modify unrelated files to hide it.

- [ ] **Step 3: Validate migration round-trip on a disposable database**

Use the repository's configured test database or a disposable SQLite URL. Upgrade to head, inspect that both tables exist, downgrade one revision, and upgrade again. Never run downgrade against the user's non-disposable development database.

- [ ] **Step 4: Inspect the final diff for scope and whitespace errors**

Run:

```bat
git diff --check
git status --short
git diff -- backend/app/models/__init__.py backend/app/api/__init__.py backend/app/api/announcements.py backend/app/api/dashboard.py backend/app/services/dashboard_service.py backend/app/schemas/announcements.py backend/app/schemas/dashboard.py frontend/src/router frontend/src/views/LoginView.vue frontend/src/components/layout/AppSidebar.vue frontend/src/components/dashboard frontend/src/views/student/DashboardView.vue frontend/src/views/teacher/DashboardView.vue
```

Expected: no whitespace errors; only the planned paths plus pre-existing unrelated user changes appear.

- [ ] **Step 5: Browser acceptance with real role sessions**

Verify at desktop `1440x900`, compact laptop `1024x768`, and mobile `390x844`:

1. Student login lands on `/student`; teacher login lands on `/teacher`.
2. Home sidebar item and logo return to the correct role root without making Home active on child routes.
3. Student task order, continuation link, course link, feedback link, mark-read state, empty state, error retry, and announcement visibility work.
4. Teacher work queue links, course rows, announcement modal validation, successful publish, and refreshed announcement list work.
5. A student cannot see another course's notice; a teacher cannot publish to another teacher's course.
6. Keyboard focus is visible; modal labels/Escape/focus restoration work; text does not clip; no horizontal scroll exists.
7. No Welcome page changes are visible and no mock metrics or hard-coded demo activities remain.

- [ ] **Step 6: Save acceptance evidence for reviewer handoff**

Capture one student desktop screenshot, one teacher desktop screenshot, and one representative mobile screenshot in a disposable temp directory outside tracked source. Report the exact test commands, pass counts, build result, visual issues fixed, and any remaining limitation. Remove temporary screenshots after review unless the reviewer asks to keep them.

## Plan self-review

- Spec coverage: student and teacher post-login routing, Home navigation, shared announcements, teacher course publishing, student read state, real task/feedback/activity data, responsive UI, loading/error/empty states, permissions, tests, and visual acceptance are each mapped to tasks above.
- Placeholder scan: every implementation and error-handling step is concrete and executable.
- Type consistency: `priority`, `scope`, route fields, summary field names, announcement fields, and API paths are identical across backend contracts, frontend wrappers, and tests.
- Scope boundary: Welcome page, admin UI, rich text, attachment/comment/edit/delete workflows, and unrelated AI implementation files are explicitly excluded.
