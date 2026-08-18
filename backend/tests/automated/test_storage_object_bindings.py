"""Phase 2B: Course Cover / Lesson Video 与 StorageObject 的绑定回归测试。"""

from __future__ import annotations

import hashlib
from io import BytesIO

from app import models
from app.services.storage_object_service import StorageIntegrityStatus, StorageObjectService
from app.storage import StorageArea, StorageService
from conftest import auth_header, create_course_db, create_user, login


API = "/api/v1"


def _png_bytes(size: int = 200) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"x" * max(0, size - 8)


def _mp4_bytes(size: int = 200) -> bytes:
    head = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2mp41"
    return head + b"x" * max(0, size - len(head))


def _cover_context(client, db_session_factory, *, tag: str = "phase2b-cover"):
    teacher = create_user(db_session_factory, f"{tag}-teacher", "teacher")
    token = login(client, f"{tag}-teacher")[0]
    course_id = create_course_db(
        db_session_factory,
        teacher_username=f"{tag}-teacher",
        title="Phase 2B cover",
        status="published",
        visibility="public",
    )
    return teacher, token, course_id


def _video_context(client, db_session_factory, *, tag: str = "phase2b-video"):
    teacher = create_user(db_session_factory, f"{tag}-teacher", "teacher")
    token = login(client, f"{tag}-teacher")[0]
    course_id = create_course_db(
        db_session_factory,
        teacher_username=f"{tag}-teacher",
        title="Phase 2B video",
        status="published",
        visibility="public",
    )
    chapter = client.post(
        f"{API}/courses/{course_id}/chapters",
        headers=auth_header(token),
        json={"title": "Videos"},
    )
    lesson = client.post(
        f"{API}/chapters/{chapter.json()['id']}/lessons",
        headers=auth_header(token),
        json={
            "title": "Phase 2B video",
            "content_type": "video",
            "video_url": "https://legacy.example/video.mp4",
        },
    )
    return teacher, token, course_id, lesson.json()["id"]


def test_new_cover_upload_registers_active_object_and_matches_physical_file(
    client, db_session_factory, test_settings
):
    teacher, token, course_id = _cover_context(client, db_session_factory)
    response = client.put(
        f"{API}/courses/{course_id}/cover",
        headers=auth_header(token),
        files={"file": ("cover.png", _png_bytes(257), "image/png")},
    )
    assert response.status_code == 200, response.text
    key = response.json()["cover"]

    with db_session_factory() as db:
        course = db.get(models.Course, course_id)
        assert course.cover_object_id is not None
        obj = db.get(models.StorageObject, course.cover_object_id)
        assert obj is not None
        assert obj.status == models.StorageObjectStatus.ACTIVE.value
        assert obj.namespace == "course-covers"
        assert obj.object_key == key
        assert obj.content_type == "image/png"
        assert obj.size_bytes == 257
        assert obj.created_by_id == teacher.id

        report = StorageObjectService(db, StorageService.from_settings(test_settings)).check_integrity(
            obj.id,
            area=StorageArea.COVERS,
            verify_sha256=True,
        )
        assert report.status == StorageIntegrityStatus.OK.value
        assert report.actual_size == 257
        assert report.actual_sha256 == hashlib.sha256(_png_bytes(257)).hexdigest()


def test_failed_binding_transaction_does_not_leave_metadata_row(db_session_factory, test_settings):
    with db_session_factory() as db:
        service = StorageObjectService(db, StorageService.from_settings(test_settings))
        obj = service.create_staging(
            namespace="course-covers",
            object_key="covers/rollback/cover.png",
            size_bytes=1,
        )
        service.activate(obj.id, size_bytes=1)
        db.rollback()

    with db_session_factory() as db:
        assert db.query(models.StorageObject).count() == 0


def test_legacy_data_uri_cover_stays_untouched_and_unbound(client, db_session_factory):
    create_user(db_session_factory, "legacy-cover-teacher", "teacher")
    token = login(client, "legacy-cover-teacher")[0]
    course_id = create_course_db(
        db_session_factory,
        teacher_username="legacy-cover-teacher",
        title="Legacy cover",
        status="published",
        visibility="public",
        cover="data:image/png;base64,AAAA",
    )

    response = client.get(f"{API}/courses/{course_id}", headers=auth_header(token))
    assert response.status_code == 200, response.text
    assert response.json()["cover"] == "data:image/png;base64,AAAA"
    with db_session_factory() as db:
        course = db.get(models.Course, course_id)
        assert course.cover_object_id is None
        assert db.query(models.StorageObject).count() == 0


