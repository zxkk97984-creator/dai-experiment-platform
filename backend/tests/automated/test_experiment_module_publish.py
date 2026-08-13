"""实验模块强类型与内部模板发布契约测试（TASK-008 / F-04 / F-05 / R-02）。

- 创建强制 draft；非法状态/未知字段（含 entry_url）422
- PATCH 强类型：拒绝裸 dict/status/未知字段
- 发布门禁：绑定模板 → 模板已发布版本 → 版本绑定运行环境
- 角色可见性：学生只看 published，Developer 只看自己的模块
"""
import pytest
from conftest import auth_header, create_user, login

from app.models import (
    EnvironmentProfile,
    EnvironmentVersion,
    ExperimentModule,
    NotebookTemplate,
    NotebookTemplateVersion,
)

API = "/api/v1"


def _user(client, db_session_factory, username, role):
    create_user(db_session_factory, username, role)
    token, _ = login(client, username)
    return token


def _env_version(db_session_factory, owner_id):
    """available 环境版本（带 digest，可绑定到模板版本）。

    digest 使用 'c'*64——conftest 预置的 basic 版本占用 'b'*64
    （image_digest 有唯一约束，TASK-010）。
    """
    with db_session_factory() as db:
        profile = EnvironmentProfile(slug=f"mp-{owner_id}", display_name="发布测试档位", status="active")
        db.add(profile)
        db.flush()
        version = EnvironmentVersion(
            profile_id=profile.id,
            version_number=1,
            base_image_ref="python:3.12-slim",
            minimum_memory_mb=128,
            manifest_sha256="a" * 64,
            status="available",
            image_digest="sha256:" + "c" * 64,
            created_by_id=owner_id,
        )
        db.add(version)
        db.commit()
        return version.id


def _template(db_session_factory, owner_id, env_version_id=None, publish=True):
    """创建模板；publish=True 时同时发布当前版本（可选绑定环境）。"""
    with db_session_factory() as db:
        template = NotebookTemplate(name=f"模板-{owner_id}", status="draft", owner_id=owner_id)
        db.add(template)
        db.flush()
        version = NotebookTemplateVersion(
            template_id=template.id,
            version_number=1,
            sha256="c" * 64,
            cells=[],
            cell_order=[],
            published_by_id=owner_id,
            environment_version_id=env_version_id,
        )
        db.add(version)
        db.flush()
        if publish:
            template.status = "published"
            template.current_version_id = version.id
        db.commit()
        return template.id


