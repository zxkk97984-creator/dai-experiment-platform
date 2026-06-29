# 人工智能基础实验平台开发

在线 AI 教学实验平台，面向机器学习/深度学习教学场景。支持在线编程判题、JupyterLab 交互式实验、课程管理与作业考试。

## 技术栈

| 层面 | 技术 |
|------|------|
| 前端 | Vue.js |
| 后端 | FastAPI（Python） |
| 数据库 | MySQL + Redis |
| 判题隔离 | Docker |
| 交互实验 | JupyterLab（嵌入式） |

## 项目结构

```
├── backend/          # FastAPI 后端
│   ├── app/
│   │   ├── api/      # API 路由
│   │   ├── models/   # 数据模型
│   │   ├── schemas/  # Pydantic Schema
│   │   ├── services/ # 业务逻辑
│   │   └── worker/   # 判题 Worker
│   └── docker/       # Docker 判题镜像
├── frontend/         # Vue.js 前端
└── docs/             # 文档
```

## 快速开始

### 后端（zxk）

Windows 本机的 `python` 命令可能被 Microsoft Store 别名劫持。本项目统一使用 `py -3` 创建虚拟环境，之后固定使用 `backend\.venv\Scripts\python.exe`。

```bat
cd backend
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

启动 MySQL、Redis、JupyterLab：

```bat
cd ..
docker compose up -d mysql redis jupyter
```

执行数据库迁移并创建管理员账号：

```bat
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m app.cli create-admin --username admin --password Passw0rd! --real-name Administrator
```

启动后端 API：

```bat
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

启动判题 Worker：

```bat
cd backend
docker build -t dai-judge-python:latest docker\judge
.venv\Scripts\python.exe -m app.worker.judge_worker
```

运行测试：

```bat
cd backend
.venv\Scripts\python.exe -m pytest
```

后端启动后访问：

- Swagger：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/health>
- JupyterLab：<http://localhost:8888>

### 前端（wyh）

```bash
cd frontend
npm install
npm run dev
```

## 详细文档

- [架构设计总览](docs/架构设计总览.md)
