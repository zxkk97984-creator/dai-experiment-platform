# DAI 实验平台

面向人工智能课程的一站式在线实验平台。支持课程学习、在线编程实验、作业与考试自动判题、AI 辅助评分、Notebook 交互式实验、多档运行环境、课程封面与课时视频上传，以及教师工作台聚合待办、统一提交中心、全局搜索、站内通知、用户偏好与 CSV 名单导入。

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

#### 2.1 一键启动/关闭（Linux/macOS，推荐）

```bash
./scripts/dev-up.sh     # MySQL/Redis → 幂等迁移(alembic upgrade head) → 判题镜像 → API + 判题 Worker + 环境构建 Worker + 前端
./scripts/dev-down.sh   # 停止全部应用进程（含清扫未登记残留）与 MySQL/Redis 容器（数据卷保留，重启不丢数据）
```

脚本幂等：已运行的服务自动跳过；进程 PID 与日志在 `/tmp/dai-dev/`。启动成功后会**自动用默认浏览器打开** `http://localhost:5173`（`DAI_DEV_NO_BROWSER=1` 可关闭）。API 端口被占用时脚本会立即报错并给出换端口指引；前端 vite 代理会**自动跟随** API 端口（无需手动改配置）。

可用环境变量：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DAI_PYTHON` | `backend/.venv/bin/python` | 后端解释器（仓库标准为 Python 3.12 venv） |
| `DAI_DEV_API_PORT` | `8000` | API 监听端口；**本机 8000 被其他项目占用时用 8001**，如 `DAI_DEV_API_PORT=8001 ./scripts/dev-up.sh` |
| `DAI_DEV_RUN_DIR` | `/tmp/dai-dev` | PID/日志目录 |
| `DAI_DEV_NO_BROWSER` | 未设置 | 设为 `1` 时启动成功后不自动打开浏览器 |

首次使用前需初始化后端环境（见下节；`uv venv backend/.venv --python 3.12` + `uv pip install -r backend/requirements.txt`）。

### 3. 初始化后端

Windows（PowerShell / cmd）：

```bash
cd backend

# 创建虚拟环境
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Linux/macOS（Python 3.12，与 CI/Dockerfile 基线一致；仓库含 `backend/.python-version`）：

```bash
cd backend
uv venv .venv --python 3.12        # 或 python3.12 -m venv .venv
uv pip install -r requirements.txt
```

两种环境通用的后续步骤：

```bash
# 配置环境变量
copy .env.example .env             # Windows
# cp .env.example .env             # Linux/macOS

# 数据库迁移（开发库跟随最新 head；生产用 docker-compose.prod.yml 的 migrate 服务）
.venv\Scripts\python.exe -m alembic upgrade head   # Windows
# .venv/bin/python -m alembic upgrade head          # Linux/macOS

# 创建管理员账号
.venv\Scripts\python.exe -m app.cli create-admin --username admin --password Test1234! --real-name Administrator

# 构建判题镜像（仅首次需要）
docker build -t dai-judge-python:latest docker\judge
docker build -t dai-kernel-python:latest docker\kernel
```

> 注意：TASK-016 后 API 启动不再自动执行 Alembic 迁移。手动启动时务必先
> `alembic upgrade head`（`dev-up.sh` 已自动包含此步骤）。

### 4. 启动后端服务

需要打开三个终端窗口（Windows 示例；Linux/macOS 把 `.venv\Scripts\` 换成 `.venv/bin/`，或用 `scripts/dev-up.sh` 一键启动）：

```bash
# 终端 1：后端 API
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# 8000 被占用时（如本机同时跑其他项目）：API 改 --port 8001，
# 前端启动时加 VITE_API_PROXY_TARGET=http://localhost:8001

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

---

### 6. Demo 演示数据（可选）

一键生成一套真实、可重复的演示数据（固定账号 / 课程 / 作业 / 考试 / AI 评分 / 实验全链路 / 白名单权限）：

```bash
cd backend
.venv/bin/python -m alembic upgrade head   # 1. 迁移（dev 库为空时必须）
# 2. 环境：basic 档位需 available（详见 docs/demo-data.md）
.venv/bin/python -m app.cli seed-demo      # 3. 播种（幂等）
.venv/bin/python -m app.cli seed-demo --reset-demo   # 重建：仅清 Demo 数据再播种
```

固定演示账号（密码 `Demo1234!`，`DAI_DEMO_PASSWORD` 可覆盖）：

| 角色 | 用户名 |
|---|---|
| 管理员 | `demo_admin` |
| 教师 | `teacher_zhang` / `teacher_chen` / `teacher_zhao` |
| 学生 | `demo_student_elite` / `demo_student_average` / `demo_student_struggling` / `demo_student_new` |
| 开发者 | `demo_developer` |

详细说明（前置条件 / 故事线 / 数据规模 / 验证结果）见 [docs/demo-data.md](docs/demo-data.md)。

