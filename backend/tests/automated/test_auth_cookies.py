"""P1-1: Auth Cookie 属性、轮换、旧 token 重放、并发 refresh、Origin 校验测试"""
import threading
import time
from unittest.mock import patch

from conftest import auth_header, create_user, login

API = "/api/v1"


# ═══════════════════════════════════════════════════════════════
# Cookie 属性
# ═══════════════════════════════════════════════════════════════

def test_login_sets_http_only_cookie(client, db_session_factory):
    """登录响应设置 HttpOnly refresh cookie"""
    create_user(db_session_factory, "ck_t", "teacher")
    r = client.post(f"{API}/auth/login", json={"username": "ck_t", "password": "Passw0rd!"})
    assert r.status_code == 200, r.text

    # 验证 Set-Cookie 头包含 HttpOnly
    cookies = r.headers.get_list("set-cookie")
    refresh_cookies = [c for c in cookies if "dai_refresh_token=" in c]
    assert len(refresh_cookies) >= 1, f"应设置 refresh cookie: {cookies}"
    cookie = refresh_cookies[0]
    assert "HttpOnly" in cookie, f"Cookie 应为 HttpOnly: {cookie}"
    assert "SameSite=Lax" in cookie or "SameSite=lax" in cookie, \
        f"Cookie 应设置 SameSite=Lax: {cookie}"
    assert "Path=/api/v1/auth" in cookie, f"Cookie Path 应为 /api/v1/auth: {cookie}"


