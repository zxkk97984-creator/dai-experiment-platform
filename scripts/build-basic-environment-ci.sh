#!/usr/bin/env bash
# 构建 basic 环境镜像并回写 image_digest。
#
# 默认模式用于 disposable CI；设置 DAI_BASIC_BUILD_RELEASE=true 后可用于
# 首个发布候选产物。发布模式要求基础镜像使用真实 digest，并且必须选择
# docker save 归档或 Registry 推送目标，避免把本地临时 tag 当成生产证据。
# 分阶段迁移的生产 bootstrap 必须使用真实、已 smoke 的 digest；
# seed-basic-environment-mysql.py 的占位值只允许 disposable smoke。
#
# 前置：compose 栈（mysql 已起）+ 空库两步迁移（迁移 A → seed → head）已完成。
# 用法：在仓库根执行  bash scripts/build-basic-environment-ci.sh
#       （栈的 compose 文件可用 COMPOSE_FILES 覆盖，默认 -f docker-compose.prod.yml）
set -euo pipefail

COMPOSE_FILES="${COMPOSE_FILES:--f docker-compose.prod.yml}"
: "${DAI_DB_ROOT_PASSWORD:?DAI_DB_ROOT_PASSWORD 未设置；请通过环境变量或批准的 .env 注入}"
ROOT_PW="$DAI_DB_ROOT_PASSWORD"
IMAGE_TAG="${DAI_BASIC_IMAGE_TAG:-dai-env-basic:ci}"
RELEASE_MODE="${DAI_BASIC_BUILD_RELEASE:-false}"

if [[ "$RELEASE_MODE" == "true" ]]; then
  if [[ ! "${DAI_ENV_BASE_IMAGE:-}" =~ @sha256:([0-9a-fA-F]{64})$ ]]; then
    echo "发布模式要求 DAI_ENV_BASE_IMAGE 使用真实 @sha256 digest" >&2
    exit 1
  fi
  if [[ "${BASH_REMATCH[1]}" =~ ^0+$ ]]; then
    echo "发布模式拒绝占位基础镜像 digest" >&2
    exit 1
  fi
  if [[ -z "${DAI_BASIC_IMAGE_ARCHIVE:-}" && -z "${DAI_BASIC_IMAGE_REGISTRY_REPOSITORY:-}" ]]; then
    echo "发布模式必须设置 DAI_BASIC_IMAGE_ARCHIVE 或 DAI_BASIC_IMAGE_REGISTRY_REPOSITORY" >&2
    exit 1
  fi
fi

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
    # disposable seed 使用全 0 digest；只对该占位值回退到 tag。
    # 发布候选必须保留真实 digest，确保 Dockerfile 的 FROM 可复现。
    base = v.base_image_ref
    if '@sha256:' in base and base.rsplit('@sha256:', 1)[1].lower() == '0' * 64:
        base = base.split('@', 1)[0]
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
docker build -t "$IMAGE_TAG" "$TMP" >/dev/null
IMG_ID="$(docker inspect --format '{{.Id}}' "$IMAGE_TAG")"
[ -n "$IMG_ID" ] || { echo "无法获取镜像 ID" >&2; exit 1; }

# 3) 在回写数据库前验证镜像确实可启动且平台包可导入。
docker run --rm --network none "$IMAGE_TAG" python -c "import ipykernel, pytest; print('basic image smoke: ok')"

# 4) 可选的可迁移产物：归档用于 docker load，或推送到 Registry 并记录远端 digest。
if [[ -n "${DAI_BASIC_IMAGE_ARCHIVE:-}" ]]; then
  mkdir -p "$(dirname "$DAI_BASIC_IMAGE_ARCHIVE")"
  docker save "$IMAGE_TAG" -o "$DAI_BASIC_IMAGE_ARCHIVE"
  echo "basic 环境镜像归档完成: $DAI_BASIC_IMAGE_ARCHIVE"
fi

if [[ -n "${DAI_BASIC_IMAGE_REGISTRY_REPOSITORY:-}" ]]; then
  REGISTRY_TAG="${DAI_BASIC_IMAGE_REGISTRY_REPOSITORY}:$(printf '%s' "$IMAGE_TAG" | sed 's/.*://')"
  docker tag "$IMAGE_TAG" "$REGISTRY_TAG"
  docker push "$REGISTRY_TAG"
  REMOTE_DIGEST="$(docker inspect --format '{{index .RepoDigests 0}}' "$REGISTRY_TAG" 2>/dev/null || true)"
  echo "basic 环境镜像 Registry 产物: ${REMOTE_DIGEST:-请从 Registry 记录返回的 digest}"
fi

# 5) 回写 digest 与 available 状态（替换 seed 脚本的占位 digest）
docker compose $COMPOSE_FILES exec -T mysql mysql -uroot -p"$ROOT_PW" dai_platform \
  -e "UPDATE environment_versions SET image_digest='${IMG_ID}', status='available' WHERE profile_id=(SELECT id FROM environment_profiles WHERE slug='basic') AND version_number=1;"

echo "basic 环境镜像构建完成: $IMG_ID"
