import pytest
import bcrypt

from app.auth.service import (
    init_auth_config,
    create_user,
    authenticate_user,
    create_token,
    decode_token,
    update_last_login,
    get_user_by_id,
    get_all_users,
    update_user,
    delete_user,
    get_user_databases,
    set_user_databases,
)


@pytest.fixture(autouse=True)
def setup_auth():
    init_auth_config()
    yield


class TestCreateUser:
    def test_first_user_is_admin(self):
        user = create_user("admin", "password123")
        assert user["role"] == "admin"
        assert user["username"] == "admin"
        assert user["is_active"] is True

    def test_second_user_is_user(self):
        create_user("admin", "password123")
        user = create_user("alice", "password456")
        assert user["role"] == "user"
        assert user["username"] == "alice"

    def test_duplicate_username_raises(self):
        create_user("admin", "password123")
        with pytest.raises(ValueError, match="用户名已存在"):
            create_user("admin", "otherpass")


class TestAuthenticateUser:
    def test_valid_credentials(self):
        create_user("admin", "password123")
        user = authenticate_user("admin", "password123")
        assert user is not None
        assert user["username"] == "admin"

    def test_invalid_password(self):
        create_user("admin", "password123")
        user = authenticate_user("admin", "wrongpass")
        assert user is None

    def test_invalid_username(self):
        user = authenticate_user("nonexistent", "password123")
        assert user is None

    def test_disabled_user(self):
        create_user("admin", "password123")
        user = get_all_users()[0]
        update_user(user["id"], is_active=False)
        result = authenticate_user("admin", "password123")
        assert result is None


class TestToken:
    def test_create_and_decode(self):
        user = {"id": "test-id", "username": "admin", "role": "admin"}
        token = create_token(user)
        assert isinstance(token, str)
        assert len(token) > 20

        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "test-id"
        assert payload["username"] == "admin"
        assert payload["role"] == "admin"

    def test_invalid_token(self):
        result = decode_token("invalid.token.here")
        assert result is None

    def test_expired_token(self):
        import jwt
        from datetime import datetime, timedelta, timezone
        from app.auth.service import SECRET_KEY, ALGORITHM

        payload = {
            "sub": "test",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        result = decode_token(token)
        assert result is None


class TestUserManagement:
    def test_get_user_by_id(self):
        created = create_user("admin", "password123")
        fetched = get_user_by_id(created["id"])
        assert fetched is not None
        assert fetched["username"] == "admin"

    def test_get_all_users(self):
        create_user("admin1", "pass1")
        create_user("user1", "pass2")
        users = get_all_users()
        assert len(users) == 2

    def test_update_user_role(self):
        created = create_user("user1", "pass1")
        updated = update_user(created["id"], role="admin")
        assert updated["role"] == "admin"

    def test_delete_user(self):
        created = create_user("user1", "pass1")
        assert delete_user(created["id"]) is True
        assert get_user_by_id(created["id"]) is None

    def test_delete_nonexistent_user(self):
        assert delete_user("nonexistent-id") is False


class TestLastLogin:
    def test_create_user_has_no_last_login(self):
        user = create_user("admin", "pass")
        assert "last_login_at" in user
        assert user["last_login_at"] is None

    def test_update_last_login_sets_timestamp(self):
        user = create_user("admin", "pass")
        assert user["last_login_at"] is None
        update_last_login(user["id"])
        updated = get_user_by_id(user["id"])
        assert updated["last_login_at"] is not None

    def test_authenticate_user_returns_last_login(self):
        user = create_user("admin", "pass")
        assert user["last_login_at"] is None
        # authenticate_user does not update last_login_at
        result = authenticate_user("admin", "pass")
        assert result is not None
        assert "last_login_at" in result

    def test_get_all_users_includes_last_login(self):
        create_user("admin", "pass")
        users = get_all_users()
        assert len(users) == 1
        assert "last_login_at" in users[0]

    def test_get_user_by_id_includes_last_login(self):
        user = create_user("admin", "pass")
        fetched = get_user_by_id(user["id"])
        assert fetched is not None
        assert "last_login_at" in fetched


class TestUserDatabases:
    def test_set_and_get_databases(self):
        created = create_user("admin", "pass")
        db_ids = ["db1", "db2", "db3"]
        set_user_databases(created["id"], db_ids)
        result = get_user_databases(created["id"])
        assert sorted(result) == sorted(db_ids)

    def test_replace_databases(self):
        created = create_user("admin", "pass")
        set_user_databases(created["id"], ["db1", "db2"])
        set_user_databases(created["id"], ["db3"])
        result = get_user_databases(created["id"])
        assert result == ["db3"]

    def test_empty_databases(self):
        created = create_user("admin", "pass")
        result = get_user_databases(created["id"])
        assert result == []
