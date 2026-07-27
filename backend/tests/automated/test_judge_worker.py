"""Judge + sample-run 第三轮 RED 测试"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest

from app import models
from app.worker.judge_worker import (
    _get_timeout,
    _run_docker_pytest,
    _status_from_pytest,
    process_submission,
)
from conftest import auth_header, create_user, login


def _setup_course(client, db_session_factory, course_status="published", assignment_status="published"):
    create_user(db_session_factory, "t_j", "teacher")
    create_user(db_session_factory, "s_j", "student")
    t_tok, _ = login(client, "t_j")
    s_tok, _ = login(client, "s_j")
    c = client.post('/api/v1/courses', headers=auth_header(t_tok), json={
        'title': 'Judge Course', 'status': course_status,
    })
    cid = c.json()['id']
    if course_status == 'published':
        client.post(f'/api/v1/courses/{cid}/enroll', headers=auth_header(s_tok))
    a = client.post('/api/v1/assignments', headers=auth_header(t_tok), json={
        'course_id': cid, 'title': 'A1', 'status': assignment_status,
    })
    aid = a.json()['id']
    q = client.post(f'/api/v1/assignments/{aid}/questions', headers=auth_header(t_tok), json={
        'title': 'Q1', 'function_name': 'add',
        'public_cases': [{'args': [1, 2], 'expected': 3}],
        'hidden_tests': 'HIDDEN_SENTINEL_XYZ\ndef test_hidden(): assert add(1,2)==3',
    })
    qid = q.json()['id']
    return t_tok, s_tok, cid, aid, qid


# ═══════════════════════════════════════════════════════════════
# 1. sample-run 无 DB 副作用
# ═══════════════════════════════════════════════════════════════

def test_sample_run_no_submission_no_queue(client, db_session_factory):
    _, s_tok, _, _, qid = _setup_course(client, db_session_factory)
    with db_session_factory() as db:
        before = db.query(models.Submission).count()

    with patch('app.api.judge._run_docker_pytest') as mock_sandbox:
        mock_sandbox.return_value = ('1 passed', '', 0, 50)
        r = client.post(f'/api/v1/judge/questions/{qid}/sample-run',
                        headers=auth_header(s_tok),
                        json={'question_id': qid, 'code': 'def add(a,b): return a+b'})

    assert r.status_code == 200, r.text
    assert r.json()['status'] == 'accepted'
    with db_session_factory() as db:
        after = db.query(models.Submission).count()
    assert after == before


# ═══════════════════════════════════════════════════════════════
# 2. 权限拒绝：未选课、draft assignment、draft course、teacher
# ═══════════════════════════════════════════════════════════════

def test_sample_run_permission_denied_all_cases(client, db_session_factory):
    # 未选课
    create_user(db_session_factory, "t_perm2", "teacher")
    create_user(db_session_factory, "s_perm2", "student")
    t_tok, _ = login(client, "t_perm2")
    s_tok, _ = login(client, "s_perm2")
    c = client.post('/api/v1/courses', headers=auth_header(t_tok), json={
        'title': 'C', 'status': 'published',
    })
    cid = c.json()['id']
    # 不选课
    a = client.post('/api/v1/assignments', headers=auth_header(t_tok), json={
        'course_id': cid, 'title': 'A', 'status': 'published',
    })
    q = client.post(f'/api/v1/assignments/{a.json()["id"]}/questions', headers=auth_header(t_tok), json={
        'title': 'Q', 'function_name': 'f', 'hidden_tests': 'def test(): pass',
    })
    qid = q.json()['id']

    r = client.post(f'/api/v1/judge/questions/{qid}/sample-run',
                    headers=auth_header(s_tok), json={'question_id': qid, 'code': 'pass'})
    assert r.status_code == 403, f"未选课: {r.status_code}"

    # teacher
    r = client.post(f'/api/v1/judge/questions/{qid}/sample-run',
                    headers=auth_header(t_tok), json={'question_id': qid, 'code': 'pass'})
    assert r.status_code == 403, f"teacher: {r.status_code}"

    # draft assignment（用不同用户名）
    create_user(db_session_factory, "t_da2", "teacher")
    create_user(db_session_factory, "s_da2", "student")
    t_da, _ = login(client, "t_da2")
    s_da, _ = login(client, "s_da2")
    c2 = client.post('/api/v1/courses', headers=auth_header(t_da), json={'title':'C2','status':'published'})
    client.post(f'/api/v1/courses/{c2.json()["id"]}/enroll', headers=auth_header(s_da))
    a2 = client.post('/api/v1/assignments', headers=auth_header(t_da), json={'course_id':c2.json()['id'],'title':'A2','status':'draft'})
    q2 = client.post(f'/api/v1/assignments/{a2.json()["id"]}/questions', headers=auth_header(t_da), json={
        'title':'Q2','function_name':'f','hidden_tests':'def test(): pass',
    })
    r = client.post(f'/api/v1/judge/questions/{q2.json()["id"]}/sample-run',
                    headers=auth_header(s_da), json={'question_id':q2.json()['id'],'code':'pass'})
    assert r.status_code == 403, f"draft assignment: {r.status_code}"

    # draft course
    create_user(db_session_factory, "t_dc2", "teacher")
    create_user(db_session_factory, "s_dc2", "student")
    t_dc, _ = login(client, "t_dc2")
    s_dc, _ = login(client, "s_dc2")
    c3 = client.post('/api/v1/courses', headers=auth_header(t_dc), json={'title':'C3','status':'draft'})
    a3 = client.post('/api/v1/assignments', headers=auth_header(t_dc), json={'course_id':c3.json()['id'],'title':'A3','status':'published'})
    q3 = client.post(f'/api/v1/assignments/{a3.json()["id"]}/questions', headers=auth_header(t_dc), json={
        'title':'Q3','function_name':'f','hidden_tests':'def test(): pass',
    })
    r = client.post(f'/api/v1/judge/questions/{q3.json()["id"]}/sample-run',
                    headers=auth_header(s_dc), json={'question_id':q3.json()['id'],'code':'pass'})
    assert r.status_code in (403, 404), f"draft course: {r.status_code}"


# ═══════════════════════════════════════════════════════════════
# 3. Docker argv 精确断言
# ═══════════════════════════════════════════════════════════════

def test_docker_sandbox_argv_exact_params():
    settings = MagicMock()
    settings.judge_cpu_limit = 2.0
    settings.judge_image = 'dai-judge'

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout='ok', stderr='')
        _run_docker_pytest(Path('/tmp/t'), settings, timeout_seconds=5, memory_limit_mb=128,
                           test_filename="test_sample.py")

    argv = mock_run.call_args[0][0]
    # --cpus after global value
    cpu_idx = argv.index('--cpus')
    assert argv[cpu_idx + 1] == '2.0', f"--cpus value: {argv[cpu_idx + 1]}"
    # --memory after question value
    mem_idx = argv.index('--memory')
    assert argv[mem_idx + 1] == '128m', f"--memory value: {argv[mem_idx + 1]}"
    # timeout kwarg
    assert mock_run.call_args[1]['timeout'] == 5
    # test filename
    assert argv[-2:] == ['-p', 'no:cacheprovider'] or 'test_sample.py' in argv
    assert 'test_sample.py' in ' '.join(argv)

    assert '--network' in argv and 'none' in argv
    assert '--cap-drop' in argv and 'ALL' in argv
    assert '--security-opt' in argv
    assert '--read-only' in argv
    tmpfs_idx = argv.index('--tmpfs')
    assert 'size=' in argv[tmpfs_idx + 1]
    assert '--user' in argv and '1000:1000' in argv


# ═══════════════════════════════════════════════════════════════
# 4. Timeout cleanup + 5. Hidden sentinel
# ═══════════════════════════════════════════════════════════════

def test_docker_timeout_cleans_up():
    settings = MagicMock()
    settings.judge_cpu_limit = 1.0
    settings.judge_image = 'dai-judge'
    rm_calls = []

    def fake_run(args, **kwargs):
        if args[0] == 'docker' and args[1] == 'rm':
            rm_calls.append(args)
            return MagicMock(returncode=0)
        raise subprocess.TimeoutExpired(args, kwargs.get('timeout', 30))

    with patch('subprocess.run', side_effect=fake_run):
        _, _, rc, _ = _run_docker_pytest(Path('/tmp/t'), settings, timeout_seconds=3, memory_limit_mb=128)
    assert rc == 124
    assert len(rm_calls) >= 1


def test_sample_run_does_not_leak_hidden_sentinel(client, db_session_factory):
    """mock _run_docker_pytest，捕获写入的 test_sample.py，断言不含 HIDDEN_SENTINEL"""
    _, s_tok, _, _, qid = _setup_course(client, db_session_factory)

    captured_test_content = []

    def mock_sandbox(workdir, *args, **kwargs):
        test_file = workdir / "test_sample.py"
        if test_file.exists():
            captured_test_content.append(test_file.read_text())
        return ('1 passed', '', 0, 50)

    with patch('app.api.judge._run_docker_pytest', side_effect=mock_sandbox):
        client.post(f'/api/v1/judge/questions/{qid}/sample-run',
                    headers=auth_header(s_tok),
                    json={'question_id': qid, 'code': 'def add(a,b): return a+b'})

    assert len(captured_test_content) > 0, "未捕获测试文件内容"
    content = captured_test_content[0]
    assert 'HIDDEN_SENTINEL_XYZ' not in content, f"hidden sentinel leaked: {content}"
    assert 'def add' in content


# ═══════════════════════════════════════════════════════════════
# 6. Docker fail → system_error / JUDGE_UNAVAILABLE
# ═══════════════════════════════════════════════════════════════

def test_formal_docker_fail_system_error():
    settings = MagicMock()
    settings.judge_use_docker = True
    settings.judge_timeout_seconds = 30
    settings.judge_memory_limit_mb = 256
    settings.judge_image = 'dai-judge'
    db = MagicMock()
    q = MagicMock()
    q.time_limit_ms = 5000
    q.memory_limit_mb = 128
    q.hidden_tests = 'def test(): pass'
    sub = MagicMock()
    sub.id = 1
    sub.code = 'pass'
    sub.status = 'queued'
    sub.grading_status = 'queued'
    sub.question_id = 1
    db.get.side_effect = lambda m, i: q if m == models.JudgeQuestion else sub
    redis = MagicMock()

    with patch('subprocess.run', side_effect=FileNotFoundError('no docker')):
        with patch('app.services.judge_queue.claim_job', return_value=True):
            result = process_submission(db, redis, settings, 1)
    assert result.status == 'system_error'
    assert result.score == 0
    db.commit.assert_called()
    db.refresh.assert_called()
    redis.setex.assert_called()


def test_sample_run_docker_unavailable(client, db_session_factory):
    _, s_tok, _, _, qid = _setup_course(client, db_session_factory)
    with patch('app.api.judge._run_docker_pytest', side_effect=FileNotFoundError('no docker')):
        r = client.post(f'/api/v1/judge/questions/{qid}/sample-run',
                        headers=auth_header(s_tok),
                        json={'question_id': qid, 'code': 'pass'})
    assert r.status_code == 503, r.text
    assert r.json()['detail']['code'] == 'JUDGE_UNAVAILABLE'


def test_get_timeout_values():
    q = MagicMock()
    s = MagicMock()
    s.judge_timeout_seconds = 30
    q.time_limit_ms = 1001; assert _get_timeout(q, s) == 2
    q.time_limit_ms = 60000; assert _get_timeout(q, s) == 30
    q.time_limit_ms = 0; assert _get_timeout(q, s) == 1
    q.time_limit_ms = 100; assert _get_timeout(q, s) == 1


# ═══════════════════════════════════════════════════════════════
# P0 回归测试
# ═══════════════════════════════════════════════════════════════

def test_p0_1_brpop_receives_list_of_queues():
    """P0-1: Worker 必须用 brpop([q1, q2], timeout=0) 而不是 brpop(q1, q2)"""
    import fakeredis
    from app.config import Settings

    r = fakeredis.FakeRedis(decode_responses=True)
    # 用正确的调用方式验证可以正常阻塞（fakeredis 支持 brpop 列表参数）
    r.rpush("judge:queue", "123")
    result = r.brpop(["judge:queue", "judge:exam:queue"], timeout=0)
    assert result is not None
    queue_name, value = result
    assert queue_name == "judge:queue"
    assert value == "123"

    # 验证不带列表的调用会报错（第二个参数被当作 timeout）
    with pytest.raises(Exception):
        r.brpop("judge:queue", "judge:exam:queue")


def test_p0_2_exam_functions_defined_at_module_level():
    """P0-2: process_exam_answer 和 enqueue_exam_answer 在模块导入时可访问"""
    from app.worker import judge_worker as jw
    assert hasattr(jw, "process_exam_answer"), "process_exam_answer 未在模块顶层定义"
    assert hasattr(jw, "enqueue_exam_answer"), "enqueue_exam_answer 未在模块顶层定义"
    assert hasattr(jw, "EXAM_JUDGE_QUEUE"), "EXAM_JUDGE_QUEUE 未在模块顶层定义"
    assert callable(jw.process_exam_answer)
    assert callable(jw.enqueue_exam_answer)


def test_p0_5_maybe_finalize_blocks_on_running():
    """P0-5: finalize_if_ready 不应在存在 running 答案时汇总"""
    from app.services.exam_grading import finalize_if_ready

    # 测试1: 存在 running 答案 → 不应汇总
    db = MagicMock()
    mock_sub = MagicMock()
    mock_sub.status = "grading"
    # scalar 调用顺序：1) with_for_update → submission, 2) unfinished check → 有值
    db.scalar.side_effect = [mock_sub, MagicMock()]

    finalize_if_ready(1, db)

    # scalar 应该只被调用了 2 次（submission + unfinished），没有后续查询
    assert db.scalar.call_count == 2, f"应该在发现未完成答案后立即返回，但调用了 {db.scalar.call_count} 次"
    assert not db.commit.called, "存在未完成答案时不应提交汇总"

    # 测试2: 全部完成 → 应该汇总
    db2 = MagicMock()
    mock_sub2 = MagicMock()
    mock_sub2.status = "grading"
    mock_sub2.exam_id = 1
    mock_sub2.student_id = 1
    # scalar: submission, unfinished=None, total=100.0, grade=None
    db2.scalar.side_effect = [mock_sub2, None, 100.0, None]

    finalize_if_ready(2, db2)
    assert db2.scalar.call_count >= 4, "应该在确认无未完成后查询 total + grade"
    assert db2.commit.called, "应该提交最终成绩"
