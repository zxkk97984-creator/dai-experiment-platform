from conftest import auth_header, create_user, login


def test_admin_can_create_user_and_logout_blacklists_token(client, db_session_factory):
    create_user(db_session_factory, "admin", "admin")
    access_token, refresh_token = login(client, "admin")

    me_response = client.get("/api/v1/auth/me", headers=auth_header(access_token))
    assert me_response.status_code == 200
    assert me_response.json()["role"] == "admin"

    create_response = client.post(
        "/api/v1/users",
        headers=auth_header(access_token),
        json={
            "username": "student001",
            "password": "Passw0rd!",
            "real_name": "Student One",
            "role": "student",
        },
    )
    assert create_response.status_code == 201, create_response.text
    assert create_response.json()["username"] == "student001"
    assert "password" not in create_response.text

    list_response = client.get("/api/v1/users", headers=auth_header(access_token))
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 2

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"] != access_token

    logout_response = client.post(
        "/api/v1/auth/logout",
        headers=auth_header(access_token),
        json={"refresh_token": refresh_token},
    )
    assert logout_response.status_code == 204

    blocked_response = client.get("/api/v1/auth/me", headers=auth_header(access_token))
    assert blocked_response.status_code == 401
    assert blocked_response.json()["detail"]["code"] == "TOKEN_REVOKED"


def test_student_cannot_create_users(client, db_session_factory):
    create_user(db_session_factory, "student", "student")
    access_token, _ = login(client, "student")

    response = client.post(
        "/api/v1/users",
        headers=auth_header(access_token),
        json={
            "username": "teacher001",
            "password": "Passw0rd!",
            "real_name": "Teacher One",
            "role": "teacher",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FORBIDDEN"