def test_direct_legacy_cover_edit_detaches_and_retires_new_object(
    client, db_session_factory, test_settings
):
    _, token, course_id = _cover_context(client, db_session_factory, tag="phase2b-cover-edit")
    uploaded = client.put(
        f"{API}/courses/{course_id}/cover",
        headers=auth_header(token),
        files={"file": ("cover.png", _png_bytes(120), "image/png")},
    )
    assert uploaded.status_code == 200
    old_key = uploaded.json()["cover"]

    edited = client.patch(
        f"{API}/courses/{course_id}",
        headers=auth_header(token),
        json={"cover": "data:image/png;base64,AAAA"},
    )
    assert edited.status_code == 200, edited.text
    with db_session_factory() as db:
        course = db.get(models.Course, course_id)
        assert course.cover == "data:image/png;base64,AAAA"
        assert course.cover_object_id is None
        obj = db.query(models.StorageObject).filter_by(object_key=old_key).one()
        assert obj.status == models.StorageObjectStatus.DELETED.value
    assert not StorageService.from_settings(test_settings).exists(StorageArea.COVERS, old_key)


def test_cover_replacement_deletes_old_object_only_after_new_binding(
    client, db_session_factory, test_settings
):
    _, token, course_id = _cover_context(client, db_session_factory, tag="phase2b-cover-replace")
    first = client.put(
        f"{API}/courses/{course_id}/cover",
        headers=auth_header(token),
        files={"file": ("first.png", _png_bytes(100), "image/png")},
    )
    second = client.put(
        f"{API}/courses/{course_id}/cover",
        headers=auth_header(token),
        files={"file": ("second.png", _png_bytes(110), "image/png")},
    )
    assert first.status_code == second.status_code == 200
    first_key = first.json()["cover"]
    second_key = second.json()["cover"]
    assert first_key != second_key

    with db_session_factory() as db:
        objects = db.query(models.StorageObject).order_by(models.StorageObject.id).all()
        assert len(objects) == 2
        assert objects[0].object_key == first_key
        assert objects[0].status == models.StorageObjectStatus.DELETED.value
        assert objects[0].deleted_at is not None
        assert objects[1].object_key == second_key
        assert objects[1].status == models.StorageObjectStatus.ACTIVE.value
    assert not StorageService.from_settings(test_settings).exists(StorageArea.COVERS, first_key)


