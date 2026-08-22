#!/usr/bin/env python3
"""幂等 seed：basic 档位 available 版本（带 image_digest）——分阶段迁移用。

迁移 B（c5d6e7f8a901）前置要求：basic 档位存在 available 且带 image_digest 的版本。
生产必须传入已经经过 smoke/备份校验的真实 basic 镜像 digest；没有传入时只允许
非生产烟测使用占位 digest。行存在且一致时跳过；生产遇到状态/digest 冲突会停止，避免覆盖。

用法：DAI_DATABASE_URL=mysql+pymysql://user:pass@host:3306/dai_platform \
      DAI_ENVIRONMENT=production \
      DAI_BASIC_ENVIRONMENT_IMAGE_DIGEST=sha256:<64位hex> \
      python scripts/seed-basic-environment-mysql.py
"""
import os
import re
import sys

import sqlalchemy as sa


_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
_DISPOSABLE_BASIC_IMAGE_DIGEST = "sha256:" + "d" * 64
_PLACEHOLDER_DIGESTS = {
    "sha256:" + "0" * 64,
    "sha256:" + "1" * 64,
}


def is_disposable_digest(image_digest: str) -> bool:
    """Return whether a digest is the explicit non-production seed value."""
    return image_digest == _DISPOSABLE_BASIC_IMAGE_DIGEST


def resolve_image_digest(*, environment: str, raw_digest: str) -> str:
    """Resolve a basic image digest without allowing fake production evidence."""
    normalized_environment = environment.strip().lower()
    image_digest = raw_digest.strip()

    if image_digest and not _DIGEST_RE.fullmatch(image_digest):
        raise ValueError("DAI_BASIC_ENVIRONMENT_IMAGE_DIGEST 必须是 sha256:<64位hex>")

    if not image_digest:
        if normalized_environment == "production":
            raise ValueError(
                "生产分阶段迁移禁止使用占位 digest；请先准备可信 basic 镜像并设置 "
                "DAI_BASIC_ENVIRONMENT_IMAGE_DIGEST"
            )
        return _DISPOSABLE_BASIC_IMAGE_DIGEST

    if image_digest in _PLACEHOLDER_DIGESTS:
        raise ValueError(
            "禁止使用 000... 或 111... 占位 digest；disposable smoke 请省略该变量，"
            "由脚本生成明确的 disposable digest"
        )

    if normalized_environment == "production" and is_disposable_digest(image_digest):
        raise ValueError(
            "生产迁移禁止使用 disposable digest；请提供已经验证的真实 basic 镜像 digest"
        )

    return image_digest


def resolve_migration_environment(*, environment: str, migration_mode: str) -> str:
    """Return the explicit seed mode and reject unsafe mode/environment mixes."""
    normalized_environment = environment.strip().lower()
    normalized_mode = migration_mode.strip().lower()
    if not normalized_mode:
        normalized_mode = "production" if normalized_environment == "production" else "disposable"
    if normalized_mode not in {"production", "disposable"}:
        raise ValueError("DAI_MIGRATION_MODE 必须是 production 或 disposable")
    if normalized_mode == "production" and normalized_environment != "production":
        raise ValueError("production 迁移必须同时设置 DAI_ENVIRONMENT=production")
    if normalized_mode == "disposable" and normalized_environment == "production":
        raise ValueError("production 环境禁止使用 disposable 迁移模式")
    return normalized_mode


def _validate_base_image_ref(*, environment: str, base_image_ref: str) -> str:
    image_ref = base_image_ref.strip()
    if not re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", image_ref):
        raise ValueError("DAI_BASIC_ENVIRONMENT_BASE_IMAGE 必须是带 digest 的镜像引用")
    if environment == "production" and image_ref.rsplit("@", 1)[1] in _PLACEHOLDER_DIGESTS:
        raise ValueError("生产迁移禁止使用 000... 或 111... 基础镜像 digest")
    return image_ref


