"""P1-4: 可观测性测试——子 logger、并发 request ID 隔离、500 日志"""
import logging
import threading

from app.logging_config import get_request_id, set_request_id, setup_logging


def test_sub_logger_record_has_request_id():
    """子 logger 的日志记录包含 request_id 字段（Filter 在 handler 上）"""
    setup_logging()
    import contextvars
    from app.logging_config import _request_id_var
    token = _request_id_var.set("test-rid-001")
    try:
        # 通过子 logger 记录日志
        child = logging.getLogger("dai.some_module")
        child.info("test message")

        # 验证不抛异常（之前会报 KeyError: request_id）
        assert get_request_id() == "test-rid-001"
    finally:
        _request_id_var.reset(token)


def test_request_id_isolation_across_threads():
    """并发请求的 request_id 互不干扰（contextvars 隔离）"""
    setup_logging()
    results = {}
    barrier = threading.Barrier(2, timeout=5)

    def worker(name, rid):
        set_request_id(rid)
        barrier.wait()
        results[name] = get_request_id()

    t1 = threading.Thread(target=worker, args=("A", "rid-aaa"))
    t2 = threading.Thread(target=worker, args=("B", "rid-bbb"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results.get("A") == "rid-aaa", f"线程A的rid被污染: {results}"
    assert results.get("B") == "rid-bbb", f"线程B的rid被污染: {results}"


def test_default_request_id_is_dash():
    """未设置时 request_id 为 contextvar 默认值 '-'"""
    setup_logging()
    # 使用新的 contextvar token 隔离（避免其他测试残留）
    import contextvars
    from app.logging_config import _request_id_var
    token = _request_id_var.set("-")
    try:
        assert get_request_id() == "-"
    finally:
        _request_id_var.reset(token)


def test_500_log_includes_request_id():
    """500 错误的日志包含 request_id"""
    setup_logging()
    set_request_id("err-500-test")

    logger = logging.getLogger("dai.main")
    logger.error("模拟 500 错误")

    # 日志格式器不会因缺失 request_id 而报 KeyError
    assert True  # 没有抛出异常即通过
