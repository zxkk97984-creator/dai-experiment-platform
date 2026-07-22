FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 安装 ipykernel + 常用数学/数据科学库
RUN pip install --no-cache-dir \
    ipykernel \
    numpy \
    pandas \
    scikit-learn \
    matplotlib

# 创建非 root 用户用于执行
RUN useradd --create-home --shell /bin/bash student

# 工作目录和临时目录
RUN mkdir -p /course /work /tmp && chown student:student /work /tmp

USER student
WORKDIR /work
