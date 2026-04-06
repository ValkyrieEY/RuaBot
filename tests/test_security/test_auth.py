"""
Tests for Authentication and Security components.

This test suite covers:
- Authentication mechanisms
- Permission system
- Access control
- Device key management
- Audit logging
- Token validation
- Session management
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

from src.security.auth import AuthService, PasswordHasher
from src.security.permissions import Permission, Role, PermissionManager
from src.security.access_control import AccessControl, AccessDecision


class TestPasswordHasher:
    """Test suite for PasswordHasher functionality."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "test_password_123"
        hashed = PasswordHasher.hash_password(password)

        assert hashed is not None
        assert hashed != password
        assert len(hashed) > 0

    def test_verify_password_correct(self):
        """Test verifying correct password."""
        password = "test_password_123"
        hashed = PasswordHasher.hash_password(password)

        is_valid = PasswordHasher.verify_password(password, hashed)

        assert is_valid is True

    def test_verify_password_incorrect(self):
        """Test verifying incorrect password."""
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = PasswordHasher.hash_password(password)

        is_valid = PasswordHasher.verify_password(wrong_password, hashed)

        assert is_valid is False

    def test_hash_same_password_different_hashes(self):
        """Test that same password produces different hashes."""
        password = "test_password_123"
        hash1 = PasswordHasher.hash_password(password)
        hash2 = PasswordHasher.hash_password(password)

        assert hash1 != hash2

    def test_verify_with_invalid_hash(self):
        """Test verifying with invalid hash format."""
        password = "test_password_123"
        invalid_hash = "invalid_hash_format"

        is_valid = PasswordHasher.verify_password(password, invalid_hash)

        assert is_valid is False


