#!/usr/bin/env python3
"""幂等 seed：basic 档位 available 版本（带 image_digest）——空库全新部署用。

迁移 B（c5d6e7f8a901）前置要求：basic 档位存在 available 且带 image_digest 的版本。
正常部署中该行由「迁移 A 部署 → seed-environments --enqueue → 环境构建 Worker 完成
basic v1 构建并回写 available 状态」产生；本脚本模拟该结果，供空库烟测/一次性
初始化使用（行存在时跳过，幂等）。

用法：DAI_DATABASE_URL=mysql+pymysql://user:pass@host:3306/dai_platform \
      python scripts/seed-basic-environment-mysql.py
"""
import os
import sys
from urllib.parse import unquote, urlparse

import pymysql


def main() -> None:
    raw = os.environ.get("DAI_DATABASE_URL", "")
    if not raw:
        sys.exit("DAI_DATABASE_URL 未设置")
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
                "SELECT id FROM environment_versions"
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
                    "         CONCAT('python:3.12-slim@sha256:', REPEAT('0', 64)),"
                    "         CONCAT('sha256:', REPEAT('1', 64)),"
                    "         '3.12', 256, REPEAT('c', 64), NOW())",
                    (profile_id,),
                )
        conn.commit()
        print("basic environment seeded (profile_id=%s)" % profile_id)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
