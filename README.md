# DAI 实验平台

面向人工智能课程的一站式在线实验平台。支持课程学习、在线编程实验、作业与考试自动判题、AI 辅助评分、Notebook 交互式实验、多档运行环境，以及课程封面和课时视频上传。

---

## 快速开始

### 环境要求

- **Docker Desktop**（运行 MySQL、Redis、判题沙箱）
- **Python 3.12**（后端；与 CI 及 Dockerfile 基线一致，仓库含 `backend/.python-version`）
- **Node.js 18+**（前端）

### 1. 克隆项目

```bash
git clone <repo-url>
cd "DAI Experiment Platform"
```

### 2. 启动基础服务（MySQL + Redis）

```bash
docker compose up -d mysql redis
```

### 3. 初始化后端

```bash
cd backend

# 创建虚拟环境
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 配置环境变量
copy .env.example .env

# 数据库迁移
.venv\Scripts\python.exe -m alembic upgrade head

# 创建管理员账号
.venv\Scripts\python.exe -m app.cli create-admin --username admin --password Test1234! --real-name Administrator

# 构建判题镜像（仅首次需要）
docker build -t dai-judge-python:latest docker\judge
docker build -t dai-kernel-python:latest docker\kernel
```

### 4. 启动后端服务

需要打开三个终端窗口：

```bash
# 终端 1：后端 API
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2：判题 Worker（按需启动）
cd backend
.venv\Scripts\python.exe -m app.worker.judge_worker

# 终端 3：前端开发服务器
cd frontend
npm install
npm run dev
```

### 5. 访问

- 前端页面：<http://localhost:5173>
- Swagger 文档：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/api/v1/health/ready>

### 6. 生产前内测全量数据

全量内测种子会清理业务演示数据，保留管理员和环境控制面数据。脚本拒绝在
`DAI_ENVIRONMENT=production` 下执行，并且必须显式确认重置。

首次使用前，先初始化并构建三类运行环境：

```bash
cd backend
.venv\Scripts\python.exe -m app.cli seed-environments --enqueue
```

等待 `basic`、`data`、`torch-cpu` 三个版本均为 `available` 后运行：

```bash
.venv\Scripts\python.exe -m app.seed_data --confirm-internal-reset
```

如果全量内测数据已经存在，只想补充典型课程的 AI 评分演示数据，可执行：

```bash
.venv\Scripts\python.exe -m app.seed_data --augment-ai-demo
```

该增量命令不会清理现有业务数据，会幂等补充 3 个已发布 AI 评分作业和 3 个已发布考试；
每场考试包含 1 道选择题和 1 道已锁定 Rubric 的 AI 评分编程题。学生端使用
`student_24621600_01 / Test1234!` 登录后即可查看。

也可以使用 Windows 一键内测启动模式。它会启动环境构建 Worker，等待三类环境
构建完成，写入全量内测数据，然后启动 API、判题 Worker 和前端：

```bat
start.bat --internal
```

普通执行 `start.bat` 不会重置数据库；`start.bat --internal` 每次执行都会重建
内测业务数据，请只在本地或预生产测试库使用。

数据规模：3 位教师、400 位学生、10 个教学班（每班 40 人）、30 门课程、12 个
Notebook 实验模块。典型课程包含至少 6 个章节、24 个课时、10 个作业和 10 场考试。

账号示例：

| 用户名 | 默认密码 | 角色 |
|--------|----------|------|
| `admin` | `Test1234!` | 管理员 |
| `teacher_zhang` | `Test1234!` | 典型教师 |
| `teacher_chen` | `Test1234!` | 教师 |
| `teacher_zhao` | `Test1234!` | 教师 |
| `developer_lab` | `Test1234!` | 实验开发者 |
| `student_24621600_01` | `Test1234!` | 学生 |

密码可通过以下环境变量覆盖：
`DAI_SEED_ADMIN_PASSWORD`、`DAI_SEED_TEACHER_PASSWORD`、
`DAI_SEED_STUDENT_PASSWORD`、`DAI_SEED_DEVELOPER_PASSWORD`。

学生学号使用 `24621600` 至 `24621609` 作为班级前缀，最后两位为 `01` 至 `40`。

**注意**：这是预生产/内测重置脚本，不应在正式生产库执行。

---

---
## 完整验收数据

用于验收课程管理、作业、考试、代码判题和 AI 评分全流程的幂等演示数据脚本。

### 前置条件

- Docker 服务已启动（`docker compose up -d`）
- 后端环境已配置 DeepSeek API Key（环境变量 `DAI_AI_API_KEY`），模型为 `deepseek-v4-flash`
- 后端 API 在 <http://localhost:8080> 可访问
- 不需要把 API Key 放进命令行参数

