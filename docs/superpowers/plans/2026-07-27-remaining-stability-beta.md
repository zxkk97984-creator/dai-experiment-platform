# DAI Platform Remaining Stability & Beta Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修完当前仓库剩余的判题可靠性、考试校验、实验提交闭环、安全部署和测试问题，使项目达到可持续验收的稳定 Beta。

**Architecture:** 数据库是判题状态的唯一事实源，Redis 只负责唤醒 Worker；所有队列消费按“至少一次”设计，Worker 和最终评分必须幂等。实验提交采用客户端幂等键和不可变快照，教师通过独立页面查看与评分。生产环境使用统一 Compose、健康检查、环境变量校验和 HttpOnly Refresh Cookie。

**Tech Stack:** FastAPI、SQLAlchemy 2、Alembic、MySQL 8、Redis、Docker、Vue 3、Pinia、Vitest、pytest、GitHub Actions。

---

## 执行规则

- 不新增 AI、推荐、聊天等无关功能。
- 每个任务先写失败测试，再实现，再运行该任务测试。
- 每个任务单独提交；禁止把所有修改压进一个提交。
- 不删除或改写用户现有数据；所有模型变化必须带 Alembic migration。
- 不用 `sleep` 伪造并发测试；使用事件、屏障、条件更新或两个独立 Session。
- 完成全部任务后才运行完整测试、Docker smoke 和端到端测试。

## 文件结构

- `backend/app/services/judge_queue.py`：统一普通作业与考试判题的入队、领取、确认、重试。
- `backend/app/services/exam_grading.py`：考试答案状态和最终成绩幂等汇总。
- `backend/app/services/time_utils.py`：UTC 时间规范化。
- `backend/app/api/experiments.py`：实验提交、查询与教师评分接口。
- `frontend/src/views/student/ExperimentDetailView.vue`：学生运行、保存、提交、提交历史。
- `frontend/src/views/teacher/ExperimentSubmissionsView.vue`：教师提交列表。
- `frontend/src/views/teacher/ExperimentSubmissionDetailView.vue`：快照查看、评分与反馈。
- `docker-compose.prod.yml`、`backend/Dockerfile`、`frontend/Dockerfile`：生产部署。
- `backend/tests/automated/`、`frontend/src/**/__tests__/`：回归测试。

---

### Task 1：建立可靠且幂等的判题任务状态机

**Files:**
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/<revision>_judge_job_reliability.py`
- Create: `backend/app/services/judge_queue.py`
- Modify: `backend/app/api/judge.py`
- Modify: `backend/app/services/exam_service.py`
- Test: `backend/tests/automated/test_judge_queue_reliability.py`

- [ ] 为普通 `Submission` 和 `ExamAnswer` 增加或统一以下字段：`grading_status`、`attempt_count`、`queued_at`、`started_at`、`finished_at`、`last_error`。合法状态固定为 `pending/queued/running/completed/system_error`。
- [ ] 编写 Alembic migration，为历史数据补默认值和索引；至少建立 `(grading_status, updated_at)` 索引。
- [ ] 在 `judge_queue.py` 提供唯一入队入口：

```python
def enqueue_job(db: Session, redis_client, *, job_type: str, object_id: int) -> bool:
    """仅当 DB 状态可从 pending/system_error 转为 queued 时入队；重复调用不重复创建有效任务。"""
