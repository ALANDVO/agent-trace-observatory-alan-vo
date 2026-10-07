"""Authentication and authorization endpoints (Keycloak OIDC and Local Demo)."""

import secrets
import time
from typing import Any, Dict, Optional
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
import httpx

from app.core.config import settings
from app.core.security import (
    Role,
    UserSession,
    create_session,
    delete_session,
    generate_pkce_pair,
    get_current_user,
    pop_pkce_state,
    store_pkce_state
)

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthMeResponse(BaseModel):
    user_id: str
    username: str
    email: str
    roles: list[str]
    csrf_token: str
    demo_mode: bool


def _set_cookie(resp: Response, sid: str, age: int = 86400):
    resp.set_cookie(key="session_id", value=sid, httponly=True, samesite="lax", max_age=age)


class RoleSwitchRequest(BaseModel):
    role: Role


@router.get("/me", response_model=AuthMeResponse)
async def get_me(user: UserSession = Depends(get_current_user)):
    """Return profile and CSRF token for the currently authenticated session."""
    return AuthMeResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        roles=user.roles,
        csrf_token=user.csrf_token,
        demo_mode=settings.demo_mode
    )


@router.get("/login")
async def login():
    """Initiate OIDC Authorization Code Flow with PKCE."""
    if settings.demo_mode and not settings.oidc_client_secret:
        # In demo mode without configured external OIDC, redirect directly to frontend with demo session
        return {"message": "Demo mode active. Use /api/auth/demo-switch-role or access endpoints with demo session."}

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier, code_challenge = generate_pkce_pair()
    store_pkce_state(state, code_verifier, nonce)

    auth_url = (
        f"{settings.oidc_issuer_url}/protocol/openid-connect/auth"
        f"?client_id={settings.oidc_client_id}"
        f"&response_type=code"
        f"&scope=openid%20profile%20email%20roles"
        f"&redirect_uri={settings.oidc_redirect_uri}"
        f"&state={state}"
        f"&nonce={nonce}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )
    return {"auth_url": auth_url}


@router.get("/callback")
async def oidc_callback(
    request: Request,
    response: Response,
    code: str = Query(...),
    state: str = Query(...)
):
    """Exchange authorization code for tokens and establish server-side session."""
    pkce_data = pop_pkce_state(state)
    if not pkce_data:
        raise HTTPException(status_code=400, detail="Invalid or expired OIDC state parameter.")

    code_verifier = pkce_data["verifier"]

    token_url = f"{settings.oidc_issuer_url}/protocol/openid-connect/token"
    token_payload = {
        "grant_type": "authorization_code",
        "client_id": settings.oidc_client_id,
        "code": code,
        "redirect_uri": settings.oidc_redirect_uri,
        "code_verifier": code_verifier
    }
    if settings.oidc_client_secret:
        token_payload["client_secret"] = settings.oidc_client_secret

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_resp = await client.post(token_url, data=token_payload)
            token_resp.raise_for_status()
            tokens = token_resp.json()

            # Retrieve user info from OIDC provider
            userinfo_url = f"{settings.oidc_issuer_url}/protocol/openid-connect/userinfo"
            userinfo_resp = await client.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {tokens['access_token']}"}
            )
            userinfo_resp.raise_for_status()
            user_data = userinfo_resp.json()

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to communicate with Keycloak OIDC provider: {str(exc)}"
        )

    # Extract roles from realm_access
    roles = user_data.get("roles", [])
    if not roles and "realm_access" in user_data:
        roles = user_data["realm_access"].get("roles", [])
    valid_roles = [r for r in roles if r in (Role.VIEWER.value, Role.ANALYST.value, Role.ADMIN.value)]
    if not valid_roles:
        valid_roles = [Role.VIEWER.value]

    session = create_session(
        user_id=user_data.get("sub", secrets.token_hex(8)),
        username=user_data.get("preferred_username", user_data.get("email", "operator")),
        email=user_data.get("email", "operator@example.com"),
        roles=valid_roles,
        id_token=tokens.get("id_token")
    )
    _set_cookie(response, session.session_id)
    return {"message": "Authentication successful", "user_id": session.user_id, "username": session.username, "roles": session.roles, "csrf_token": session.csrf_token}


@router.post("/logout")
async def logout(response: Response, session_id: Optional[str] = Cookie(default=None, alias="session_id"), user: UserSession = Depends(get_current_user)):
    """Revoke session and clear session cookie."""
    delete_session(user.session_id)
    if session_id: delete_session(session_id)
    response.delete_cookie("session_id")
    return {"message": "Logged out successfully"}


@router.post("/demo-switch-role", response_model=AuthMeResponse)
async def demo_switch_role(req: RoleSwitchRequest, response: Response, user: UserSession = Depends(get_current_user)):
    """Switch active role in local demo mode."""
    if not settings.demo_mode:
        raise HTTPException(status_code=403, detail="Role switching is only available in demo mode.")
    new_sess = create_session(user_id=user.user_id, username=user.username, email=user.email, roles=[req.role.value], ttl_seconds=3600)
    delete_session(user.session_id)
    _set_cookie(response, new_sess.session_id, 3600)
    return AuthMeResponse(user_id=new_sess.user_id, username=new_sess.username, email=new_sess.email, roles=new_sess.roles, csrf_token=new_sess.csrf_token, demo_mode=True)
