#!/usr/bin/env bash
# CI e2e 专用：构建 basic 环境镜像并回写 image_digest。
# 分阶段迁移的生产 bootstrap 必须使用真实、已 smoke 的 digest；
# seed-basic-environment-mysql.py 的占位值只允许 disposable smoke。
#
# 前置：compose 栈（mysql 已起）+ 空库两步迁移（迁移 A → seed → head）已完成。
# 用法：在仓库根执行  bash scripts/build-basic-environment-ci.sh
#       （栈的 compose 文件可用 COMPOSE_FILES 覆盖，默认 -f docker-compose.prod.yml）
set -euo pipefail

COMPOSE_FILES="${COMPOSE_FILES:--f docker-compose.prod.yml}"
ROOT_PW="${DAI_DB_ROOT_PASSWORD:-root_secret}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# 1) 用栈内 migrate 容器（含应用代码与依赖）渲染 basic 环境 Dockerfile 与 kernel_runner.py
docker compose $COMPOSE_FILES run --rm migrate python -c "
from app.config import get_settings
from app.database import SessionLocal
from app.models import EnvironmentVersion
from app.services.environment_builder import canonical_build_spec, render_dockerfile
from sqlalchemy import select
with SessionLocal() as db:
    v = db.scalar(select(EnvironmentVersion).order_by(EnvironmentVersion.id).limit(1))
    # seed 脚本写入的 base_image_ref 带占位假 digest（sha256:000...），
    # 构建必须剥掉 digest 用可拉取的真实基础镜像。
    base = v.base_image_ref.split('@')[0]
    spec = canonical_build_spec(base, 'basic', 1, [], get_settings())
    print('===DAI-DOCKERFILE===')
    print(render_dockerfile(spec))
    print('===DAI-KERNEL-RUNNER===')
    print(spec.kernel_runner_source)
" > "$TMP/combined.txt"

sed -n '/===DAI-DOCKERFILE===/,/===DAI-KERNEL-RUNNER===/{/===DAI-/d;p}' "$TMP/combined.txt" > "$TMP/Dockerfile"
sed -n '/===DAI-KERNEL-RUNNER===/,$p' "$TMP/combined.txt" | sed '1d' > "$TMP/kernel_runner.py"
test -s "$TMP/Dockerfile"
test -s "$TMP/kernel_runner.py"

# 2) 构建镜像并捕获 image ID（单机 digest 语义：运行链路直接以 image ID 启动）
docker build -t dai-env-basic:ci "$TMP" >/dev/null
IMG_ID="$(docker inspect --format '{{.Id}}' dai-env-basic:ci)"
[ -n "$IMG_ID" ] || { echo "无法获取镜像 ID" >&2; exit 1; }

# 3) 回写 digest 与 available 状态（替换 seed 脚本的占位 digest）
docker compose $COMPOSE_FILES exec -T mysql mysql -uroot -p"$ROOT_PW" dai_platform \
  -e "UPDATE environment_versions SET image_digest='${IMG_ID}', status='available' WHERE profile_id=(SELECT id FROM environment_profiles WHERE slug='basic') AND version_number=1;"

echo "basic 环境镜像构建完成: $IMG_ID"