```

- [ ] 使用数据库条件更新实现状态抢占，不能先读后写：

```python
updated = db.execute(
    update(ExamAnswer)
    .where(ExamAnswer.id == answer_id, ExamAnswer.grading_status.in_(["pending", "system_error"]))
    .values(grading_status="queued", queued_at=utc_now())
).rowcount
```

- [ ] Redis 消息统一为 `{"type":"assignment"|"exam","id":123,"attempt":1}`，禁止两套不兼容格式继续扩散。
- [ ] API 必须先持久化数据库状态，再调用统一入队入口。Redis 暂时不可用时保留 `pending`，由恢复扫描重新入队，不得直接把正常答案计 0 分。
- [ ] 测试：重复入队只产生一条有效任务；Redis 故障不会丢失数据库任务；普通作业和考试使用同一消息协议。
- [ ] Run: `cd backend && python -m pytest tests/automated/test_judge_queue_reliability.py -q`
- [ ] Commit: `git commit -m "fix: make judge enqueue idempotent and recoverable"`

### Task 2：修复 Worker 丢消息、重复执行和 stale-running

**Files:**
- Modify: `backend/app/worker/judge_worker.py`
- Modify: `backend/app/services/judge_queue.py`
- Modify: `backend/app/services/exam_service.py`
- Test: `backend/tests/automated/test_judge_worker_recovery.py`

- [ ] Worker 领取任务时用条件更新 `queued -> running`；抢占失败说明消息重复，直接确认并跳过。
- [ ] Worker 成功后写 `completed/finished_at`；可重试异常写回 `pending` 并递增 `attempt_count`；达到最大次数后写 `system_error` 并保留错误详情。
- [ ] 对考试与普通作业都处理主循环外层的未知异常，禁止“打印 traceback 后丢掉已弹出的消息”。
- [ ] 恢复扫描同时处理：
  - `pending` 超过阈值：重新入队；
  - `queued` 超过阈值：重新发送通知；
  - `running` 超过执行超时：重置为 `pending` 后重新入队；
  - 超过最大重试：终止为 `system_error`，考试题计 0 分并触发最终汇总。
- [ ] 扫描必须使用 `updated_at/started_at`，不能只看 submission 的 `submitted_at`，否则每轮都会重复发送同一答案。
- [ ] 测试：进程在领取后崩溃可恢复；重复 Redis 消息不会执行两次；stale running 会重试；永久错误最终进入终态。
- [ ] Run: `cd backend && python -m pytest tests/automated/test_judge_worker_recovery.py tests/automated/test_judge_worker.py -q`
- [ ] Commit: `git commit -m "fix: recover interrupted judge jobs safely"`

### Task 3：考试最终评分原子化

**Files:**
- Create: `backend/app/services/exam_grading.py`
- Modify: `backend/app/services/exam_service.py`
- Modify: `backend/app/worker/judge_worker.py`
- Test: `backend/tests/automated/test_exam_finalization_concurrency.py`

- [ ] 把两份 `_maybe_finalize` 合并为 `exam_grading.finalize_if_ready()`。
- [ ] 使用 MySQL `SELECT ... FOR UPDATE` 锁定 `ExamSubmission`，锁内重新检查所有答案均为终态。
- [ ] `ExamGrade` 使用 upsert 或捕获唯一键冲突后重新读取；任何并发 Worker 都只能得到一份成绩。
- [ ] 总分只计算 `completed/system_error` 终态；`pending/queued/running` 任一存在时禁止结算。
- [ ] 在同一事务内写入 `ExamGrade`、`submission.score/status/graded_at`，不得分两次 commit。
- [ ] 测试：两个独立 Session 同时完成最后两题，最终只有一条 `ExamGrade`，分数正确，submission 为 `graded`。
- [ ] Run: `cd backend && python -m pytest tests/automated/test_exam_finalization_concurrency.py -q`
- [ ] Commit: `git commit -m "fix: finalize exam grades atomically"`

### Task 4：补全考试题目与发布校验

**Files:**
- Modify: `backend/app/schemas/__init__.py`
- Modify: `backend/app/api/exams.py`
- Modify: `backend/app/services/exam_service.py`
- Create: `backend/alembic/versions/<revision>_normalize_public_cases.py`
- Test: `backend/tests/automated/test_exam_validation.py`

- [ ] `PublicCase` 在 `model_validator(mode="before")` 中把历史 `{"input":[1,2],"expected":3}` 转成 `{"args":[1,2],"expected":3}`；不能只是允许并忽略 `input`。
- [ ] `expected` 必填；`args` 必须为数组；拒绝同时传入相互冲突的 `input` 和 `args`。
- [ ] Exam question PATCH 禁止接收裸 `dict`，改用明确的 `ExamQuestionUpdate` schema。
- [ ] 单选题必须至少两个选项且 `correct` 恰好一个并存在于选项中；多选题必须至少两个选项且所有正确键都存在；代码题必须有非空 `hidden_tests`、正数时间/内存限制。
- [ ] 所有题目 `points > 0`；发布时逐题执行校验，而不只是验证总分大于 0。
- [ ] Alembic 数据迁移规范化数据库中历史 `public_cases.input`；迁移必须可重复执行且保留 `expected`。
- [ ] 测试创建、PATCH、发布和历史格式转换的成功/失败路径。
- [ ] Run: `cd backend && python -m pytest tests/automated/test_exam_validation.py -q`
- [ ] Commit: `git commit -m "fix: validate exam questions and migrate public cases"`

### Task 5：统一 UTC 时间处理和考试边界

**Files:**
- Create: `backend/app/services/time_utils.py`
- Modify: `backend/app/api/exams.py`
- Modify: `backend/app/services/exam_service.py`
- Test: `backend/tests/automated/test_exam_time_boundaries.py`

- [ ] 提供：

```python
def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
```

- [ ] 删除考试代码中所有对 aware datetime 的 `replace(tzinfo=UTC)`。
- [ ] 覆盖恰好等于 `start_at/end_at/expires_at` 的行为，并统一约定：`now < start_at` 不可开始，`now >= end_at/expires_at` 不可答题或交卷。
- [ ] 测试 UTC、Asia/Shanghai aware datetime 和 MySQL 返回 naive datetime。
- [ ] Run: `cd backend && python -m pytest tests/automated/test_exam_time_boundaries.py -q`
- [ ] Commit: `git commit -m "fix: normalize exam timestamps to UTC"`

### Task 6：实验提交原子化与幂等

**Files:**
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/schemas/__init__.py`
- Modify: `backend/app/api/experiments.py`
- Create: `backend/alembic/versions/<revision>_experiment_submission_idempotency.py`
- Test: `backend/tests/automated/test_experiment_submission_idempotency.py`

