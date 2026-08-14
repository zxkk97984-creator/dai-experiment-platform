FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    docker-cli \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 默认命令：仅 API 服务（Worker 用 command override）
# 数据库迁移由 Compose 的一次性 migrate 服务执行，API 启动不再跑 Alembic
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
