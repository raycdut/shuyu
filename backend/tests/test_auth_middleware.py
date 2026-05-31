from __future__ import annotations

from unittest import mock

import pytest
from fastapi import HTTPException

from app.auth.middleware import get_current_user, require_admin


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset all mocks after each test to prevent cross-test leakage."""
    yield


class TestGetCurrentUser:
    """Tests for get_current_user middleware dependency."""

    async def test_missing_authorization_header(self):
        """Should raise 401 when no authorization header is provided."""
        with pytest.raises(HTTPException) as exc:
            await get_current_user(authorization=None)
        assert exc.value.status_code == 401
        assert exc.value.detail == "未登录"

    async def test_empty_authorization_header(self):
        """Should raise 401 when authorization header is an empty string."""
        with pytest.raises(HTTPException) as exc:
            await get_current_user(authorization="")
        assert exc.value.status_code == 401
        assert exc.value.detail == "未登录"

    async def test_non_bearer_token(self):
        """Should raise 401 when authorization header does not start with 'Bearer '."""
        with pytest.raises(HTTPException) as exc:
            await get_current_user(authorization="Basic token123")
        assert exc.value.status_code == 401
        assert exc.value.detail == "未登录"

    async def test_invalid_token(self):
        """Should raise 401 when decode_token returns None."""
        with mock.patch("app.auth.middleware.decode_token", return_value=None):
            with pytest.raises(HTTPException) as exc:
                await get_current_user(authorization="Bearer invalidtoken")
            assert exc.value.status_code == 401
            assert exc.value.detail == "登录已过期或无效，请重新登录"

    async def test_valid_token_but_user_not_found(self):
        """Should raise 401 when token is valid but user does not exist."""
        with (
            mock.patch("app.auth.middleware.decode_token", return_value={"sub": "user-1"}),
            mock.patch("app.auth.middleware.get_user_by_id", return_value=None),
        ):
            with pytest.raises(HTTPException) as exc:
                await get_current_user(authorization="Bearer validtoken")
            assert exc.value.status_code == 401
            assert exc.value.detail == "用户不存在"

    async def test_user_is_disabled(self):
        """Should raise 401 when the user account is disabled."""
        mock_user = {"id": "user-1", "username": "test", "role": "user", "is_active": False}
        with (
            mock.patch("app.auth.middleware.decode_token", return_value={"sub": "user-1"}),
            mock.patch("app.auth.middleware.get_user_by_id", return_value=mock_user),
        ):
            with pytest.raises(HTTPException) as exc:
                await get_current_user(authorization="Bearer validtoken")
            assert exc.value.status_code == 401
            assert exc.value.detail == "用户已被禁用"

    async def test_valid_user(self):
        """Should return the user dict when everything is valid."""
        mock_user = {"id": "user-1", "username": "test", "role": "user", "is_active": True}
        with (
            mock.patch("app.auth.middleware.decode_token", return_value={"sub": "user-1"}),
            mock.patch("app.auth.middleware.get_user_by_id", return_value=mock_user),
        ):
            result = await get_current_user(authorization="Bearer validtoken")
            assert result == mock_user
            assert result["is_active"] is True

    async def test_valid_admin_user(self):
        """Should return the admin user dict when everything is valid."""
        mock_user = {"id": "admin-1", "username": "admin", "role": "admin", "is_active": True}
        with (
            mock.patch("app.auth.middleware.decode_token", return_value={"sub": "admin-1"}),
            mock.patch("app.auth.middleware.get_user_by_id", return_value=mock_user),
        ):
            result = await get_current_user(authorization="Bearer admintoken")
            assert result["role"] == "admin"

    async def test_calls_decode_token_with_correct_token(self):
        """Should pass the Bearer token value (without prefix) to decode_token."""
        mock_decode = mock.patch("app.auth.middleware.decode_token", return_value={"sub": "user-1"})
        mock_get_user = mock.patch(
            "app.auth.middleware.get_user_by_id",
            return_value={"id": "user-1", "role": "user", "is_active": True},
        )
        with mock_decode as decode_mock, mock_get_user:
            await get_current_user(authorization="Bearer mytoken123")
            decode_mock.assert_called_once_with("mytoken123")

    async def test_calls_get_user_by_id_with_correct_id(self):
        """Should pass the user ID from the token payload to get_user_by_id."""
        with (
            mock.patch("app.auth.middleware.decode_token", return_value={"sub": "user-abc"}),
            mock.patch("app.auth.middleware.get_user_by_id", return_value=None),
        ):
            with mock.patch("app.auth.middleware.get_user_by_id") as get_user_mock:
                get_user_mock.return_value = {
                    "id": "user-abc",
                    "username": "test",
                    "role": "user",
                    "is_active": True,
                }
                await get_current_user(authorization="Bearer token")
                get_user_mock.assert_called_once_with("user-abc")


class TestRequireAdmin:
    """Tests for require_admin middleware dependency."""

    async def test_admin_user_passes(self):
        """Should return the user when the user has admin role."""
        user = {"id": "admin-1", "username": "admin", "role": "admin", "is_active": True}
        result = await require_admin(user=user)
        assert result == user

    async def test_non_admin_user_raises_403(self):
        """Should raise 403 when the user does not have admin role."""
        user = {"id": "user-1", "username": "test", "role": "user", "is_active": True}
        with pytest.raises(HTTPException) as exc:
            await require_admin(user=user)
        assert exc.value.status_code == 403
        assert exc.value.detail == "需要管理员权限"

    async def test_custom_role_lowercase(self):
        """Should treat 'Admin' (capitalized) as non-admin and raise 403."""
        user = {"id": "user-1", "username": "test", "role": "Admin", "is_active": True}
        with pytest.raises(HTTPException) as exc:
            await require_admin(user=user)
        assert exc.value.status_code == 403

    async def test_disabled_admin_user(self):
        """Should pass admin check even if the user is disabled (role check only)."""
        user = {"id": "admin-1", "username": "admin", "role": "admin", "is_active": False}
        result = await require_admin(user=user)
        assert result == user
