# Acceptance Demo Data and Course Management Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复教师课程管理页白屏，并提供一套可重复创建、足以验收课程/作业/考试/判题/AI 评分流程的完整演示数据。

**Architecture:** 前端用 Vitest 组件回归测试固定 `ChapterManageView` 的路由初始化；后端新增独立的 API 驱动验收数据脚本，所有资源都通过现有 `/api/v1` 接口创建和发布，以精确的 `[验收]` 标题和固定用户名实现幂等。脚本不接触数据库和 DeepSeek 密钥；AI Rubric 由已配置的后端在真实发布请求中生成。

**Tech Stack:** Vue 3、Vue Router、Vitest、Vue Test Utils、FastAPI、Python 3.11、httpx、pytest、Docker Compose、DeepSeek `deepseek-v4-flash`

---

实施前完整阅读：

- `docs/superpowers/specs/2026-07-29-acceptance-demo-data-design.md`
- `frontend/src/views/teacher/ChapterManageView.vue`
- `frontend/src/views/teacher/__tests__/AIGradingReview.spec.js`
- `frontend/src/api/courses.js`
- `backend/app/api/v1/users.py`
- `backend/app/api/v1/courses.py`
- `backend/app/api/v1/assignments.py`
- `backend/app/api/v1/exams.py`
- `backend/app/api/v1/judge.py`
- 对应的 Pydantic schema 与 service 文件

始终遵守：

- 当前分支必须是 `AIpanti`；
- 不显示、复制或提交任何 API Key；
- 不提交 `DAI智能代码评分方案_V1.md`、`.env`、`.pt-*` 或其他用户/临时文件；
- 不删除原有 E2E 数据；
- 遇到接口字段与计划不一致时，以当前 schema 为准，并把最小适配记录在提交说明中；
- 每个实现任务均按 RED → GREEN → REFACTOR 执行。

## Task 1: 锁定并修复课程管理页白屏

**Files:**

- Create: `frontend/src/views/teacher/__tests__/ChapterManageView.spec.js`
- Modify: `frontend/src/views/teacher/ChapterManageView.vue`

- [ ] **Step 1: 写一个会暴露当前异常的组件测试**

参考现有教师视图测试的 Pinia、router 和 API mock 写法。测试中：

```js
const push = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' } }),
  useRouter: () => ({ push }),
}))

vi.mock('../../../api/courses', () => ({
  coursesAPI: {
    get: vi.fn(),
    getChapters: vi.fn(),
    createChapter: vi.fn(),
    createLesson: vi.fn(),
    updateLesson: vi.fn(),
  },
}))
```

让 `get()` 返回 `{ id: 1, title: '验收课程' }`，让 `getChapters()` 返回：

```js
[
  {
    id: 11,
    title: '第一章',
    order_index: 1,
    lessons: [
      { id: 111, title: '第一课', content_type: 'markdown', order_index: 1 },
    ],
  },
]
```

挂载时使用 `createPinia()`。等待异步刷新后断言：

- 存在 `验收课程`；
- 存在 `第一章`；
- 存在 `第一课`；
- `coursesAPI.get(1)` 和 `coursesAPI.getChapters(1)` 被调用。

- [ ] **Step 2: 单独运行测试并确认 RED**

Run:

```bat
cd frontend
npm.cmd test -- src/views/teacher/__tests__/ChapterManageView.spec.js
```

Expected: 测试因 `ReferenceError: useRouter is not defined` 失败。若失败原因不是该异常，先修正测试环境，禁止为迎合测试改业务行为。

- [ ] **Step 3: 做最小修复**

在 `ChapterManageView.vue` 中把：

```js
import { useRoute } from 'vue-router'
```

改为：

```js
import { useRoute, useRouter } from 'vue-router'
```

不要顺带重构该页面。

- [ ] **Step 4: 确认 GREEN**

Run:

```bat
cd frontend
npm.cmd test -- src/views/teacher/__tests__/ChapterManageView.spec.js
```

Expected: 新测试全部通过，无未处理 Promise 或 Vue warning。

- [ ] **Step 5: 运行相邻回归测试**

