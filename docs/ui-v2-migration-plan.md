# DAI UI V2 工程落地计划（墨松绿 × 岩灰）

> 本文件是 `docs/dai-design-system-v2.md`（DESIGN_DOC）的执行层映射：
> 记录「现有业务实现 → 页面 → API → 状态 → V2 UI」以及实时迁移状态。
> 视觉冲突时以 DESIGN_DOC + `new-frontend/` 原始 7 个文件为准。

## 1. 基线

- Branch：`master`
- HEAD：`a42e9816875b21112760e5c129583110778241b2`
- 修改前基线：`lint ✅` / `vitest 88 files, 825 tests ✅` / `vite build ✅`
- DESIGN_DOC：`docs/dai-design-system-v2.md`
- V2 参考文件：`new-frontend/` 下 6 个 HTML + 1 个 CSS，均已复核存在。

## 2. 全局策略（不逐页复制 CSS）

1. `frontend/src/styles/dai-ds-v2.css`：从 `new-frontend/dai-ds-v2.css` 复制，仅删除 `.select select:disabled` 后多余的孤立 `}`。
2. `frontend/src/style.css`：改为 `@import dai-ds-v2.css` + 旧 token 别名 + 未迁移页面桥接样式。桥接样式只用 V2 token，不保留旧设计数值。
3. `frontend/src/styles/teacher-management.css`：改为 V2 桥接（旧教师列表页在未迁移前自动获得 V2 颜色 / 密度）。
4. App Shell 与基础组件统一迁移后，逐页替换为 V2 类名；旧 scoped 样式按迁移完成顺序清理。
5. 新增 UI 禁止 hex / rgb / hsl；颜色一律 V2 token 或 `oklch()` / `color-mix(in oklch, …)`。

## 3. 页面—业务—API—V2 矩阵

状态：✅ 已迁移 / 🔶 桥接可用（旧页面结构 + V2 token） / ⬜ 待迁移

### 3.1 公共骨架与基础组件

| 模块 | 业务 | V2 落点 | 状态 |
| --- | --- | --- | --- |
| `AppLayout` | 应用外壳、侧栏折叠、移动导航 | `.shell/.sidebar/.main/.content` | ✅ |
| `AppSidebar` | 角色菜单、权限、折叠、用户信息 | `.nav-group/.nav-item/.nav-badge/.user-card` | ✅ |
| `AppHeader` | 用户菜单、登出、全局搜索入口 | `.header/.crumb/.header-search`；搜索跳转真实列表 `?q=` | ✅ |
| `App.vue` toast | 全局消息 | token-only 扩展组件，左 3px 语义栏 | ✅ |
| `UiPanel` | 面板容器 | `.panel` | ✅ |
| `UiStatusPill` | 状态徽标 | `.badge` + dot；purple → info | ✅ |
| `UiProgress` | 进度条 | `.score-bar` | ✅ |
| `ConfirmDialog` | 通用确认 | `.modal/.modal-head/.modal-body/.modal-foot` | ✅ |
| `TeacherPageHeader` | 教师页头 | `.page-head` | ✅ |
| `TeacherMetricGrid` | KPI | `.metric-strip` | ✅ |
| `TeacherPagination` / `StudentPagination` | 分页 | `.pagination/.pg-btn` 语义 | ✅ |
| AI 组件 | 评分展示 / 复核 / 代码 | `.evidence-*/.score-orb/.code-panel` | ✅ |

### 3.2 第一批页面

| 页面 | Route | 主要 API | V2 模式 | 状态 |
| --- | --- | --- | --- | --- |
| 学生首页 | `/student` | `GET /dashboard/student`、`POST /announcements/{id}/read`、`GET /courses/{id}/progress` | Page Head + Continue Panel + Metric Strip + 双列 Panel | ✅ |
| 教师首页 | `/teacher` | `GET /dashboard/teacher`、公告 read/create | Page Head + Metric Strip + grid-2-1 工作队列 / 公告 | ✅ |
| 课程管理 | `/teacher/courses`、`/admin/courses` | `GET /courses`、`PATCH /courses/{id}`、`GET /academic-terms`、创建课程 | Page Head + Metric Strip + Toolbar + Dense Table + Modal | ✅ |
| 学生任务中心（提交列表） | `/student/assignments` | `GET /assignments`、`GET /exams`、`GET /experiments/records`、`GET /courses` | Tabs + Toolbar + Dense Table | ✅ |
| 教师提交与评分 | `/teacher/submissions`、`/admin/submissions` | `GET /experiments/submissions`（q/course/entry/review_status/sort/page） | Page Head + Metric Strip + Toolbar + Dense Table | ✅ |
| AI 评分列表 | `/teacher/ai-grading`、`/admin/ai-grading` | `GET /ai-grading/grades` | Page Head + Metric Strip + Toolbar + Dense Table | ✅ |
| AI 评分详情 | `/teacher/ai-grading/:id` | `GET /ai-grading/grades/{id}`、`POST .../override` | 证据图例 + 3 列总览 + 双栏 workbench + 高级信息 | ✅ |

