FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    docker-cli \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 默认命令：API 服务（Worker/migrate 用 command override）。
# TASK-016：API 不再内嵌 alembic——迁移由 compose 的一次性 migrate 服务执行
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