Run:

```bat
cd frontend
npm.cmd test -- src/views/teacher
```

Expected: 教师视图测试全部通过。

- [ ] **Step 6: 提交白屏修复**

Run:

```bat
git add frontend/src/views/teacher/ChapterManageView.vue frontend/src/views/teacher/__tests__/ChapterManageView.spec.js
git diff --cached --check
git commit -m "fix: restore course chapter management view"
```

Expected: 只包含上述两个文件。

## Task 2: 定义验收数据并用测试固定完整性

**Files:**

- Create: `backend/seed_acceptance_data.py`
- Create: `backend/tests/automated/test_acceptance_seed.py`

- [ ] **Step 1: 先写数据契约测试**

在测试中导入 `ACCEPTANCE_DATA`，断言：

- 课程数为 2；
- 章节总数为 6；
- 课时总数为 12；
- 作业数为 3；
- 作业代码题总数为 9；
- 考试数为 2；
- 考试题总数为 12；
- 每门课程恰好 3 章，每章恰好 2 个课时；
- 每个课时内容同时包含学习目标、核心知识、示例和练习；
- 每个代码题拥有非空 `function_name`、`signature`、`starter_code`；
- 每个代码题至少 2 个 `public_cases`，且 `hidden_tests` 非空；
- 作业题的 grading mode 集合覆盖 `legacy`、`shadow`、`active`；
- 选择题 options、correct_answer、points、order_index 完整；
- 两份考试总分分别为 100。

固定标题和函数名必须与设计文档完全一致。

- [ ] **Step 2: 添加幂等辅助函数的失败测试**

为将要实现的精确查找函数写测试，例如：

```py
def test_find_exact_returns_matching_item_without_mutation():
    items = [{"id": 1, "title": "A"}, {"id": 2, "title": "B"}]
    assert find_exact(items, "title", "B") == items[1]
    assert find_exact(items, "title", "missing") is None
```

再用一个轻量 fake client 或 `httpx.MockTransport` 固定“第一次创建、第二次复用”的行为。至少覆盖一个父子层级：

- 第一次 ensure course/chapter/lesson 发生 3 次 POST；
- 第二次传回第一次创建的列表后不再 POST；
- 最终 ID 不变。

不要让测试依赖真实 Docker、数据库或互联网。

- [ ] **Step 3: 运行测试并确认 RED**

Run:

```bat
cd backend
.venv\Scripts\python.exe -m pytest tests\automated\test_acceptance_seed.py -q --basetemp=.pt-acceptance-seed
```

Expected: 因模块或数据常量尚不存在而失败。

- [ ] **Step 4: 创建模块骨架和完整常量**

`backend/seed_acceptance_data.py` 必须使用：

```py
if __name__ == "__main__":
    raise SystemExit(main())
```

从而允许测试安全导入。

定义：

- `ACCEPTANCE_DATA`：完整两门课程数据；
- `DEMO_STUDENTS`：两名验收学生；
- `DEMO_SUBMISSIONS`：代表性提交；
- `find_exact(items, field, value)`；
- `SeedError`；
- 后续需要的轻量数据类或类型别名。

所有 Markdown 课时都写成可实际阅读的教学内容，不使用 `TODO`、`示例内容` 或重复占位段落。

- [ ] **Step 5: 实现 API Client**

实现 `ApiClient`，封装：

- `login(username, password)`；
- 带 Bearer Token 的 `get/post/patch`；
- 分页列表归一化；
- 4xx/5xx 错误转换成不泄漏 Authorization header 的 `SeedError`；
- 默认 30 秒请求超时；
- 对 AI 发布请求允许更长超时（建议 180 秒）。

CLI 参数至少包括：

```text
--base-url              默认 http://localhost:8080/api/v1
--admin-username        默认 admin
--teacher-username      默认 teacher
--submission-timeout    默认 180
--skip-submissions      可选，仅在排障时跳过预置提交
```

密码优先从环境变量读取：

- `DAI_SEED_ADMIN_PASSWORD`
- `DAI_SEED_TEACHER_PASSWORD`
- `DAI_SEED_STUDENT_PASSWORD`