### 运行

```bat
cd backend
.venv\Scripts\python.exe seed_acceptance_data.py --base-url http://localhost:8080/api/v1
```

### 验收账号

| 角色 | 用户名 | 默认密码 | 用途 |
|------|--------|----------|------|
| 教师 | `teacher` | `Passw0rd!` | 课程、作业、考试和成绩验收 |
| 学生甲 | `accept_student_a` | `Passw0rd!` | 正确/高质量提交 |
| 学生乙 | `accept_student_b` | `Passw0rd!` | 错误或部分正确提交 |
| 管理员 | `admin` | `Passw0rd!` | 仅用于创建学生账号 |

密码可通过环境变量覆盖：`DAI_SEED_ADMIN_PASSWORD`、`DAI_SEED_TEACHER_PASSWORD`、`DAI_SEED_STUDENT_PASSWORD`。

### 创建的课程

| 课程 | 章节 | 课时 | 作业 | 考试 |
|------|------|------|------|------|
| `[验收] Python 算法与工程实践` | 3 章 | 6 课时 | 2 份（6 道编程题） | 1 份（6 道题，含 AI 评分） |
| `[验收] 数据分析与机器学习入门` | 3 章 | 6 课时 | 1 份（3 道编程题） | 1 份（6 道题，含 AI 评分） |

教师管理页 URL（脚本结束后输出课程 ID）：
```text
http://localhost:8080/teacher/courses/<脚本输出的课程ID>/manage
```

### 幂等性

脚本可重复执行，第二次不会重复创建数据。所有资源按精确的 `[验收]` 标题和用户名识别，已存在的课程、章节、课时、作业、题目、考试和提交全部复用。

---

## 判题架构

### 正式提交（异步）

```text
学生提交代码 → API 创建 Submission(status=queued) → 入队 Redis judge:queue
                                                        ↓
                                               Worker brpop 消费
                                                        ↓
                                              Docker sandbox 运行 pytest
                                                        ↓
                                              更新 Submission status/score
                                                        ↓
                                              前端轮询 GET /result 获取结果
```

### 自测（同步）

```text
学生点击自测 → API sample-run → 仅用公开样例构建测试 → Docker sandbox 同步运行
                                                              ↓
                                                    直接返回 output/status/execution_time_ms
                                                    （不创建 Submission，不计次数）
```

### 考试判题

```text
学生交卷 → 选择题立即评分 → 代码题入队 Redis judge:exam:queue
                                    ↓
                           Worker 消费判题（与普通作业共用进程）
                                    ↓
                          全部答案 completed → 生成 ExamGrade
```

### 判题队列可靠性

- **原子抢占**：`claim_job()` 条件 UPDATE `queued→running`，多 Worker 不会重复执行同一任务
- **恢复扫描**：15 秒间隔扫描 `pending`/`running` 超时任务，重新入队为 `queued`
- **最大重试**：达到 `MAX_ATTEMPTS` 后写入 `system_error` 终态，考试答案立即触发 `finalize_if_ready`
- **去重**：相同 `queued` 任务重复推送时更新 `queued_at` 而非创建新记录

### 后台任务（FastAPI lifespan）

| 任务 | 间隔 | 说明 |
|------|------|------|
| 过期考试扫描 | 15 秒 | 自动交卷超时考试 |
| 判题任务恢复 | 15 秒 | `requeue_stale_jobs` 恢复超时 pending/running 任务 |
| Kernel 清理 | 5 分钟 | 销毁 15 分钟无活动的 Kernel 会话 |

### 启动方式

```bash
# 终端 1：后端 API（含 lifespan 后台任务）
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2：判题 Worker（消费 judge:queue 和 judge:exam:queue）
cd backend
.venv/Scripts/python.exe -m app.worker.judge_worker

# 终端 3：前端
cd frontend
npm run dev
```

---
## 认证机制

- **Access Token**：JWT，30 分钟过期，存于 Pinia 内存（不写 localStorage）
- **Refresh Token**：JWT，7 天过期，仅存于 HttpOnly + Secure + SameSite=Lax Cookie（`Path=/api/v1/auth`）
- **登录响应**：JSON body 仅返回 `access_token`/`expires_in`/`user`，不返回 `refresh_token`
- **刷新**：`POST /auth/refresh` 优先从 Cookie 读取，备选 JSON body；使用 GETDEL 原子消费旧 token（防并发重放）
- **登出**：`POST /auth/logout` 撤销 refresh token + access token 加入黑名单
- **Origin 校验**：refresh/logout 端点校验 Origin 头，跨域请求返回 403