- [ ] 请求增加 `client_request_id: UUID`，并建立 `(record_id, client_request_id)` 唯一约束。
- [ ] 提交时锁定 `ExperimentRecord`，在锁内计算下一个 `attempt_number`、复制快照并更新 record 状态。
- [ ] 同一 `client_request_id` 重试时返回原 submission；不同 key 才产生下一次 attempt。
- [ ] 处理唯一键竞争，禁止把数据库 IntegrityError 直接返回 500。
- [ ] 快照使用深复制，确保后续保存 cells 不改变历史提交。
- [ ] 测试并发提交、HTTP 重试、不可变快照和越权。
- [ ] Run: `cd backend && python -m pytest tests/automated/test_experiment_submission_idempotency.py -q`
- [ ] Commit: `git commit -m "fix: make experiment submission atomic and idempotent"`

### Task 7：完成学生实验提交 UI

**Files:**
- Modify: `frontend/src/api/experiments.js`
- Modify: `frontend/src/stores/experiment.js`
- Modify: `frontend/src/components/notebook/NotebookPlayer.vue`
- Modify: `frontend/src/views/student/ExperimentDetailView.vue`
- Test: `frontend/src/views/student/__tests__/ExperimentDetailView.spec.js`

- [ ] 在 Notebook 工具栏增加“提交实验”；提交前必须 flush 当前自动保存队列，失败时阻止提交。
- [ ] 每次点击生成并复用一个 `client_request_id`，直到请求成功或用户明确再次发起新提交。
- [ ] 显示当前保存状态、最近提交时间、提交次数和最近提交列表。
- [ ] 提交成功后继续允许编辑和再次提交；已评分/完成时按后端状态禁用。
- [ ] 离开页面仍使用现有实验 Store 的 flush/冲突提示逻辑。
- [ ] 测试保存失败阻止提交、请求重试不换 key、成功后刷新历史、重复提交生成新 key。
- [ ] Run: `cd frontend && npm.cmd test -- ExperimentDetailView.spec.js`
- [ ] Commit: `git commit -m "feat: add student experiment submission flow"`

### Task 8：完成教师实验查看、反馈与评分闭环

**Files:**
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/schemas/__init__.py`
- Modify: `backend/app/api/experiments.py`
- Create: `backend/alembic/versions/<revision>_experiment_reviews.py`
- Create: `frontend/src/views/teacher/ExperimentSubmissionsView.vue`
- Create: `frontend/src/views/teacher/ExperimentSubmissionDetailView.vue`
- Modify: `frontend/src/views/teacher/ExperimentManageView.vue`
- Modify: `frontend/src/router/index.js`
- Test: `backend/tests/automated/test_experiment_reviews.py`
- Test: `frontend/src/views/teacher/__tests__/ExperimentSubmissionsView.spec.js`

- [ ] Submission 增加 `score`、`feedback`、`reviewed_by_id`、`reviewed_at`；定义 `ExperimentReviewUpdate`。
- [ ] 新增教师评分接口，限制教师只能评分自己课程，开发者只能查看/评分自己模块，管理员可处理全部。
- [ ] 列表 API 返回学生、课程/模块、attempt、submitted_at、score 等展示字段，避免前端逐条 N+1 请求。
- [ ] 教师管理页增加“查看提交”，支持分页和按课程/模块/学生筛选。
- [ ] 详情页只读渲染 `cells_snapshot`，显示代码、Markdown 和保存的输出；禁止启动学生 Kernel 或修改快照。
- [ ] 保存反馈/成绩后更新 record 为 `graded`，但保留所有历史 attempt。
- [ ] 测试 Teacher A 看不到 Teacher B 数据、开发者模块边界、快照只读、评分落库。
- [ ] Run: `cd backend && python -m pytest tests/automated/test_experiment_reviews.py -q`
- [ ] Run: `cd frontend && npm.cmd test -- ExperimentSubmissionsView.spec.js`
- [ ] Commit: `git commit -m "feat: complete experiment review workflow"`

### Task 9：认证 Token 改为生产安全存储

**Files:**
- Modify: `backend/app/api/auth.py`
- Modify: `backend/app/services/auth_service.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/schemas/__init__.py`
- Modify: `frontend/src/stores/auth.js`
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/api/auth.js`
- Test: `backend/tests/automated/test_auth_cookies.py`
- Test: `frontend/src/stores/__tests__/auth.spec.js`