def _create(client, token, **payload):
    resp = client.post(f"{API}/experiments/modules", headers=auth_header(token), json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── 创建契约 ───────────────────────────────────────────────────


def test_create_with_published_status_rejected(client, db_session_factory):
    token = _user(client, db_session_factory, "mp-creator", "developer")
    response = client.post(
        f"{API}/experiments/modules", headers=auth_header(token),
        json={"name": "旁路模块", "status": "published"},
    )
    assert response.status_code == 422, response.text


def test_create_with_entry_url_rejected(client, db_session_factory):
    """R-02：entry_url 已从契约移除——提交即 422，不再静默丢弃。"""
    token = _user(client, db_session_factory, "mp-creator2", "developer")
    response = client.post(
        f"{API}/experiments/modules", headers=auth_header(token),
        json={"name": "外部入口模块", "entry_url": "https://example.com/lab"},
    )
    assert response.status_code == 422, response.text


def test_create_with_unknown_field_rejected(client, db_session_factory):
    token = _user(client, db_session_factory, "mp-creator3", "developer")
    response = client.post(
        f"{API}/experiments/modules", headers=auth_header(token),
        json={"name": "未知字段", "owner_id": 9999},
    )
    assert response.status_code == 422, response.text


# ── 更新契约 ───────────────────────────────────────────────────


def test_patch_cannot_write_status(client, db_session_factory):
    token = _user(client, db_session_factory, "mp-patch", "developer")
    module = _create(client, token, name="状态保护模块")
    response = client.patch(
        f"{API}/experiments/modules/{module['id']}", headers=auth_header(token),
        json={"status": "published"},
    )
    assert response.status_code == 422, response.text


def test_patch_rejects_unknown_field(client, db_session_factory):
    token = _user(client, db_session_factory, "mp-patch2", "developer")
    module = _create(client, token, name="未知字段保护")
    response = client.patch(
        f"{API}/experiments/modules/{module['id']}", headers=auth_header(token),
        json={"entry_url": "https://example.com/lab"},
    )
    assert response.status_code == 422, response.text


# ── 发布门禁 ───────────────────────────────────────────────────


def test_publish_without_template_rejected(client, db_session_factory):
    token = _user(client, db_session_factory, "mp-no-tpl", "developer")
    module = _create(client, token, name="无模板模块")
    response = client.post(
        f"{API}/experiments/modules/{module['id']}/publish", headers=auth_header(token),
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "MODULE_TEMPLATE_MISSING"


def test_publish_with_unpublished_template_rejected(client, db_session_factory):
    token = _user(client, db_session_factory, "mp-no-ver", "developer")
    template_id = _template(db_session_factory, 1, publish=False)
    module = _create(client, token, name="模板未发布", template_id=template_id)
    response = client.post(
        f"{API}/experiments/modules/{module['id']}/publish", headers=auth_header(token),
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "MODULE_VERSION_MISSING"


def test_publish_without_explicit_env_binds_basic_available(client, db_session_factory):
    """TASK-010 后模板版本环境列 NOT NULL + 默认绑定 basic 可用版本——
    未显式指定环境的模板发布时自动绑定 basic（MODULE_ENV_MISSING 门禁保留为纵深防御）。"""
    token = _user(client, db_session_factory, "mp-no-env", "developer")
    template_id = _template(db_session_factory, 1, env_version_id=None)
    module = _create(client, token, name="环境缺失", template_id=template_id)
    response = client.post(
        f"{API}/experiments/modules/{module['id']}/publish", headers=auth_header(token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "published"


def test_publish_and_unpublish_roundtrip(client, db_session_factory):
    token = _user(client, db_session_factory, "mp-ok", "developer")
    env_id = _env_version(db_session_factory, 1)
    template_id = _template(db_session_factory, 1, env_version_id=env_id)
    module = _create(client, token, name="完整模块", template_id=template_id)

    publish = client.post(
        f"{API}/experiments/modules/{module['id']}/publish", headers=auth_header(token),
    )
    assert publish.status_code == 200, publish.text
    assert publish.json()["status"] == "published"

    # 重复发布幂等
    again = client.post(
        f"{API}/experiments/modules/{module['id']}/publish", headers=auth_header(token),
    )
    assert again.status_code == 200, again.text

    unpublish = client.post(
        f"{API}/experiments/modules/{module['id']}/unpublish", headers=auth_header(token),
    )
    assert unpublish.status_code == 200, unpublish.text
    assert unpublish.json()["status"] == "draft"

    # 下架 draft 再下架 → 409
    double = client.post(
        f"{API}/experiments/modules/{module['id']}/unpublish", headers=auth_header(token),
    )
    assert double.status_code == 409, double.text
    assert double.json()["detail"]["code"] == "MODULE_NOT_PUBLISHED"


# ── 角色可见性 ─────────────────────────────────────────────────


def test_developer_cannot_view_other_developers_module(client, db_session_factory):
    """F-05：Developer 详情权限与列表规则一致——只能看自己的模块。"""
    dev_a = _user(client, db_session_factory, "mp-dev-a", "developer")
    dev_b = _user(client, db_session_factory, "mp-dev-b", "developer")
    module = _create(client, dev_a, name="A 的模块")
    detail = client.get(f"{API}/experiments/modules/{module['id']}", headers=auth_header(dev_b))
    assert detail.status_code == 403, detail.text
    own = client.get(f"{API}/experiments/modules/{module['id']}", headers=auth_header(dev_a))
    assert own.status_code == 200, own.text


def test_student_only_sees_published(client, db_session_factory):
    """学生目录只含 published 模块。"""
    dev = _user(client, db_session_factory, "mp-dev-c", "developer")
    student = _user(client, db_session_factory, "mp-stu", "student")
    env_id = _env_version(db_session_factory, 1)
    template_id = _template(db_session_factory, 1, env_version_id=env_id)

    draft_module = _create(client, dev, name="草稿模块", template_id=template_id)
    published_module = _create(client, dev, name="已发布模块", template_id=template_id)
    client.post(
        f"{API}/experiments/modules/{published_module['id']}/publish",
        headers=auth_header(dev),
    )

    listing = client.get(f"{API}/experiments/modules", headers=auth_header(student))
    assert listing.status_code == 200, listing.text
    ids = [item["id"] for item in listing.json()["items"]]
    assert published_module["id"] in ids
    assert draft_module["id"] not in ids

    detail = client.get(
        f"{API}/experiments/modules/{draft_module['id']}", headers=auth_header(student)
    )
    assert detail.status_code == 403, detail.text