## 实验提交

```text
学生点击提交 → POST /experiments/records/{id}/submit
                    ↓
              加载 record + 所有权校验
                    ↓
              client_request_id 幂等检查（已存在 → 直接返回）
                    ↓
              SELECT FOR UPDATE 锁定 record 行
                    ↓
              锁内二次幂等 + 计算 attempt_number
                    ↓
              深复制 cells_sources 为不可变快照 → 写入 experiment_submissions
```

- **幂等**：同一 `client_request_id`（UUID v4）重复提交返回已有记录（201 而非 409）
- **并发安全**：行锁 + 冲突 retry（SQLite 兼容）
- **教师评分**：`PATCH /submissions/{id}/review`，评分 0-100，空 review 拒绝（422）
- **提交列表**：教师/管理员可按课程查看，返回学生姓名和入口名称，分页

## Docker Compose 生产部署

```bash
# 环境变量（必填）
export DAI_SECRET_KEY=<至少16字符的唯一密钥>
export DAI_CORS_ORIGINS=https://your-domain.com
export DAI_DB_PASSWORD=<数据库密码>

# 启动全栈
docker compose -f docker-compose.prod.yml up -d

# 验证
curl http://localhost:8080/api/v1/health/ready
# → {"status":"ready","checks":{"mysql":"ok","redis":"ok"}}
```

### DoD 判题配置

Worker 容器通过宿主机 docker.sock 启动 judge 容器。需配置宿主机工作目录：

```yaml
# docker-compose.prod.yml
environment:
  DAI_JUDGE_WORK_DIR: /judge-work              # 容器内路径（文件操作）
  DAI_JUDGE_HOST_WORK_DIR: /opt/dai/judge-work # 宿主机绝对路径（传给 Docker -v）
volumes:
  - ./judge-work:/judge-work  # bind mount，两边路径对应
```

## 数据库迁移与回滚

### 升级

生产发布顺序（TASK-014/TASK-016）：**先备份，再迁移，最后起新 API**——
迁移由 compose 的一次性 `migrate` 服务执行，API 容器自身不再运行 Alembic。
真实部署信息、责任人与恢复证据必须先按
[`docs/backup-restore.md`](docs/backup-restore.md) 的待办表确认。

```bash
# 1. 备份（TASK-014：自动化备份依赖真实部署主机信息，落地前须按部署环境
#    先完成数据库与持久卷的备份并验证可恢复）
# 2. 执行迁移（一次性服务；失败则新 API 不会启动，旧 API 不受影响）
docker compose -f docker-compose.prod.yml up migrate

# 3. 部署其余服务（api/worker/frontend 等待 migrate 成功后才启动）
docker compose -f docker-compose.prod.yml up -d
```

### 回滚（生产环境）

迁移 `f2a3b4c5d678`（add course whitelist）的 downgrade 会：
1. 将 `courses.visibility` 中所有 `public` / `whitelist` 课程归一化为 `private`；
2. 删除 `course_whitelist_students` 表（含索引与外键）。

**回滚到旧版本前必须先导出备份**，否则白名单关系与可见性设置不可恢复：

```bash
# 1. 白名单关系表全量备份（downgrade 会删表，此备份需含建表语句）
mysqldump -u<用户> -p <库名> course_whitelist_students > whitelist_bak_<日期>.sql

# 2. 可见性原值备份（--replace 便于回滚后按 id 回写）
mysqldump -u<用户> -p <库名> --no-create-info --replace courses \
  --where="visibility IN ('public','whitelist')" > visibility_bak_<日期>.sql
```

执行回滚：

```bash
.venv\Scripts\python.exe -m alembic downgrade e1f2a3b4c567
```

回滚后按需恢复：

```bash
# 3. 重建白名单表并导入备份
mysql -u<用户> -p <库名> < whitelist_bak_<日期>.sql

# 4. 恢复可见性原值（REPLACE 按 id 回写）
mysql -u<用户> -p <库名> < visibility_bak_<日期>.sql
```

## 开发验证

### 后端自动化测试

Windows 下建议把 pytest 临时目录放到当前用户的本地临时目录，避免历史测试目录权限异常：

```bat
cd backend
mkdir "%LOCALAPPDATA%\Temp\dai-pytest-tmp" 2>nul
set PYTEST_DEBUG_TEMPROOT=%LOCALAPPDATA%\Temp\dai-pytest-tmp
.venv\Scripts\python.exe -m pytest tests\automated -q -p no:cacheprovider
```

当前基线：**1023 项通过、3 项跳过、0 项失败**（2026-08-14，提交 `10f3a58`，
Python 3.12）。精确数字以 CI `backend-test-sqlite` 门禁为准。