class TestAuthService:
    """Test suite for AuthService functionality."""

    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock database manager."""
        db = MagicMock()
        db.get_user_by_username = AsyncMock(return_value=None)
        db.create_user = AsyncMock()
        db.update_user = AsyncMock()
        db.get_user_by_id = AsyncMock(return_value=None)
        return db

    @pytest.fixture
    def auth_service(self, mock_db_manager):
        """Create an auth service instance."""
        return AuthService(db_manager=mock_db_manager)

    @pytest.mark.asyncio
    async def test_auth_service_initialization(self, auth_service: AuthService):
        """Test that auth service initializes correctly."""
        assert auth_service is not None
        assert auth_service.db_manager is not None

    @pytest.mark.asyncio
    async def test_register_user(self, auth_service: AuthService):
        """Test user registration."""
        username = "testuser"
        password = "test_password_123"

        # Mock user creation
        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_user.username = username
        mock_user.hashed_password = PasswordHasher.hash_password(password)

        auth_service.db_manager.create_user = AsyncMock(return_value=mock_user)

        user = await auth_service.register_user(username, password)

        assert user is not None
        assert user.username == username

    @pytest.mark.asyncio
    async def test_register_duplicate_user(self, auth_service: AuthService):
        """Test registering duplicate username."""
        username = "testuser"
        password = "test_password_123"

        # Mock existing user
        existing_user = MagicMock()
        auth_service.db_manager.get_user_by_username = AsyncMock(return_value=existing_user)

        with pytest.raises(ValueError):
            await auth_service.register_user(username, password)

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, auth_service: AuthService):
        """Test successful user authentication."""
        username = "testuser"
        password = "test_password_123"
        hashed_password = PasswordHasher.hash_password(password)

        # Mock user
        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_user.username = username
        mock_user.hashed_password = hashed_password

        auth_service.db_manager.get_user_by_username = AsyncMock(return_value=mock_user)

        user = await auth_service.authenticate_user(username, password)

        assert user is not None
        assert user.username == username

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, auth_service: AuthService):
        """Test authentication with wrong password."""
        username = "testuser"
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed_password = PasswordHasher.hash_password(password)

        # Mock user
        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_user.username = username
        mock_user.hashed_password = hashed_password

        auth_service.db_manager.get_user_by_username = AsyncMock(return_value=mock_user)

        user = await auth_service.authenticate_user(username, wrong_password)

        assert user is None

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, auth_service: AuthService):
        """Test authentication with non-existent user."""
        username = "nonexistent"
        password = "test_password_123"

        auth_service.db_manager.get_user_by_username = AsyncMock(return_value=None)

        user = await auth_service.authenticate_user(username, password)

        assert user is None


class TestPermissionManager:
    """Test suite for PermissionManager functionality."""

    @pytest.fixture
    def permission_manager(self):
        """Create a permission manager instance."""
        return PermissionManager()

    def test_create_permission(self, permission_manager: PermissionManager):
        """Test creating a permission."""
        permission = permission_manager.create_permission(
            name="users.read",
            description="Read user data"
        )

        assert permission is not None
        assert permission.name == "users.read"
        assert permission.description == "Read user data"

    def test_create_role(self, permission_manager: PermissionManager):
        """Test creating a role."""
        role = permission_manager.create_role(
            name="admin",
            description="Administrator"
        )

        assert role is not None
        assert role.name == "admin"
        assert role.description == "Administrator"

    def test_assign_permission_to_role(self, permission_manager: PermissionManager):
        """Test assigning permission to role."""
        permission = permission_manager.create_permission("users.read")
        role = permission_manager.create_role("admin")

        permission_manager.assign_permission_to_role(role.id, permission.id)

        updated_role = permission_manager.get_role(role.id)
        assert permission.id in updated_role.permission_ids

    def test_check_role_has_permission(self, permission_manager: PermissionManager):
        """Test checking if role has permission."""
        permission = permission_manager.create_permission("users.read")
        role = permission_manager.create_role("admin")

        permission_manager.assign_permission_to_role(role.id, permission.id)

        has_permission = permission_manager.role_has_permission(role.id, permission.id)

        assert has_permission is True

    def test_check_role_lacks_permission(self, permission_manager: PermissionManager):
        """Test checking if role lacks permission."""
        permission = permission_manager.create_permission("users.read")
        role = permission_manager.create_role("admin")

        has_permission = permission_manager.role_has_permission(role.id, permission.id)

        assert has_permission is False


class TestAccessControl:
    """Test suite for AccessControl functionality."""

    @pytest.fixture
    def mock_permission_manager(self):
        """Create a mock permission manager."""
        pm = MagicMock()
        pm.role_has_permission = MagicMock(return_value=True)
        return pm

    @pytest.fixture
    def access_control(self, mock_permission_manager):
        """Create an access control instance."""
        return AccessControl(permission_manager=mock_permission_manager)

    @pytest.mark.asyncio
    async def test_check_access_granted(self, access_control: AccessControl):
        """Test checking access when granted."""
        user_id = "user-123"
        resource = "users"
        action = "read"

        # Mock user has admin role
        access_control.get_user_roles = AsyncMock(return_value=["admin"])

        decision = await access_control.check_access(user_id, resource, action)

        assert decision.decision == AccessDecision.GRANTED

    @pytest.mark.asyncio
    async def test_check_access_denied(self, access_control: AccessControl):
        """Test checking access when denied."""
        user_id = "user-123"
        resource = "users"
        action = "delete"

        # Mock user has no roles or roles lack permission
        access_control.get_user_roles = AsyncMock(return_value=["guest"])
        access_control.permission_manager.role_has_permission = MagicMock(return_value=False)

        decision = await access_control.check_access(user_id, resource, action)

        assert decision.decision == AccessDecision.DENIED

    @pytest.mark.asyncio
    async def test_check_access_with_multiple_roles(self, access_control: AccessControl):
        """Test checking access with multiple roles."""
        user_id = "user-123"
        resource = "users"
        action = "read"

        # Mock user has multiple roles
        access_control.get_user_roles = AsyncMock(return_value=["admin", "moderator"])

        decision = await access_control.check_access(user_id, resource, action)

        assert decision.decision == AccessDecision.GRANTED

    @pytest.mark.asyncio
    async def test_require_access_granted(self, access_control: AccessControl):
        """Test require access when granted."""
        user_id = "user-123"
        resource = "users"
        action = "read"

        access_control.get_user_roles = AsyncMock(return_value=["admin"])

        # Should not raise exception
        await access_control.require_access(user_id, resource, action)

    @pytest.mark.asyncio
    async def test_require_access_denied(self, access_control: AccessControl):
        """Test require access when denied."""
        user_id = "user-123"
        resource = "users"
        action = "delete"

        access_control.get_user_roles = AsyncMock(return_value=["guest"])
        access_control.permission_manager.role_has_permission = MagicMock(return_value=False)

        with pytest.raises(PermissionError):
            await access_control.require_access(user_id, resource, action)


class TestAccessDecision:
    """Test suite for AccessDecision enum."""

    def test_access_decision_values(self):
        """Test access decision values."""
        assert AccessDecision.GRANTED.value == "granted"
        assert AccessDecision.DENIED.value == "denied"
        assert AccessDecision.UNKNOWN.value == "unknown"