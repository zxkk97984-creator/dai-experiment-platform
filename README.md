# DAI 实验平台

面向人工智能课程的一站式在线实验平台。支持课程学习、在线编程实验、作业自动判题、考试系统（选择题 + 编程题）和 Notebook 交互式实验。

---

## 快速开始

### 环境要求

- **Docker Desktop**（运行 MySQL、Redis、判题沙箱）
- **Python 3.11+**（后端）
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
.venv\Scripts\python.exe -m app.cli create-admin --username admin --password Passw0rd! --real-name Administrator

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
- 健康检查：<http://localhost:8000/health>

### 6. 默认账号

配置统一密码，登录后按角色进入不同页面。

| 用户名 | 密码 | 角色 | 说明 |
|--------|------|------|------|
| `admin` | `Passw0rd!` | 管理员 | 管理用户、课程和实验模块 |
| `teacher_john` | `Test1234!` | 教师 | 张教授，管理课程与作业 |
| `teacher_li` | `Test1234!` | 教师 | 李老师，管理课程与作业 |
| `student_alice` | `Test1234!` | 学生 | 已选课、已完成部分作业和考试 |
| `student_bob` | `Test1234!` | 学生 | 已选课、部分作业答错 |
| `student_charlie` | `Test1234!` | 学生 | 已选课 |
| `developer_wang` | `Test1234!` | 开发者 | 管理实验模板和模块 |

> 种子数据包含 2 门课程（8 个课时含完整教学内容）、3 个作业（7 道编程题含答案）、2 个考试、2 个实验模块。如果没有种子数据，运行：
> ```bash
> cd backend
> .venv\Scripts\python.exe -m app.seed_data
> ```

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
│   │   ├── api/              # API 路由（auth/users/courses/assignments/judge/exams/experiments/studio）
│   │   ├── models/           # SQLAlchemy 数据模型
│   │   ├── schemas/          # Pydantic 请求/响应模型
│   │   ├── services/         # 业务服务
│   │   └── worker/           # 判题 Worker
│   ├── alembic/              # 数据库迁移
│   ├── docker/
│   │   ├── judge/            # 判题镜像
│   │   └── kernel/           # Kernel 镜像
│   ├── lesson_content/       # 课时教学内容（Markdown）
│   └── tests/                # 后端测试
├── frontend/
│   └── src/
│       ├── api/              # Axios API 封装
│       ├── components/       # 公共组件（CodeBlock、AppLayout 等）
│       ├── stores/           # Pinia 状态管理
│       ├── utils/            # 工具函数
│       └── views/            # 页面（按角色分目录）
├── docker-compose.yml        # MySQL + Redis
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
.venv\Scripts\python.exe -m app.cli create-admin --username admin --password Passw0rd! --real-name Administrator
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
2. 确认后端 API 在 <http://localhost:8000/health> 可访问
3. 打开浏览器控制台查看具体报错

### Docker 未启动

确保 Docker Desktop 在运行，任务栏应有 Docker 图标。Windows 下可能需要以管理员身份运行。