- [ ] Refresh Token 改为 `HttpOnly + Secure(生产) + SameSite=Lax + Path=/api/auth` Cookie；响应 JSON 不再暴露 refresh token。
- [ ] Access Token 只保存在 Pinia 内存，不写 localStorage；页面刷新时调用 cookie refresh 恢复登录。
- [ ] Axios 设置 `withCredentials: true`，刷新并发仍只能发起一次 refresh 请求。
- [ ] Logout 删除 Cookie，并继续撤销 Redis 中的 refresh JTI 和当前 access JTI。
- [ ] 生产环境校验 Cookie Secure、允许 Origin 和 HTTPS 配置；refresh/logout 校验 Origin。
- [ ] 测试 Cookie 属性、轮换、重放旧 refresh token、退出、页面恢复和并发 401。
- [ ] Run: `cd backend && python -m pytest tests/automated/test_auth_cookies.py -q`
- [ ] Run: `cd frontend && npm.cmd test -- auth.spec.js`
- [ ] Commit: `git commit -m "security: move refresh token to http-only cookie"`

### Task 10：生产 Compose、健康检查和配置校验

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`
- Create: `docker-compose.prod.yml`
- Create: `.env.example`
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Modify: `README.md`

- [ ] 创建 API、Worker、前端 Nginx、MySQL、Redis 服务；API 与 Worker 使用同一镜像但不同 command。
- [ ] Nginx 同源代理 `/api`，前端 history fallback 到 `index.html`。
- [ ] 增加 `/health/live` 和 `/health/ready`；ready 检查 MySQL、Redis，不能因 Docker judge image 暂时繁忙而永久失败。
- [ ] 生产环境启动时拒绝默认 `secret_key`、默认数据库密码、通配 CORS 和缺失必要变量。
- [ ] MySQL/Redis 只在内部网络，不把 3306/6379 暴露公网。
- [ ] Docker socket 权限风险必须写入 README；若仍挂载 socket，仅允许部署在专用主机，并限制 API/Worker 容器权限。不得宣称该方案是强多租户隔离。
- [ ] 增加迁移启动步骤：先 `alembic upgrade head`，成功后再启动 API/Worker。
- [ ] Run: `docker compose -f docker-compose.prod.yml config`
- [ ] Run: `docker compose -f docker-compose.prod.yml up -d --build`
- [ ] 验证 Nginx 首页、ready、登录、作业判题、考试判题和 Kernel；随后正常 `docker compose ... down`，不得删除 volumes。
- [ ] Commit: `git commit -m "build: add production compose deployment"`

### Task 11：可观测性与运维恢复

**Files:**
- Create: `backend/app/logging_config.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/worker/judge_worker.py`
- Modify: `backend/app/services/kernel_manager.py`
- Modify: `backend/app/config.py`
- Test: `backend/tests/automated/test_observability.py`

- [ ] 每个 HTTP 请求生成/透传 `X-Request-ID`，响应返回相同 ID。
- [ ] API、Worker、Kernel 日志至少包含 timestamp、level、request/job ID、submission/answer/record ID 和异常堆栈。
- [ ] 禁止 `print`/静默 `except`; Worker 未知异常必须写结构化错误并进入重试状态。
- [ ] 为扫描任务记录数量：expired、requeued、stale-running、system-error、finalized。
- [ ] 增加 `/metrics` 或最小内部指标接口，至少暴露队列积压和各状态任务数量；接口需受保护或仅内网开放。
- [ ] 测试 request ID 透传、500 日志、Worker job ID 日志和扫描计数。
- [ ] Run: `cd backend && python -m pytest tests/automated/test_observability.py -q`
- [ ] Commit: `git commit -m "chore: add request and job observability"`

### Task 12：补齐端到端测试与 CI 门禁

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `frontend/e2e/assignment-flow.spec.js`
- Create: `frontend/e2e/exam-flow.spec.js`
- Create: `frontend/e2e/experiment-flow.spec.js`
- Create: `frontend/playwright.config.js`
- Modify: `frontend/package.json`
- Modify: `backend/pytest.ini`

- [ ] 后端单元/集成测试增加超时和 marker：`unit`、`integration`、`docker`；CI 普通 job 不得因真实 Docker 测试无限等待。
- [ ] 增加 MySQL 与 Redis CI services，至少一组测试必须运行真实 MySQL，避免 SQLite 掩盖锁、JSON、时区和唯一约束问题。
- [ ] Docker smoke 独立 job，显式构建 judge/kernel image 后运行。
- [ ] Playwright 覆盖四条主流程：
  - 学生登录、选课、阅读课时；
  - 作业提交、Worker 判题、结果展示；
  - 考试开始、自动保存、交卷、编程题评分；
  - 教师发布 Notebook、学生运行保存提交、教师查看评分。
- [ ] CI 增加 frontend test/build、backend full test、migration from empty DB、migration from pre-change fixture、E2E。
- [ ] 所有 job 设置合理 timeout；保存失败时上传 pytest/Playwright 日志和 trace。
- [ ] Run: `cd backend && python -m pytest -q`
- [ ] Run: `cd frontend && npm.cmd test && npm.cmd run build && npx.cmd playwright test`
- [ ] Commit: `git commit -m "test: enforce beta quality gates in CI"`

### Task 13：仓库清理与文档收敛

**Files:**
- Modify: `.gitignore`
- Modify: `README.md`
- Modify: `docs/架构设计总览.md`
- Delete after verification: `backend/_build_main.py`
- Delete after verification: `backend/_fix_module.py`
- Delete after verification: `backend/fix_data.py`
- Delete or move to documented manual-tools directory: `backend/tests/debug_kernel.py`, `backend/tests/diag_execute.py`, `backend/tests/kernel_*_test.py`, `backend/tests/test_kernel_prototype.py`
- Remove generated samples from Git after backup decision: `backend/storage/exec.json`, `backend/storage/exec_result.json`, `backend/storage/nb.json`

- [ ] 逐个确认临时脚本没有被 CI、README 或生产启动引用，再删除或迁移，禁止批量盲删。
- [ ] 真实运行数据移出 Git；只保留明确命名的测试 fixture。
- [ ] README 的判题流程、启动命令、Cookie 认证、实验评分、队列恢复和生产限制必须与代码一致。
- [ ] 架构文档明确数据库为任务事实源、Redis 为通知层，以及状态转换图。
- [ ] Run: `git grep "_build_main\\|_fix_module\\|fix_data.py\\|storage/exec.json"`
- [ ] Run: `git diff --check`
- [ ] Commit: `git commit -m "docs: align repository with beta architecture"`

---

## 最终验收

- [ ] `alembic upgrade head` 能从空数据库成功执行。
- [ ] 从第三轮修复前的数据库快照升级后，历史 public cases 和提交记录仍可读取。
- [ ] `cd backend && python -m pytest -q` 全部通过，无无故 hang。
- [ ] `cd frontend && npm.cmd test` 全部通过。
- [ ] `cd frontend && npm.cmd run build` 成功且无重复路由/关键警告。
- [ ] Playwright 四条主流程全部通过。
- [ ] Docker judge/kernel smoke 全部通过，超时容器被清理。
- [ ] 人工终止 Worker 后，queued/running 作业能够自动恢复且不会重复计分。
- [ ] 两个 Worker 并发完成最后两道考试题，只产生一条最终成绩。
- [ ] 学生实验提交重试不产生重复 attempt，教师能查看快照并评分。
- [ ] 浏览器 localStorage 中不存在 access/refresh token。
- [ ] `docker compose -f docker-compose.prod.yml config` 和生产 smoke 通过。
- [ ] `git status --short` 只包含本计划产生的预期修改。
- [ ] `git diff --check` 无空白错误。

## 明确不在本轮范围

- AI 助教、推荐系统、聊天功能。
- 大规模 Kubernetes、多地域容灾。
- 支持 Python 以外的新判题语言。
- Notebook 实时多人协作。
- 无明确需求的 UI 全量重做。