def test_login_response_body_no_refresh_token(client, db_session_factory):
    """登录响应 JSON body 不包含 refresh_token"""
    create_user(db_session_factory, "ck2_t", "teacher")
    r = client.post(f"{API}/auth/login", json={"username": "ck2_t", "password": "Passw0rd!"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert "refresh_token" not in body, f"JSON body 不应包含 refresh_token: {body.keys()}"


# ═══════════════════════════════════════════════════════════════
# Token 轮换（refresh token rotation）
# ═══════════════════════════════════════════════════════════════

def test_refresh_rotates_cookie(client, db_session_factory):
    """刷新后旧 Cookie 被替换为新 Cookie"""
    create_user(db_session_factory, "ro_t", "teacher")
    login_r = client.post(f"{API}/auth/login",
                          json={"username": "ro_t", "password": "Passw0rd!"})

    # 从 Set-Cookie 提取 refresh token
    cookies1 = login_r.headers.get_list("set-cookie")
    old_refresh = ""
    for c in cookies1:
        if "dai_refresh_token=" in c:
            old_refresh = c.split("dai_refresh_token=")[1].split(";")[0]
    assert old_refresh, "应能从 Cookie 提取 refresh token"

    # 用旧 token 刷新（模拟 Cookie 携带）
    refresh_r = client.post(f"{API}/auth/refresh", json={}, cookies={"dai_refresh_token": old_refresh})
    assert refresh_r.status_code == 200, refresh_r.text

    # 新响应也有 Set-Cookie
    cookies2 = refresh_r.headers.get_list("set-cookie")
    new_cookies = [c for c in cookies2 if "dai_refresh_token=" in c]
    assert len(new_cookies) >= 1, "刷新后应设置新 Cookie"


def test_old_refresh_token_replay_rejected(client, db_session_factory):
    """旧 refresh token 重放被拒绝（token 轮换安全）"""
    create_user(db_session_factory, "rp_t", "teacher")
    login_r = client.post(f"{API}/auth/login",
                          json={"username": "rp_t", "password": "Passw0rd!"})

    old_refresh = ""
    for c in login_r.headers.get_list("set-cookie"):
        if "dai_refresh_token=" in c:
            old_refresh = c.split("dai_refresh_token=")[1].split(";")[0]

    # 第一次刷新成功
    r1 = client.post(f"{API}/auth/refresh", json={}, cookies={"dai_refresh_token": old_refresh})
    assert r1.status_code == 200

    # 用旧 token 再次刷新 → 401（token 已被撤销）
    r2 = client.post(f"{API}/auth/refresh", json={}, cookies={"dai_refresh_token": old_refresh})
    assert r2.status_code == 401, f"旧 token 重放应返回 401: {r2.status_code}"


# ═══════════════════════════════════════════════════════════════
# Logout 清除 Cookie
# ═══════════════════════════════════════════════════════════════

def test_logout_clears_cookie(client, db_session_factory):
    """登出后 Cookie 被清除"""
    create_user(db_session_factory, "lo_t", "teacher")
    login_r = client.post(f"{API}/auth/login",
                          json={"username": "lo_t", "password": "Passw0rd!"})
    access_token = login_r.json()["access_token"]

    old_refresh = ""
    for c in login_r.headers.get_list("set-cookie"):
        if "dai_refresh_token=" in c:
            old_refresh = c.split("dai_refresh_token=")[1].split(";")[0]

    logout_r = client.post(f"{API}/auth/logout", json={},
                           cookies={"dai_refresh_token": old_refresh},
                           headers=auth_header(access_token))
    assert logout_r.status_code == 204

    # 登出后 Cookie 被清除
    cookies = logout_r.headers.get_list("set-cookie")
    clear_cookies = [c for c in cookies if "dai_refresh_token=" in c]
    if clear_cookies:
        # 清除 Cookie 的 max-age 应为 0 或值为空
        assert 'Max-Age=0' in clear_cookies[0] or 'max-age=0' in clear_cookies[0] or \
               'dai_refresh_token="";' in clear_cookies[0] or \
               'dai_refresh_token=;' in clear_cookies[0], \
               f"Cookie 应被清除: {clear_cookies[0]}"


# ═══════════════════════════════════════════════════════════════
# 并发 refresh —— 真并发 Barrier
# ═══════════════════════════════════════════════════════════════

def test_concurrent_refresh_only_one_succeeds(client, db_session_factory):
    """真并发 refresh：两个线程同时用同一旧 token 刷新，只有第一个成功（GETDEL 原子性）"""
    create_user(db_session_factory, "cr_t", "teacher")
    login_r = client.post(f"{API}/auth/login",
                          json={"username": "cr_t", "password": "Passw0rd!"})

    old_refresh = ""
    for c in login_r.headers.get_list("set-cookie"):
        if "dai_refresh_token=" in c:
            old_refresh = c.split("dai_refresh_token=")[1].split(";")[0]
    assert old_refresh, "应能提取 refresh token"

    results = []
    errors = []
    barrier = threading.Barrier(2, timeout=5)

    def do_refresh():
        try:
            barrier.wait()  # 同步起点——两个线程同时发起 refresh
            r = client.post(f"{API}/auth/refresh", json={},
                           cookies={"dai_refresh_token": old_refresh})
            results.append(r.status_code)
        except Exception as e:
            errors.append(str(e))

    t1 = threading.Thread(target=do_refresh)
    t2 = threading.Thread(target=do_refresh)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert len(errors) == 0, f"线程异常: {errors}"
    assert len(results) == 2, f"应有 2 个结果: {results}"

    # 只有 1 个能成功（GETDEL 原子删除），另一个应 401
    success_count = sum(1 for s in results if s == 200)
    fail_count = sum(1 for s in results if s == 401)
    assert success_count == 1, f"应有恰好 1 个成功: results={results}"
    assert fail_count == 1, f"应有恰好 1 个 401: results={results}"


# ═══════════════════════════════════════════════════════════════
# Origin 校验
# ═══════════════════════════════════════════════════════════════

def test_refresh_rejects_cross_origin(client, db_session_factory):
    """refresh 拒绝跨域请求（Origin 不在 CORS 白名单）"""
    create_user(db_session_factory, "orig_t", "teacher")
    login_r = client.post(f"{API}/auth/login",
                          json={"username": "orig_t", "password": "Passw0rd!"})

    old_refresh = ""
    for c in login_r.headers.get_list("set-cookie"):
        if "dai_refresh_token=" in c:
            old_refresh = c.split("dai_refresh_token=")[1].split(";")[0]

    # 使用恶意的 Origin 头
    r = client.post(f"{API}/auth/refresh", json={},
                    cookies={"dai_refresh_token": old_refresh},
                    headers={"Origin": "https://evil.com"})
    assert r.status_code == 403, f"跨域 Origin 应返回 403: {r.status_code} {r.text}"


def test_refresh_allows_same_origin(client, db_session_factory):
    """refresh 放行无 Origin 头的请求（同源请求）"""
    create_user(db_session_factory, "orig2_t", "teacher")
    login_r = client.post(f"{API}/auth/login",
                          json={"username": "orig2_t", "password": "Passw0rd!"})

    old_refresh = ""
    for c in login_r.headers.get_list("set-cookie"):
        if "dai_refresh_token=" in c:
            old_refresh = c.split("dai_refresh_token=")[1].split(";")[0]

    # 无 Origin 头（同源请求）→ 应放行
    r = client.post(f"{API}/auth/refresh", json={},
                    cookies={"dai_refresh_token": old_refresh})
    assert r.status_code == 200, f"同源请求应返回 200: {r.status_code} {r.text}"
