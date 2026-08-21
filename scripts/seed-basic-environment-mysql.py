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
from urllib.parse import unquote, urlparse

import pymysql


def main() -> None:
    raw = os.environ.get("DAI_DATABASE_URL", "")
    if not raw:
        sys.exit("DAI_DATABASE_URL 未设置")
    image_digest = os.environ.get("DAI_BASIC_ENVIRONMENT_IMAGE_DIGEST", "").strip()
    if image_digest and not re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest):
        sys.exit("DAI_BASIC_ENVIRONMENT_IMAGE_DIGEST 必须是 sha256:<64位hex>")
    if os.environ.get("DAI_ENVIRONMENT", "development") == "production" and not image_digest:
        sys.exit(
            "生产分阶段迁移禁止使用占位 digest；请先准备可信 basic 镜像并设置 "
            "DAI_BASIC_ENVIRONMENT_IMAGE_DIGEST"
        )
    image_digest = image_digest or ("sha256:" + "1" * 64)
    base_image_ref = os.environ.get(
        "DAI_BASIC_ENVIRONMENT_BASE_IMAGE",
        "python:3.12-slim@sha256:" + "0" * 64,
    ).strip()
    if not re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", base_image_ref):
        sys.exit("DAI_BASIC_ENVIRONMENT_BASE_IMAGE 必须是带 digest 的镜像引用")
    url = urlparse(raw)
    conn = pymysql.connect(
        host=url.hostname,
        port=url.port or 3306,
        user=unquote(url.username or ""),
        password=unquote(url.password or ""),
        database=url.path.lstrip("/"),
        autocommit=False,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM environment_profiles WHERE slug='basic' LIMIT 1"
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "INSERT INTO environment_profiles (slug, display_name, status)"
                    " VALUES ('basic', 'Basic', 'active')"
                )
                profile_id = cur.lastrowid
            else:
                profile_id = row[0]
            cur.execute(
                "SELECT id, status, image_digest FROM environment_versions"
                " WHERE profile_id=%s AND version_number=1 LIMIT 1",
                (profile_id,),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "INSERT INTO environment_versions"
                    " (profile_id, version_number, status, base_image_ref,"
                    "  image_digest, python_version, minimum_memory_mb,"
                    "  manifest_sha256, available_at)"
                    " VALUES (%s, 1, 'available',"
                    "         %s, %s, '3.12', 256, REPEAT('c', 64), NOW())",
                    (profile_id, base_image_ref, image_digest),
                )
            elif (
                os.environ.get("DAI_ENVIRONMENT", "development") == "production"
                and (row[1] != "available" or row[2] != image_digest)
            ):
                sys.exit(
                    "basic v1 已存在但状态或 digest 与目标不一致；请先人工核对数据库和备份，"
                    "不要静默覆盖既有环境版本"
                )
        conn.commit()
        print("basic environment seeded (profile_id=%s)" % profile_id)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