def test_failed_cover_replacement_keeps_old_binding_and_object(
    client, app, db_session_factory, test_settings, monkeypatch
):
    _, token, course_id = _cover_context(client, db_session_factory, tag="phase2b-cover-fail")
    first = client.put(
        f"{API}/courses/{course_id}/cover",
        headers=auth_header(token),
        files={"file": ("first.png", _png_bytes(100), "image/png")},
    )
    assert first.status_code == 200
    first_key = first.json()["cover"]

    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session as ORMSession

    def fail_commit(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(ORMSession, "commit", fail_commit)
    quiet_client = TestClient(app, raise_server_exceptions=False)
    failed = quiet_client.put(
        f"{API}/courses/{course_id}/cover",
        headers=auth_header(token),
        files={"file": ("second.png", _png_bytes(110), "image/png")},
    )
    assert failed.status_code == 500

    with db_session_factory() as db:
        course = db.get(models.Course, course_id)
        assert course.cover == first_key
        objects = db.query(models.StorageObject).all()
        assert [(item.object_key, item.status) for item in objects] == [(first_key, "active")]
        old = objects[0]
        assert old.status == models.StorageObjectStatus.ACTIVE.value
        assert course.cover_object_id == old.id
    assert StorageService.from_settings(test_settings).exists(StorageArea.COVERS, first_key)


def test_new_video_upload_registers_object_and_external_switch_deletes_it(
    client, db_session_factory, test_settings
):
    teacher, token, _, lesson_id = _video_context(client, db_session_factory)
    upload = client.put(
        f"{API}/lessons/{lesson_id}/video-file",
        headers=auth_header(token),
        files={"file": ("lesson.mp4", _mp4_bytes(311), "video/mp4")},
    )
    assert upload.status_code == 200, upload.text
    # The public LessonRead contract intentionally does not expose the storage key.
    with db_session_factory() as db:
        lesson = db.get(models.Lesson, lesson_id)
        assert lesson.video_object_id is not None
        key = lesson.video_storage_key
        obj = db.get(models.StorageObject, lesson.video_object_id)
        assert obj is not None
        assert obj.status == models.StorageObjectStatus.ACTIVE.value
        assert obj.namespace == "lesson-videos"
        assert obj.object_key == key
        assert obj.content_type == "video/mp4"
        assert obj.size_bytes == 311
        assert obj.created_by_id == teacher.id
        report = StorageObjectService(db, StorageService.from_settings(test_settings)).check_integrity(
            obj.id, area=StorageArea.VIDEOS
        )
        assert report.status == StorageIntegrityStatus.OK.value

    switched = client.patch(
        f"{API}/lessons/{lesson_id}",
        headers=auth_header(token),
        json={"video_url": "https://new.example/video.mp4"},
    )
    assert switched.status_code == 200, switched.text
    with db_session_factory() as db:
        lesson = db.get(models.Lesson, lesson_id)
        assert lesson.video_source == "external"
        assert lesson.video_object_id is None
        obj = db.query(models.StorageObject).filter_by(object_key=key).one()
        assert obj.status == models.StorageObjectStatus.DELETED.value
        assert obj.deleted_at is not None
    assert not StorageService.from_settings(test_settings).exists(StorageArea.VIDEOS, key)


def test_legacy_uploaded_video_without_object_binding_keeps_signature_and_range(
    client, db_session_factory, test_settings
):
    _, token, _, lesson_id = _video_context(client, db_session_factory, tag="phase2b-legacy-video")
    key = f"lessons/{lesson_id}/legacy.mp4"
    body = _mp4_bytes(500)
    StorageService.from_settings(test_settings).put(StorageArea.VIDEOS, key, BytesIO(body))
    with db_session_factory() as db:
        lesson = db.get(models.Lesson, lesson_id)
        lesson.video_source = "upload"
        lesson.video_url = None
        lesson.video_storage_key = key
        lesson.video_filename = "legacy.mp4"
        lesson.video_content_type = "video/mp4"
        lesson.video_size = len(body)
        lesson.video_object_id = None
        db.commit()

    playback = client.get(
        f"{API}/lessons/{lesson_id}/video-playback-url",
        headers=auth_header(token),
    )
    assert playback.status_code == 200, playback.text
    media = client.get(playback.json()["url"], headers={"Range": "bytes=0-9"})
    assert media.status_code == 206
    assert media.headers["content-range"] == "bytes 0-9/500"
    assert len(media.content) == 10
    with db_session_factory() as db:
        assert db.query(models.StorageObject).count() == 0


def test_deleting_uploaded_video_is_idempotent_and_keeps_metadata_audit(
    client, db_session_factory, test_settings
):
    _, token, _, lesson_id = _video_context(client, db_session_factory, tag="phase2b-delete-video")
    upload = client.put(
        f"{API}/lessons/{lesson_id}/video-file",
        headers=auth_header(token),
        files={"file": ("lesson.mp4", _mp4_bytes(220), "video/mp4")},
    )
    assert upload.status_code == 200
    with db_session_factory() as db:
        lesson = db.get(models.Lesson, lesson_id)
        object_id = lesson.video_object_id
        key = lesson.video_storage_key

    first = client.delete(
        f"{API}/lessons/{lesson_id}/video-file", headers=auth_header(token)
    )
    second = client.delete(
        f"{API}/lessons/{lesson_id}/video-file", headers=auth_header(token)
    )
    assert first.status_code == second.status_code == 204
    with db_session_factory() as db:
        lesson = db.get(models.Lesson, lesson_id)
        assert lesson.video_object_id is None
        obj = db.get(models.StorageObject, object_id)
        assert obj.status == models.StorageObjectStatus.DELETED.value
        assert obj.deleted_at is not None
    assert not StorageService.from_settings(test_settings).exists(StorageArea.VIDEOS, key)