---

## 教师端工作台与数据运维

### 教师端能力

- 教师工作台 `/teacher`：聚合待评分/待复核/临期任务、最近提交表格与课程公告
- 统一提交中心 `/teacher/submissions/unified`：实验 / 作业 / 考试提交合并检索
- 全局搜索：顶部 `⌘K / Ctrl+K`，搜索课程 / 作业 / 考试 / 学生 / 提交
- 班级与学员 `/teacher/classes`：仅展示教师自己课程关联的教学班与名单
- 成绩统计 `/teacher/grades`：跨课程考试成绩总览
- 运行环境 `/teacher/environments`：教师只读查看可用环境档位
- 通知中心 `/teacher/notifications`：待办与公告通知，已读状态落库
- 设置 `/teacher/settings`：个人资料、密码、侧栏偏好（后端持久化）
- 课程名单 CSV 导入：课程设置 → 学生名单 → 导入 CSV，支持 UTF-8 / GB18030
- 作业 / 考试任务级发布范围：课程全部学生、指定多个教学班、仅白名单，可追加白名单与排除名单（白名单学生无需提前选课），支持手动选择与 CSV 导入

### 教师工作台迁移与回填

教师工作台 V3 相关迁移由 `alembic upgrade head` 一并执行，包含：

- `13697fb5ecbf`：院系、课程编号、实验截止、测试通过数、待办索引
- `20260816_0001`：通知表、通知已读回执、用户偏好表
- `936ca2d19666`：作业 / 考试发布范围关系表与 `audience_mode`

升级后如需补齐历史提交的测试通过数，执行：

```bash
cd backend
.venv/bin/python ../scripts/backfill_test_counts.py --dry-run   # 预览
.venv/bin/python ../scripts/backfill_test_counts.py             # 回填
```

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
# 环境变量（必填；缺任何一项 compose 都会在启动前校验失败）
export DAI_SECRET_KEY=<至少16字符的唯一密钥>
export DAI_CORS_ORIGINS=https://your-domain.com
export DAI_DB_PASSWORD=<数据库密码>
export DAI_DB_ROOT_PASSWORD=<数据库 root 密码>
export DAI_JUDGE_HOST_WORK_DIR=/opt/dai/judge-work   # 宿主机判题工作目录绝对路径
export DAI_ENV_BASE_IMAGE=python:3.12-slim@sha256:<真实digest>  # 环境构建基础镜像，必须带 digest

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

当前基线：**1042 项通过、3 项跳过、0 项失败**（2026-08-15，SQLite 外键开启下
实测，Python 3.12；清理内测/验收种子测试后）。精确数字以 CI
`backend-test-sqlite` 门禁为准。
MySQL 门禁（`backend-test-mysql`）与 SQLite 同套件跑双库，双库 0 失败才算过。

### 前端测试与构建

```bash
cd frontend
npm test
npm run build
```

当前基线：**825 项测试全部通过**（2026-08-15），生产构建成功；测试已改为
时区无关断言，UTC 机器（CI）与本地时区均可通过。精确数字以 CI `frontend-test` 门禁为准。

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
| 数据库 | MySQL 8.0（生产/CI）；8.4 亦经本地开发验证 |
| 缓存/队列 | Redis 7 |
| 判题沙箱 | Docker + pytest（经环境版本 digest 冻结镜像） |
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
├── scripts/                  # 开发/CI/E2E 辅助脚本（dev-up/down、环境镜像构建、验收种子等）
├── judge-work/               # 本地判题与 Kernel 运行目录（不提交）
├── docker-compose.yml        # 本地 MySQL 与 Redis
├── docker-compose.prod.yml   # 生产部署编排
└── README.md
```

---

## 角色与权限

| 角色 | 首页 | 主要权限 |
|------|------|----------|
| 学生 `student` | 学生首页 Dashboard（`/student`，含课程列表入口） | 选课、学习课时、提交作业、参加考试、进入实验 |
| 教师 `teacher` | 工作台 | 课程/作业/实验/考试管理、统一提交评分、AI 复核、成绩统计、班级与学员、运行环境、设置 |
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

### 8000 端口被占用（后端起不来）

本机 8000 已被其他程序占用时，一键脚本会在启动前直接报错并给出指引；手动启动则 uvicorn 会报 `address already in use`。处理方式：

```bash
# 方式一（推荐）：一键脚本用 8001，vite 代理自动跟随
DAI_DEV_API_PORT=8001 ./scripts/dev-up.sh

# 方式二：手动启动时同步改两个端口
.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
VITE_API_PROXY_TARGET=http://localhost:8001 npm run dev   # 前端代理必须指向新端口
```

> 注意：`backend/.env` 的 `DAI_CORS_ORIGINS` 配置的是浏览器来源（`localhost:5173`），
> 与 API 端口无关，换端口**不需要**改 CORS。