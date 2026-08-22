"""Phase 5 legacy endpoint and dead-client-surface regressions."""

from pathlib import Path

from conftest import auth_header, create_user, login


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_legacy_jupyter_template_endpoints_are_explicitly_retired(client, db_session_factory):
    create_user(db_session_factory, "legacy-jupyter-student", "student")
    token, _ = login(client, "legacy-jupyter-student")
    headers = auth_header(token)

    templates = client.get("/api/v1/jupyter/templates", headers=headers)
    copied = client.post("/api/v1/jupyter/templates/intro-ml/copy", headers=headers)

    assert templates.status_code == 410
    assert templates.json()["detail"]["code"] == "JUPYTER_TEMPLATES_RETIRED"
    assert copied.status_code == 410
    assert copied.json()["detail"]["code"] == "JUPYTER_TEMPLATES_RETIRED"


def test_legacy_notebooks_routes_are_retired_with_migration_hint(client, db_session_factory):
    create_user(db_session_factory, "legacy-notebook-student", "student")
    token, _ = login(client, "legacy-notebook-student")

    response = client.get("/api/v1/notebooks/123", headers=auth_header(token))

    assert response.status_code == 410
    assert response.headers.get("Deprecation") == "true"
    assert response.json()["detail"]["code"] == "DEPRECATED"


def test_exam_client_exposes_only_supported_delete_operations():
    content = (REPO_ROOT / "frontend/src/api/exams.js").read_text(encoding="utf-8")

    assert "delete(id)" not in content
    assert "deleteQuestion(examId, qId)" in content


def test_removed_notebook_compatibility_schemas_have_no_runtime_references():
    schemas = (REPO_ROOT / "backend/app/schemas/__init__.py").read_text(encoding="utf-8")

    for name in (
        "NotebookCopyResponse",
        "JupyterTemplateRead",
        "NotebookCellOut",
        "NotebookResponse",
        "NotebookCellsSaveRequest",
        "NotebookSaveResponse",
    ):
        assert f"class {name}" not in schemas


def test_production_evidence_checklist_keeps_external_gates_unverified():
    checklist = (REPO_ROOT / "docs/production-evidence-checklist.md").read_text(encoding="utf-8")

    for gate in ("备份恢复", "TLS", "Docker 主机", "Registry", "容量", "AI 数据治理"):
        assert gate in checklist
    assert "待部署方" in checklist
    assert "不能替代" in checklist


def test_current_docs_describe_retired_notebooks_and_split_workers():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    architecture = (REPO_ROOT / "docs/架构设计总览.md").read_text(encoding="utf-8")

    assert "JUPYTER_TEMPLATES_RETIRED" in readme
    assert "进程内转发" not in readme
    assert "AI worker" in architecture
    assert "消费作业、考试和 AI 评分队列" not in architecture