本地默认均为 `Passw0rd!`。禁止读取或打印 DeepSeek key。

- [ ] **Step 6: 运行纯数据与辅助函数测试**

Run:

```bat
cd backend
.venv\Scripts\python.exe -m pytest tests\automated\test_acceptance_seed.py -q --basetemp=.pt-acceptance-seed
```

Expected: 数据契约和无网络单元测试通过。

## Task 3: 实现用户、课程与内容的幂等创建

**Files:**

- Modify: `backend/seed_acceptance_data.py`
- Modify: `backend/tests/automated/test_acceptance_seed.py`

- [ ] **Step 1: 扩展 fake API RED 测试**

覆盖：

- 用户已存在时不重复创建，并通过管理员接口确保其 active、role 正确和密码确定；
- 同名课程存在时校验 teacher ownership；
- 章节按课程内精确标题复用；
- 课时按章节内精确标题复用；
- 重跑后资源计数不变。

- [ ] **Step 2: 实现账号保障**

管理员登录后：

1. 分页查询用户；
2. 找不到 `accept_student_a` 或 `accept_student_b` 时创建；
3. 已存在时确保角色是 `student`、状态为 active，并通过当前用户管理接口重置密码；
4. 再分别登录两个学生账号，尽早发现凭据问题。

不要修改 `teacher` 或 `admin` 的角色。

- [ ] **Step 3: 实现课程、章节与课时保障**

教师登录后对两门验收课程：

1. 按精确标题查询；
2. 不存在则创建，存在则校验 `teacher_id`；
3. 补齐描述、课程图片以外的必要元数据；
4. 按标题补齐 3 章；
5. 在各自章节下按标题补齐 2 课时；
6. 缺失时创建，存在时不重复；
7. 最终把课程设为 published。

若现有 API 支持更新课时，则可对验收脚本拥有的同名课时补齐内容；若不支持，已存在内容不覆盖，只做结构校验并在摘要中提示。

- [ ] **Step 4: 实现选课保障**

以两个学生身份为两门已发布课程调用选课接口。若接口返回“已经选课”之类的冲突，先用列表确认确实已选课，再视为成功；其他冲突仍然失败。

- [ ] **Step 5: 运行单元测试**

Run:

```bat
cd backend
.venv\Scripts\python.exe -m pytest tests\automated\test_acceptance_seed.py -q --basetemp=.pt-acceptance-seed
```

Expected: 资源重跑测试通过。

## Task 4: 实现作业、考试与真实 AI 发布

**Files:**

- Modify: `backend/seed_acceptance_data.py`
- Modify: `backend/tests/automated/test_acceptance_seed.py`

- [ ] **Step 1: 写发布顺序的 RED 测试**

Fake API 必须验证：

- 已发布的验收作业/考试在需要补题时先切回 draft；
- 仅创建缺失题目；
- 所有题目补齐后才调用 publish；
- 不需要变更且已经发布的对象不做无意义的重复发布；
- 发布 AI 题时使用长超时；
- 绝不在 payload 里出现 API Key。

- [ ] **Step 2: 实现三份作业**

严格创建设计文档中的三份作业和九道代码题。每道题使用当前 `JudgeQuestionCreate` schema 所要求的真实字段：

- title/description；
- function_name/signature/starter_code；
- public_cases/hidden_tests；
- time_limit_ms/memory_limit_mb；
- grading_mode。

若作业已发布但缺题，使用现有更新接口安全切为 draft，再创建缺失题。以作业内精确题目标题识别重复。

补齐后调用真实 publish endpoint。shadow/active 题发布时必须让后端走当前 DeepSeek Rubric 生成和锁定流程；不要在脚本中伪造 Rubric。

- [ ] **Step 3: 实现两份考试**

严格创建设计文档中的两份考试，每份：

- 2 道 single choice；
- 2 道 multiple choice；
- 2 道 code；
- 合计 100 分；
- 开始/结束时间覆盖当前验收日期；
- 最终发布。

按考试内 `prompt`（代码题可结合 function name）精确识别重复。使用当前 schema 的 question type 枚举和值，不猜测字段。

