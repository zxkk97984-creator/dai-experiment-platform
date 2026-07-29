# 001 第二轮验收结论：不通过，必须继续修复

你刚提交的 `5373e90` 让前端测试和构建通过了，但后端全量测试仍为
`5 failed, 306 passed, 3 skipped`。不要把这些失败当成“只有 MagicMock 不匹配”：
我已确认里面有真实行为回归。请在当前 `AIpanti` 分支继续修复、补测试并提交。

不要改动或清理用户原有的 `.pt-*` 删除项和未跟踪的
`DAI智能代码评分方案_V1.md`。不要泄露或提交 API key。不要削弱已有测试来换绿。

## 一、先修复当前 5 个后端失败

- `test_judge_docker_failure_sets_system_error`
- `test_formal_docker_fail_system_error`
- `test_p0_maybe_finalize_checks_running_not_just_pending`
- `test_p0_5_maybe_finalize_blocks_on_running`
- `test_process_submission_unknown_exception_triggers_fail_job`

根因不只是 mock：`JudgeQuestion.grading_mode` 默认 `shadow`，但现有创建接口和页面并未创建
有效的 F/R 测试组，使原有 legacy 判题路径被绕开。请建立明确兼容策略：

- 数据库/ORM 的安全默认应保护旧数据和直接 ORM 创建的题目；
- 新建编程题由应用层明确设为 `shadow`，且必须同时具备有效的结构化配置；
- 选择题保持 `legacy`；
- `shadow/active` 缺测试组、Docker 失败、锁定 rubric 缺失等属于系统错误，不能给学生错误扣分或把任务伪装成 completed；
- 尽量复用原有 `_write_submission_files` 等 helper，不要复制一套导致原回归测试失效。

## 二、修复判题与 AI 队列状态机

- assignment 的 `shadow` 必须保留旧 hidden-tests 全通过/不通过得到的官方 legacy 成绩，同时后台计算 F/A/R/Q；当前代码把 shadow 的 `submission.score` 设成 `None`。
- exam 的 `shadow` 也必须以旧规则“全部通过才得该题满分”，不能“任一 F 组通过就满分”。
- deterministic 判题未全通过时不能一律标成 `accepted`；partial score 与判题状态要一致。
- structured 判题的系统错误要走可重试失败路径，不能调用 `complete_job` 后静默完成。
- `AIServiceError` 用 `str(exc)`，不能访问不存在的 `exc.message`。
- `review_required` 不能随后被 `complete_ai_grade` 覆盖为 `completed`。
- active exam 要在 CodeGrade 真正变成 `completed` 后再次尝试 finalize；当前调用顺序会永远卡在 grading。
- exam finalize 必须阻止任何非 `completed` 的 active CodeGrade，包括
  `pending/queued/running/review_required/system_error`，不能把 `ExamAnswer.score is None`
  当零分后提前发布。
- producer、consumer、重试和 stale recovery 必须统一使用配置的 AI queue 名称。
- retry/stale recovery 推回队列前状态必须变为 `queued`；当前设成 `pending` 后直接 `rpush`
  会被 `claim_ai_grade` 忽略。
- 保证重复消息、并发 retry/regrade 不会产生重复 CodeGrade 或重复计分。

## 三、补齐 API 权限、事务和重判范围

所有 teacher 操作都必须校验题目/提交/考试属于自己教授的课程；admin 才可跨课程。
特别修复：

- `GET question config`、`list rubrics`、exam grade detail、retry、override 的越权读取/写入；
- `list_grades.total` 必须应用和 items 相同的 course ownership/filter；
- assignment/exam 的 `question_id`、`student_id` 筛选都要正确；
- `patch_rubric`、`lock_rubric` 必须 commit；
- `generate_rubric` 不能假定 ExamQuestion 有 `title`；
- `retry` 不能重置 running/completed 造成竞态，返回状态必须与实际入队状态一致；
- override A/Q 后重算 raw/final；active assignment/exam 同步官方分数，exam 必要时 finalize，并保留 override audit；
- regrade 只能入队目标题目的 grades；禁止当前“查询并入队全库所有 pending grades”的严重范围错误；
- regrade 新记录必须继承题目 mode 和已有 deterministic F/R/details，不能硬编码 shadow 或从零计分。

请为上述越权、事务、筛选、全库误入队分别写回归测试。

## 四、补齐用户可用的端到端页面

当前只有 review 路由，仍不能完成实际工作流：

- `QuestionEditView.vue` 和 `ExamQuestionEditView.vue` 增加编程题 AI 配置：
  `grading_mode`、constraints、reference solution、F/R groups、caps、rubric 生成/编辑/锁定。
  创建时必须与后端 schema 一致，不能再产生“默认 shadow 但无测试组”的坏题。
- teacher/admin 侧边栏加入 AI 复核入口；review 页面使用 `AppLayout`。
- admin 列表详情链接不能硬编码 `/teacher/...`。
- 复核详情展示学生代码、F/A/R/Q、证据、系统/人工审计信息。
- 增加学生安全响应：active 仅返回可公开的 F/A/R/Q 分解和教师反馈；
  shadow 不向学生暴露 AI 分数、reasoning、raw response、reference solution、hidden tests。
- `SubmissionView.vue` 和考试结果页展示 active 的评分分解；处理 `graded` 等终态，
  避免无限轮询。最好统一现有状态语义，不随意新增前端未知状态。

请写真正挂载组件并模拟 API 的前端测试；仅测试常量不算覆盖配置工作流。

## 五、最终验证（全部通过后才可声称完成）

从仓库实际虚拟环境运行并保留摘要：

1. `cd backend && .venv\Scripts\python.exe -m pytest -q`
2. `cd backend && .venv\Scripts\python.exe -m alembic heads`（必须单 head）
3. 用临时 SQLite 数据库执行 `alembic upgrade head`，确认全量迁移可落地
4. `cd frontend && npm.cmd test`
5. `cd frontend && npm.cmd run build`
6. 检查 Git diff，确认无真实 key、无越权接口、无用户旧文件被改动

请完成所有修复并提交一个或多个清晰 commit。做完后停下来，向 001 汇报：
commit、各验证命令的精确通过数、关键兼容/状态机决策。不要只说“已完成”。
