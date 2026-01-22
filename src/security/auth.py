"""Authentication and token management."""

import warnings
import sys
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from jose import jwt, JWTError

# Fix passlib bcrypt version reading issue for Python 3.13 + bcrypt 4.2.1+
# bcrypt 4.2.1 changed __about__ location, passlib 1.7.4 tries old location
# Workaround: Monkey patch bcrypt to provide __about__ for passlib
try:
    import bcrypt
    if not hasattr(bcrypt, '__about__'):
        # Create a mock __about__ module for passlib compatibility
        class MockAbout:
            __version__ = getattr(bcrypt, '__version__', '4.2.1')
        bcrypt.__about__ = MockAbout()
except (ImportError, AttributeError):
    pass

# Suppress all passlib-related warnings and errors
warnings.filterwarnings("ignore", message=".*error reading bcrypt version.*")
warnings.filterwarnings("ignore", message=".*trapped.*error reading bcrypt version.*")

# Suppress stderr output from passlib
logging.getLogger("passlib").setLevel(logging.CRITICAL)

# Import passlib (errors should be suppressed now)
from passlib.context import CryptContext

from ..core.config import get_config
from ..core.logger import get_logger

logger = get_logger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Get password hash."""
    return pwd_context.hash(password)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Data to encode in the token
        expires_delta: Token expiration time
        
    Returns:
        JWT token string
    """
    config = get_config()
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=config.access_token_expire_minutes
        )
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        config.secret_key,
        algorithm="HS256"
    )
    return encoded_jwt


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token data or None if invalid
    """
    try:
        config = get_config()
        payload = jwt.decode(
            token,
            config.secret_key,
            algorithms=["HS256"]
        )
        return payload
    except JWTError as e:
        logger.warning("Token verification failed", error=str(e))
        return None


class AuthManager:
    """Manage authentication and user sessions."""

    def __init__(self):
        self._users: Dict[str, Dict[str, Any]] = {}
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._permission_manager = None
        
        # Initialize with default admin user
        config = get_config()
        self._users["admin"] = {
            "username": "admin",
            "password_hash": get_password_hash(config.web_ui_password),
            "roles": ["admin"],
            "enabled": True
        }
        
        # Initialize admin user permissions
        self._init_permissions()
    
    def _init_permissions(self):
        """Initialize permission manager and assign admin role."""
        from ..security.permissions import get_permission_manager
        self._permission_manager = get_permission_manager()
        # Assign admin role to admin user
        self._permission_manager.assign_role_to_user("admin", "admin")

    async def authenticate(self, username: str, password: str) -> Optional[str]:
        """
        Authenticate a user and return access token.
        
        Args:
            username: Username
            password: Plain password
            
        Returns:
            Access token if authentication successful
        """
        user = self._users.get(username)
        if not user:
            logger.warning("Authentication failed: user not found", username=username)
            return None
        
        if not user.get("enabled", False):
            logger.warning("Authentication failed: user disabled", username=username)
            return None
        
        if not verify_password(password, user["password_hash"]):
            logger.warning("Authentication failed: invalid password", username=username)
            return None
        
        # Create access token
        token = create_access_token(
            data={
                "sub": username,
                "roles": user.get("roles", [])
            }
        )
        
        # Store session
        self._sessions[token] = {
            "username": username,
            "roles": user.get("roles", []),
            "created_at": datetime.utcnow()
        }
        
        logger.info("User authenticated", username=username)
        return token

    async def verify_session(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify a session token."""
        payload = verify_token(token)
        if payload and token in self._sessions:
            return self._sessions[token]
        return None

    async def logout(self, token: str) -> bool:
        """Logout a user session."""
        if token in self._sessions:
            username = self._sessions[token]["username"]
            del self._sessions[token]
            logger.info("User logged out", username=username)
            return True
        return False

    async def create_user(
        self,
        username: str,
        password: str,
        roles: Optional[list] = None
    ) -> bool:
        """Create a new user."""
        if username in self._users:
            return False
        
        self._users[username] = {
            "username": username,
            "password_hash": get_password_hash(password),
            "roles": roles or ["user"],
            "enabled": True
        }
        
        logger.info("User created", username=username)
        return True

    async def delete_user(self, username: str) -> bool:
        """Delete a user."""
        if username in self._users and username != "admin":
            del self._users[username]
            logger.info("User deleted", username=username)
            return True
        return False

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user info."""
        user = self._users.get(username)
        if user:
            # Don't return password hash
            return {
                "username": user["username"],
                "roles": user["roles"],
                "enabled": user["enabled"]
            }
        return None

    def get_all_users(self) -> list:
        """Get all users."""
        return [
            {
                "username": user["username"],
                "roles": user["roles"],
                "enabled": user["enabled"]
            }
            for user in self._users.values()
        ]