- [ ] **Step 4: 验证发布后的 Rubric 状态**

发布结束后重新 GET 作业/考试详情或题目列表。对 shadow/active 代码题检查后端暴露的 Rubric/版本/锁定状态字段。若当前 API 不向该角色返回具体 Rubric，至少确认发布成功且对象状态为 published，并在摘要中标明验证层级。

- [ ] **Step 5: 运行单元测试**

Run:

```bat
cd backend
.venv\Scripts\python.exe -m pytest tests\automated\test_acceptance_seed.py -q --basetemp=.pt-acceptance-seed
```

Expected: 全部通过。

## Task 5: 实现代表性学生提交和结果轮询

**Files:**

- Modify: `backend/seed_acceptance_data.py`
- Modify: `backend/tests/automated/test_acceptance_seed.py`

- [ ] **Step 1: 写提交幂等和轮询 RED 测试**

覆盖：

- 某学生对目标问题已有至少一条提交时不重复 POST；
- 没有提交时创建；
- `queued`/`running` 会继续轮询；
- `completed`/`failed`/`system_error` 等当前真实终态会结束轮询；
- 超过 `--submission-timeout` 抛出包含 submission ID 的错误；
- 多个提交中任意失败使 CLI 最终退出非零。

- [ ] **Step 2: 实现四类代表性提交**

至少创建：

- 学生甲对一个 legacy 题的正确提交；
- 学生甲对一个 active 题的正确提交；
- 学生乙对一个 shadow 题的部分错误提交；
- 学生乙对一个 active 题的错误提交。

每份代码都是真实可运行 Python，错误提交应是可信的边界错误，而不是语法错误。这样教师端可观察传统测试、AI 评分和最终分数之间的差异。

- [ ] **Step 3: 实现有界轮询和摘要**

提交后按当前 submission/result endpoint 轮询。摘要打印：

- 两门课程 ID；
- 三份作业 ID；
- 两份考试 ID；
- 每份代表性 submission ID 和终态；
- 创建与复用数量；
- 教师和学生用户名；
- 教师课程管理推荐 URL。

摘要不打印 token、请求 header、密码以外的秘密；默认演示密码可按 README 约定显示一次。

- [ ] **Step 4: 运行测试**

Run:

```bat
cd backend
.venv\Scripts\python.exe -m pytest tests\automated\test_acceptance_seed.py -q --basetemp=.pt-acceptance-seed
```

Expected: 全部通过。

- [ ] **Step 5: 静态检查敏感信息**

Run:

```bat
git diff -- backend/seed_acceptance_data.py backend/tests/automated/test_acceptance_seed.py
rg -n "sk-|DEEPSEEK_API_KEY|Authorization:" backend/seed_acceptance_data.py backend/tests/automated/test_acceptance_seed.py
```

Expected: `rg` 不匹配任何硬编码 key；若匹配到测试中的字段名，也必须确认没有值或 header 内容。

## Task 6: 编写本地验收说明

**Files:**

- Modify: `README.md`

- [ ] **Step 1: 添加“完整验收数据”章节**

写明前置条件：

- Docker 服务已经启动；
- 后端环境已配置 DeepSeek，模型为 `deepseek-v4-flash`；
- 不要求把 key 放进命令行。

给出 Windows 命令：

```bat
cd backend
.venv\Scripts\python.exe seed_acceptance_data.py --base-url http://localhost:8080/api/v1
```

列出三个验收账号、默认密码、两门课程名，以及教师管理页 URL 形式：

```text
http://localhost:8080/teacher/courses/<脚本输出的课程ID>/manage
```

明确说明脚本可重复执行，第二次不会重复创建数据。

- [ ] **Step 2: 校正文档中的冲突命令**

如果 README 仍把旧脚本错误写为 `python -m app.seed_data`，改成与真实文件位置一致；保留旧 seed 的用途说明，不让它与新的完整验收数据混淆。

- [ ] **Step 3: 提交验收数据功能**

Run:

