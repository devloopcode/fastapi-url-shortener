from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import decode_token
from app.dependencies.db import DBSession
from app.models.user import User, UserRole
from app.repositories.user import UserRepository

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    session: DBSession,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    if not credentials:
        raise AuthenticationError("Missing authentication token")

    try:
        payload = decode_token(credentials.credentials)
    except ValueError:
        raise AuthenticationError("Invalid or expired token")

    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token payload")

    repo = UserRepository(session)
    user = await repo.get_by_id(uuid.UUID(user_id))
    if not user or not user.is_active:
        raise AuthenticationError("User not found or inactive")

    return user


async def get_optional_user(
    session: DBSession,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Optional[User]:
    if not credentials:
        return None
    try:
        return await get_current_user(session, credentials)
    except (AuthenticationError, Exception):
        return None


def require_role(*roles: UserRole):
    async def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in [r.value for r in roles]:
            raise AuthorizationError("Insufficient permissions")
        return user
    return _checker


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[Optional[User], Depends(get_optional_user)]
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]