### 前端测试与构建

```bash
cd frontend
npm test
npm run build
```

当前基线：**817 项测试全部通过**（2026-08-14，提交 `10f3a58`），生产构建成功。
精确数字以 CI `frontend-test` 门禁为准。

### 仓库清理边界

以下内容属于可重新生成的本地文件，不应提交：

- `frontend/dist/`、`frontend/node_modules/.vite/`；
- `.pytest_cache/`、`__pycache__/`、`*.pyc`；
- `.playwright-mcp/`、测试临时数据库和 `MagicMock/mock.judge_work_dir/` 残留。

以下内容是业务数据或运行状态，即使被 Git 忽略也不得当作缓存清理：

- `backend/storage/`：课程封面、课时视频等上传文件；
- `backend/lesson_content/`：课程讲义和教学内容；
- `judge-work/`：判题与 Kernel 当前工作目录；
- `.env`、`backend/.env`：本地运行配置。

Notebook 前端现统一使用 Studio 和 Experiment 链路；旧版前端 Notebook/Jupyter API 包装已移除，后端兼容接口仍暂时保留。

---

## 技术栈

| 层面 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + Pinia + Vue Router + CodeMirror 6 + Marked |
| 后端 | FastAPI + SQLAlchemy + Alembic + Pydantic |
| 数据库 | MySQL 8.4 |
| 缓存/队列 | Redis 7.4 |
| 判题沙箱 | Docker + pytest |
| 交互实验 | Docker ipykernel（持久化 Kernel Session） |

---

## 项目结构

```text
├── backend/
│   ├── app/
│   │   ├── api/              # 认证、课程、作业、考试、判题、实验、AI 评分等接口
│   │   ├── models/           # SQLAlchemy 数据模型
│   │   ├── schemas/          # Pydantic 请求与响应模型
│   │   ├── services/         # 业务、媒体、环境与 Notebook 服务
│   │   └── worker/           # 判题与环境构建 Worker
│   ├── alembic/              # 数据库迁移
│   ├── docker/
│   │   ├── judge/            # 判题镜像
│   │   └── kernel/           # 交互式 Kernel 镜像
│   ├── lesson_content/       # 课时教学内容（业务数据）
│   ├── storage/              # 封面、视频等上传内容（业务数据）
│   └── tests/automated/      # 后端自动化测试
├── frontend/
│   ├── e2e/                  # Playwright 端到端测试
│   └── src/
│       ├── api/              # Axios API 封装
│       ├── components/       # 公共和业务组件
│       ├── stores/           # Pinia 状态管理
│       ├── utils/            # 工具函数
│       └── views/            # 页面（按角色分目录）
├── docs/                     # 架构和部署运维文档
├── scripts/                  # 验收与演示辅助脚本
├── judge-work/               # 本地判题与 Kernel 运行目录（不提交）
├── docker-compose.yml        # 本地 MySQL 与 Redis
├── docker-compose.prod.yml   # 生产部署编排
└── README.md
```

---

## 角色与权限

| 角色 | 首页 | 主要权限 |
|------|------|----------|
| 学生 `student` | 课程列表 | 选课、学习课时、提交作业、参加考试、进入实验 |
| 教师 `teacher` | 课程管理 | 创建课程/作业/考试、管理题目、查看成绩 |
| 管理员 `admin` | 用户管理 | 创建用户、管理全部资源 |
| 开发者 `developer` | 模板管理 | 管理 Notebook 模板和实验模块 |

---

## 常见问题

### `python` 命令打开 Microsoft Store

用 `py -3` 代替 `python`，或者使用虚拟环境中的 `.venv\Scripts\python.exe`。

### 登录失败

确认管理员账号已创建：
```bash
cd backend
.venv\Scripts\python.exe -m app.cli create-admin --username admin --password Test1234! --real-name Administrator
```

### 提交代码一直是 `queued`

判题 Worker 没启动，另开终端：
```bash
cd backend
.venv\Scripts\python.exe -m app.worker.judge_worker
```

### 前端跨域失败

默认允许 `localhost:5173` 和 `127.0.0.1:5173`。如果前端端口变了，修改 `backend/.env`：
```env
DAI_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

### 前端页面打开白屏

1. 确认 `cd frontend && npm install` 已执行
2. 确认后端 API 在 <http://localhost:8000/api/v1/health/ready> 可访问
3. 打开浏览器控制台查看具体报错

### Docker 未启动

确保 Docker Desktop 在运行，任务栏应有 Docker 图标。Windows 下可能需要以管理员身份运行。