### 3.3 学生端剩余页面

| 页面 | Route | API | 状态 |
| --- | --- | --- | --- |
| 课程列表 | `/student/courses` | `GET /courses`、`GET /courses/{id}/chapters`、`GET /courses/{id}/progress`、enroll/unenroll | Page Head + Underline Tabs + Searchbox + Panel rows | ✅ |
| 课程详情 | `/student/courses/:id` | `GET /courses/{id}`、assignments/exams/progress | 🔶 |
| 课时学习 | `/student/courses/:id/lessons/:lid` | courses/lesson-progress/video playback | 🔶 |
| 作业详情 | `/student/assignments/:id` | `GET /assignments/{id}`、`POST /judge/submissions`、`GET /judge/submissions/{id}/result`、sample-run | 🔶 |
| 提交结果 | `/student/submissions/:id` | `GET /judge/submissions/{id}/result` | Page Head + Submission Panel + Terminal + AI Result | ✅ |
| 考试列表 | `/student/exams` | `GET /exams` | V2 卡片语义 + Page Head + Empty | ✅ |
| 实验列表 | `/student/experiments` | experiments modules/records | Metric Strip + Catalog | ✅ |
| 学习反馈 | `/student/feedback` | `GET /dashboard/student`（feedback 聚合） | Tabs + Toolbar + Dense Feedback rows | ✅ |
| Notebook | `/student/courses/:id/notebook/:lid` | experiments records/cells execute | 🔶 |

### 3.4 教师端剩余页面

| 页面 | Route | API | 状态 |
| --- | --- | --- | --- |
| 作业管理 | `/teacher/assignments` | `GET/POST /assignments`、publish/unpublish/delete | V2 组件 + table-wrap/toolbar 桥接 | ✅ |
| 题目编辑 | `/teacher/assignments/:id/edit` | assignments/questions、judge sample-run、ai-grading config/rubrics | 🔶 |
| 考试管理 | `/teacher/exams` | `GET/POST/PATCH/DELETE /exams` | V2 组件 + table-wrap/toolbar 桥接 | ✅ |
| 实验管理 | `/teacher/experiments` | experiments modules publish/unpublish | V2 组件 + table-wrap/toolbar 桥接 | ✅ |
| 提交详情 | `/teacher/submissions/:id` | `GET /experiments/submissions/{id}`、`PATCH .../review` | token/代码快照迁移 | ✅ |
| 章节课时管理 | `/teacher/courses/:id/manage` | courses chapters/lessons/whitelist/cover/studio | 🔶 |
| 课时编辑 / Studio | `/teacher/courses/:id/lessons/:id/edit`、`.../studio/:lid` | courses lessons、studio | 🔶 |

### 3.5 管理端 / 公共页

| 页面 | Route | API | 状态 |
| --- | --- | --- | --- |
| Admin 概览 / 用户 / 教务 / 环境 | `/admin*` | users/academics/environments | 🔶 |
| 登录 / 欢迎 | `/login`、`/welcome` | `POST /auth/login` | 🔶（无 App Shell，视觉待迁移） |

## 4. 迁移顺序

1. ✅ 基础设施 + App Shell
2. ✅ 第一批代表页
3. 🔜 第二批：学生课程 / 任务 / 提交 / 反馈 / 实验
4. 🔜 第三批：教师作业 / 考试 / 章节课时 / 提交详情
5. 🔜 第四批：Admin / 登录欢迎
6. 最后：删除 `teacher-management.css` 桥接、旧 token 别名、无引用 scoped 样式；复跑全量验证。

## 5. 验证基线（当前）

- `npm run lint`：✅
- `npm test`：✅（88 files / 825 tests）
- `npm run build`：✅
- 颜色纪律：`frontend/src` 中除 `dai-ds-v2.css` 外，hex / rgb() / rgba() / hsl() 数量为 0。
- 1440 / 1280 / 1920 桌面 Smoke：欢迎、登录、学生首页、教师首页、课程管理、提交列表、AI 评分列表/详情无横向溢出、无 console error / pageerror。
- Git 工作区：100 个 frontend 文件 + 3 个 docs / V2 CSS 文件；不触碰 backend。