def seed_basic_environment(
    *,
    database_url: str,
    environment: str,
    raw_digest: str,
    base_image_ref: str,
) -> int:
    """Idempotently seed basic v1 for both MySQL and disposable SQLite databases."""
    normalized_environment = environment.strip().lower()
    image_digest = resolve_image_digest(
        environment=normalized_environment,
        raw_digest=raw_digest,
    )
    image_ref = _validate_base_image_ref(
        environment=normalized_environment,
        base_image_ref=base_image_ref,
    )
    engine = sa.create_engine(database_url)
    try:
        with engine.begin() as conn:
            profile_id = conn.execute(
                sa.text(
                    "SELECT id FROM environment_profiles "
                    "WHERE slug = 'basic' LIMIT 1"
                )
            ).scalar_one_or_none()
            if profile_id is None:
                if conn.dialect.name == "sqlite":
                    profile_id = conn.execute(
                        sa.text("SELECT COALESCE(MAX(id), 0) + 1 FROM environment_profiles")
                    ).scalar_one()
                    conn.execute(
                        sa.text(
                            "INSERT INTO environment_profiles "
                            "(id, slug, display_name, status) "
                            "VALUES (:id, 'basic', 'Basic', 'active')"
                        ),
                        {"id": profile_id},
                    )
                else:
                    result = conn.execute(
                        sa.text(
                            "INSERT INTO environment_profiles "
                            "(slug, display_name, status) "
                            "VALUES ('basic', 'Basic', 'active')"
                        )
                    )
                    profile_id = result.lastrowid
            if profile_id is None:
                raise RuntimeError("无法取得 basic environment_profiles.id")

            row = conn.execute(
                sa.text(
                    "SELECT id, status, image_digest FROM environment_versions "
                    "WHERE profile_id = :profile_id AND version_number = 1 LIMIT 1"
                ),
                {"profile_id": profile_id},
            ).first()
            if row is None:
                values = {
                    "profile_id": profile_id,
                    "base_image_ref": image_ref,
                    "image_digest": image_digest,
                    "manifest_sha256": "c" * 64,
                }
                if conn.dialect.name == "sqlite":
                    values["id"] = conn.execute(
                        sa.text("SELECT COALESCE(MAX(id), 0) + 1 FROM environment_versions")
                    ).scalar_one()
                    conn.execute(
                        sa.text(
                            "INSERT INTO environment_versions "
                            "(id, profile_id, version_number, status, base_image_ref, "
                            " image_digest, python_version, minimum_memory_mb, manifest_sha256) "
                            "VALUES (:id, :profile_id, 1, 'available', :base_image_ref, "
                            " :image_digest, '3.12', 256, :manifest_sha256)"
                        ),
                        values,
                    )
                else:
                    conn.execute(
                        sa.text(
                            "INSERT INTO environment_versions "
                            "(profile_id, version_number, status, base_image_ref, "
                            " image_digest, python_version, minimum_memory_mb, manifest_sha256) "
                            "VALUES (:profile_id, 1, 'available', :base_image_ref, "
                            " :image_digest, '3.12', 256, :manifest_sha256)"
                        ),
                        values,
                    )
            elif row.status != "available" or row.image_digest != image_digest:
                raise RuntimeError(
                    "basic v1 已存在但状态或 digest 与目标不一致；请先人工核对数据库和备份，"
                    "不要静默覆盖既有环境版本"
                )
        return int(profile_id)
    finally:
        engine.dispose()


def main() -> None:
    database_url = os.environ.get("DAI_DATABASE_URL", "")
    if not database_url:
        sys.exit("DAI_DATABASE_URL 未设置")
    environment = os.environ.get("DAI_ENVIRONMENT", "development")
    try:
        migration_mode = resolve_migration_environment(
            environment=environment,
            migration_mode=os.environ.get("DAI_MIGRATION_MODE", ""),
        )
    except ValueError as exc:
        sys.exit(str(exc))
    try:
        profile_id = seed_basic_environment(
            database_url=database_url,
            environment="production" if migration_mode == "production" else "disposable",
            raw_digest=os.environ.get("DAI_BASIC_ENVIRONMENT_IMAGE_DIGEST", ""),
            base_image_ref=os.environ.get(
                "DAI_BASIC_ENVIRONMENT_BASE_IMAGE",
                os.environ.get(
                    "DAI_ENV_BASE_IMAGE",
                    "python:3.12-slim@sha256:" + "0" * 64,
                ),
            ),
        )
        print("basic environment seeded (profile_id=%s)" % profile_id)
    except (RuntimeError, ValueError, sa.exc.SQLAlchemyError) as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