```bat
git add backend/seed_acceptance_data.py backend/tests/automated/test_acceptance_seed.py README.md
git diff --cached --check
git status --short
git commit -m "feat: add idempotent acceptance demo data"
```

Expected: 暂存区只包含上述三个文件，用户原始方案和 `.pt-*` 没有被提交。

## Task 7: 运行自动化验证

**Files:**

- Verify only

- [ ] **Step 1: 后端专项测试**

Run:

```bat
cd backend
.venv\Scripts\python.exe -m pytest tests\automated\test_acceptance_seed.py -q --basetemp=.pt-acceptance-seed
```

Expected: 全部通过。

- [ ] **Step 2: 前端完整测试**

Run:

```bat
cd frontend
npm.cmd test
```

Expected: 全部通过，无 unhandled error。

- [ ] **Step 3: 前端生产构建**

Run:

```bat
cd frontend
npm.cmd run build
```

Expected: exit code 0。

- [ ] **Step 4: 工作树检查**

Run:

```bat
git status --short --branch
git log -3 --oneline
```

Expected: 只有实施前已有的用户文档和 `.pt-*` 等未追踪文件；本任务应有两个新实现提交。

## Task 8: 部署前端并运行真实验收数据脚本

**Files:**

- Runtime only; never commit environment files

- [ ] **Step 1: 检查服务健康**

Run:

```bat
docker compose -f docker-compose.prod.yml ps
curl.exe -fsS http://localhost:8080/api/v1/health
```

Expected: 相关服务 healthy/running，health 返回成功。

- [ ] **Step 2: 安全重建前端**

只重建需要更新的 frontend 服务。必须沿用当前容器/Compose 的环境配置，禁止为了方便把 DeepSeek key 写入仓库、计划或命令输出。若 Compose 要求临时 env 文件：

1. 在仓库内创建名字明确的临时 env；
2. 从当前运行环境安全填充，命令输出不得显示内容；
3. `docker compose --env-file <临时文件> ... up -d --build --no-deps --force-recreate frontend`；
4. `del` 临时文件；
5. 用 `git status` 确认未被跟踪。

- [ ] **Step 3: 第一次运行验收脚本**

Run:

```bat
cd backend
.venv\Scripts\python.exe seed_acceptance_data.py --base-url http://localhost:8080/api/v1
```

Expected:

- 两门课程、六章、十二课时、三作业、九道作业题、两考试、十二道考试题就绪；
- shadow/active 发布成功，真实 AI Rubric 流程没有报错；
- 两名学生均完成选课；
- 代表性提交进入终态；
- exit code 0。

记录脚本输出的课程 ID，供浏览器验收使用。

- [ ] **Step 4: 第二次运行并验证幂等**

再次运行同一命令。Expected:

- 主要资源均报告“复用”；
- 课程/章节/课时/作业/问题/考试/考试题/预置提交数量不增加；
- exit code 0。

通过教师 API 或脚本摘要记录前后计数，不以肉眼猜测。

- [ ] **Step 5: 最终运行态检查**

Run:

```bat
docker compose -f docker-compose.prod.yml ps
curl.exe -fsS http://localhost:8080/api/v1/health
git status --short --branch
```

Expected: 服务正常，仓库无本任务遗漏改动，无临时 env。

## Task 9: 交回 001 验收

- [ ] **Step 1: 向 001 报告**

报告必须包含：

- 两个实现提交的 hash；
- 变更文件列表；
- 所有测试/构建的精确结果；
- 两次 seed 的创建/复用摘要；
- 两门课程 ID 和教师管理 URL；
- 代表性 submission 的终态；
- 当前 Docker 状态；
- 剩余问题（若无，明确写“未发现已知阻塞问题”）。

- [ ] **Step 2: 停止执行并等待 001 的浏览器验收**

不要自行宣布用户验收完成。001 将使用真实浏览器检查：

- 原白屏 URL 已恢复内容；
- 验收课程显示 3 章 6 课时；
- 页面可以打开添加章节并取消；
- 教师作业/考试/成绩或 AI 复核存在完整数据；
- 学生能看到课程、作业和考试；
- 控制台无相关 Vue 异常或关键请求错误。
