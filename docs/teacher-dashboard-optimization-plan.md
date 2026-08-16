# 教师端工作台功能优化与重构 Plan

> 基线：`a42e981`；参考稿：`new-frontend/teacher-home.html`（教师工作台截图）。
> 目标：参考稿中可见的教师端能力全部由真实数据驱动，不堆静态 UI。

## 1. 参考界面功能拆解

| 区域 | 功能 |
| --- | --- |
| 顶部栏 | 面包屑、侧栏折叠、全局搜索（课程 / 作业 / 学生 / 提交，`⌘K`）、通知、账户菜单 |
| 问候区 | 日期、姓名、动态待办文案；“查看公告”与“处理待评分 N”双主操作 |
| 指标条 | 进行中课程、在册学生、待复核提交、近 7 天截止 |
| 待处理工作 | 按任务聚合（实验待评分 / AI 待复核 / 作业待评分 / 考试待发布），带紧急度与状态徽标 |
| 课程公告 | 公告日期、课程标签、发布入口 |
| 最近提交 | 表格：学生+学号、实验/作业、状态、测试通过数、AI 得分、提交时间 |
| 侧边栏 | 工作台、课程管理、作业管理、实验管理、考试管理、班级与学员、提交与评分（徽标）、AI 评分复核、成绩统计、运行环境、设置 |
| 用户卡 | 教师姓名、教师·院系 |

## 2. 现状差距

- 全局搜索只跳转实验提交列表 `?q=`，没有统一搜索 API 与 `⌘K` 下拉。
- 教师 Dashboard 工作队列是逐条提交，缺少作业待评分、考试待发布成绩两类。
- “最近动态”只查实验提交，不是参考稿的混合提交表格。
- 侧栏缺少班级与学员、成绩统计、运行环境、设置，且菜单命名不一致。
- “提交与评分”仅覆盖实验提交，作业代码提交没有教师详情页。
- 教师无院系字段；课程无编号；实验无截止时间；通知无持久化。
- 判题测试通过数散落在 `result_details`/stdout 中，没有归一化字段。

## 3. 前端改造

1. `DashboardView.vue`：双主操作、真实指标、聚合工作队列、最近提交表格。
2. `AppSidebar.vue`：菜单对齐参考稿，新增徽标与 4 个入口。
3. `AppHeader.vue`：`⌘K` 搜索下拉、通知铃铛、用户院系。
4. 新增页面：
   - `/teacher/submissions/unified` 统一提交中心
   - `/teacher/judge-submissions/:id` 作业提交详情
   - `/teacher/classes` 班级与学员
   - `/teacher/grades` 成绩统计
   - `/teacher/environments` 运行环境
   - `/teacher/settings` 设置
   - `/teacher/notifications` 通知中心

## 4. 后端与数据库

### 4.1 Dashboard V3

扩展 `GET /api/v1/dashboard/teacher`：

- `summary`：`active_course_count`、`course_count`、`student_count`、`pending_grading_count`、`pending_review_count`、`upcoming_deadline_count`、`pending_release_count`。
- `work_items`：保留 `experiment_review / ai_review / deadline` kind 兼容，新增 `assignment_grading / exam_release`，按任务聚合并带 `count`、`status`。
- `recent_submissions`：混合实验/作业/考试提交摘要；旧 `recent_activity` 保留一个版本。
- 新增轻量 `GET /api/v1/dashboard/teacher/counts` 供侧栏徽标轮询。

### 4.2 统一提交与搜索

- `GET /api/v1/submissions/unified`：实验/作业/考试 `UNION ALL`，支持 `q/course_id/kind/status/sort/page`。
- `GET /api/v1/search?q=&limit=`：按角色隔离返回课程/作业/学生/提交分组。
- `GET /api/v1/judge/submissions` 增加教师筛选与测试摘要；新增教师作业提交详情上下文。

### 4.3 教师侧新能力

- `GET /api/v1/teaching-classes` 教师只看自己课程关联班级；对应学员名单对教师开放但只读。
- `GET /api/v1/teacher/grade-statistics` 跨课程/考试成绩总览。
- `GET /api/v1/environments/available` 复用为教师只读环境页数据源。
- `GET/PATCH /api/v1/users/me/preferences` 偏好设置。

### 4.4 数据库迁移

- `users.department`、`courses.code`、`lessons.due_at`、`experiment_modules.due_at`
- `submissions.tests_passed/tests_total`、`exam_answers.tests_passed/tests_total`
- 相关索引：待评分、待复核、截止、学生搜索
- 二期：`user_preferences`、`notifications`、`notification_reads`

## 5. 实施顺序

1. P0：基线测试与文档。
2. P1：模型字段 + Dashboard V3 + 工作台前端。
3. P2：统一提交中心 + 作业提交详情。
4. P3：全局搜索 + 侧栏/顶部导航。
5. P4：班级与学员、成绩统计、环境、设置、通知。

## 6. 验收

- 后端 `pytest` 全绿；新增 dashboard/search/unified/academics 权限测试。
- 前端 `npm run lint`、`npm test`、`npm run build` 全绿。
- Dashboard 四个模块均由 `/dashboard/teacher` 真实数据渲染。
- 工作队列、最近提交可点击并落到正确过滤页面。
- 全局搜索与教师名单接口无越权。

## 7. 当前实施进度

- [x] 模型字段与 Alembic 迁移 `13697fb5ecbf`：院系、课程编号、实验截止、测试通过数、索引。
- [x] Dashboard V3：聚合工作队列、考试待发布、最近提交混合表格、counts 徽标接口。
- [x] 统一提交中心 `/api/v1/submissions/unified` 与 `/teacher/submissions/unified`。
- [x] 作业提交详情 `/api/v1/judge/submissions/{id}/teacher` 与 `/teacher/judge-submissions/:id`。
- [x] 全局搜索 `/api/v1/search` 与 `⌘K` 下拉。
- [x] 教师侧栏：工作台/课程管理/作业管理/实验管理/考试管理/班级与学员/提交与评分（徽标）/AI 评分复核/成绩统计/运行环境/设置。
- [x] 教师班级与学员、成绩统计、只读运行环境、设置、通知中心页面。
- [x] 通知落表（迁移 `20260816_0001`：`notifications` / `notification_reads`）、通知 API 与通知中心真实化。
- [x] 用户偏好后端持久化（`user_preferences`、`/users/me/preferences`，AppLayout 启动时同步）。
- [x] 课程名单 CSV 导入（`POST /courses/{id}/students/import`）。
- [x] 历史 `tests_passed/tests_total` 回填脚本 `scripts/backfill_test_counts.py`。
- [x] 创建课程表单增加课程编号。
