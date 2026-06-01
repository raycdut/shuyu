import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.service import init_auth_config, create_user


@pytest.fixture(autouse=True)
def setup_app():
    init_auth_config()
    from app.main import app
    yield app


@pytest.fixture
async def client(setup_app):
    transport = ASGITransport(app=setup_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def admin_token(client):
    resp = await client.post("/api/auth/register", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 201
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    return resp.json()["access_token"]


class TestRegister:
    async def test_register_success(self, client):
        resp = await client.post("/api/auth/register", json={"username": "alice", "password": "alice123"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "alice"
        assert data["role"] in ("admin", "user")
        assert "id" in data

    async def test_register_duplicate(self, client):
        await client.post("/api/auth/register", json={"username": "alice", "password": "alice123"})
        resp = await client.post("/api/auth/register", json={"username": "alice", "password": "other123"})
        assert resp.status_code == 409
        assert "用户名已存在" in resp.text

    async def test_register_short_password(self, client):
        resp = await client.post("/api/auth/register", json={"username": "bob", "password": "12345"})
        assert resp.status_code == 400


class TestLogin:
    async def test_login_success(self, client):
        await client.post("/api/auth/register", json={"username": "admin", "password": "admin123"})
        resp = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "admin"

    async def test_login_returns_last_login_at(self, client):
        await client.post("/api/auth/register", json={"username": "admin", "password": "admin123"})
        resp = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert resp.status_code == 200
        user = resp.json()["user"]
        assert "last_login_at" in user
        assert user["last_login_at"] is not None

    async def test_login_wrong_password(self, client):
        await client.post("/api/auth/register", json={"username": "admin", "password": "admin123"})
        resp = await client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    async def test_login_nonexistent(self, client):
        resp = await client.post("/api/auth/login", json={"username": "nobody", "password": "pass"})
        assert resp.status_code == 401


class TestMe:
    async def test_me_authenticated(self, client, admin_token):
        resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["username"] == "admin"

    async def test_me_unauthenticated(self, client):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_me_invalid_token(self, client):
        resp = await client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code == 401


class TestAdminUsers:
    async def test_list_users(self, client, admin_token):
        await client.post("/api/auth/register", json={"username": "alice", "password": "alice123"})
        resp = await client.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2

    async def test_list_users_includes_last_login(self, client, admin_token):
        await client.post("/api/auth/register", json={"username": "alice", "password": "alice123"})
        resp = await client.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        for user in resp.json():
            assert "last_login_at" in user

    async def test_list_users_forbidden_for_user(self, client):
        await client.post("/api/auth/register", json={"username": "admin1", "password": "admin123"})
        await client.post("/api/auth/register", json={"username": "alice", "password": "alice123"})
        resp = await client.post("/api/auth/login", json={"username": "alice", "password": "alice123"})
        token = resp.json()["access_token"]
        resp = await client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    async def test_update_user(self, client, admin_token):
        await client.post("/api/auth/register", json={"username": "alice", "password": "alice123"})
        users = await client.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
        user_id = users.json()[1]["id"]
        resp = await client.patch(
            f"/api/admin/users/{user_id}",
            json={"role": "admin"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    async def test_delete_user(self, client, admin_token):
        await client.post("/api/auth/register", json={"username": "alice", "password": "alice123"})
        users = await client.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
        user_id = users.json()[1]["id"]
        resp = await client.delete(
            f"/api/admin/users/{user_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200


class TestUserDatabases:
    async def test_set_and_get_databases(self, client, admin_token):
        await client.post("/api/auth/register", json={"username": "alice", "password": "alice123"})
        users = await client.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
        user_id = users.json()[1]["id"]

        resp = await client.put(
            f"/api/admin/users/{user_id}/databases",
            json={"database_ids": ["db1", "db2"]},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert set(resp.json()["database_ids"]) == {"db1", "db2"}

        resp = await client.get(
            f"/api/admin/users/{user_id}/databases",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert set(resp.json()["database_ids"]) == {"db1", "db2"}
