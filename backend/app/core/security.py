"""Authentication, session management, CSRF validation, and Role-Based Access Control."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from enum import Enum
from typing import Dict, List, Optional
from fastapi import Cookie, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel
import httpx

from app.core.config import settings


class Role(str, Enum):
    """User roles for access control."""
    VIEWER = "viewer"
    ANALYST = "analyst"
    ADMIN = "admin"


class UserSession(BaseModel):
    """Active authenticated session model."""
    session_id: str
    user_id: str
    username: str
    email: str
    roles: List[str]
    created_at: float
    expires_at: float
    csrf_token: str
    id_token: Optional[str] = None


# Thread-safe in-memory session registry with TTL
_SESSIONS: Dict[str, UserSession] = {}
# Ephemeral PKCE verifiers storage for OIDC auth flow
_PKCE_STORE: Dict[str, Dict[str, str]] = {}


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    return secrets.token_urlsafe(32)


def create_session(
    user_id: str,
    username: str,
    email: str,
    roles: List[str],
    id_token: Optional[str] = None,
    ttl_seconds: int = 86400
) -> UserSession:
    """Create and register a new user session."""
    session_id = secrets.token_hex(24)
    csrf_token = generate_csrf_token()
    now = time.time()
    session = UserSession(
        session_id=session_id,
        user_id=user_id,
        username=username,
        email=email,
        roles=roles if roles else [Role.VIEWER.value],
        created_at=now,
        expires_at=now + ttl_seconds,
        csrf_token=csrf_token,
        id_token=id_token
    )
    _SESSIONS[session_id] = session
    return session


def get_session(session_id: Optional[str]) -> Optional[UserSession]:
    """Retrieve an active session if not expired."""
    if not session_id or session_id not in _SESSIONS:
        return None
    session = _SESSIONS[session_id]
    if time.time() > session.expires_at:
        _SESSIONS.pop(session_id, None)
        return None
    return session


def delete_session(session_id: Optional[str]) -> None:
    """Revoke and delete a session."""
    if session_id:
        _SESSIONS.pop(session_id, None)


def generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256)."""
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("utf-8").replace("=", "")
    return code_verifier, code_challenge


def store_pkce_state(state: str, code_verifier: str, nonce: str) -> None:
    """Store PKCE verifier keyed by state."""
    _PKCE_STORE[state] = {
        "verifier": code_verifier,
        "nonce": nonce,
        "created_at": str(time.time())
    }


def pop_pkce_state(state: str) -> Optional[Dict[str, str]]:
    """Retrieve and remove PKCE state."""
    return _PKCE_STORE.pop(state, None)


async def get_current_user(
    request: Request,
    session_cookie: Optional[str] = Cookie(default=None, alias="session_id")
) -> UserSession:
    """Authenticate incoming request via session cookie or Authorization header."""
    auth_header = request.headers.get("Authorization")
    session: Optional[UserSession] = None

    if session_cookie:
        session = get_session(session_cookie)
    elif auth_header and auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
        # Check if the token corresponds to an active session ID
        session = get_session(token)

    # In demo mode, if no active session, auto-provision a local demo session
    if not session and settings.demo_mode:
        # Check for demo role override header for testing role permissions
        demo_role = request.headers.get("X-Demo-Role", Role.ADMIN.value)
        if demo_role not in (Role.VIEWER.value, Role.ANALYST.value, Role.ADMIN.value):
            demo_role = Role.ADMIN.value
        session = create_session(
            user_id="demo-user-1",
            username="Demo Operator",
            email="demo@localhost",
            roles=[demo_role],
            ttl_seconds=3600
        )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in via Keycloak OIDC.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return session


def require_role(required_role: Role):
    """Enforce role-based access control hierarchy (ADMIN > ANALYST > VIEWER)."""
    hierarchy = {
        Role.VIEWER.value: 1,
        Role.ANALYST.value: 2,
        Role.ADMIN.value: 3
    }
    required_level = hierarchy[required_role.value]

    async def role_checker(
        request: Request,
        current_user: UserSession = Depends(get_current_user),
        x_csrf_token: Optional[str] = Header(default=None, alias="X-CSRF-Token")
    ) -> UserSession:
        # Check CSRF token for mutating state requests
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            # If session was authenticated via cookie, require matching CSRF header
            cookie_session = request.cookies.get("session_id")
            if cookie_session and not settings.demo_mode:
                if not x_csrf_token or not hmac.compare_digest(x_csrf_token, current_user.csrf_token):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Invalid or missing CSRF token."
                    )

        user_level = max([hierarchy.get(r, 0) for r in current_user.roles], default=0)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires role '{required_role.value}' or higher."
            )
        return current_user

    return role_checker
