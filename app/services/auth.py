from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._users = UserRepository(session)
        self._tokens = RefreshTokenRepository(session)

    async def register(self, data: RegisterRequest, ip: Optional[str] = None) -> User:
        if await self._users.email_exists(data.email):
            raise ConflictError("Email already registered")

        return await self._users.create(
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
        )

    async def login(
        self,
        data: LoginRequest,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> TokenResponse:
        user = await self._users.get_by_email(data.email)
        if not user or not verify_password(data.password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        access_token = create_access_token(str(user.id))
        refresh_token = create_refresh_token(str(user.id))

        # Store hashed refresh token for revocation support
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        await self._tokens.create(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip,
            user_agent=user_agent,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh(self, raw_refresh_token: str) -> TokenResponse:
        token_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()
        stored = await self._tokens.get_by_hash(token_hash)
        if not stored:
            raise AuthenticationError("Invalid or expired refresh token")

        try:
            payload = decode_token(raw_refresh_token)
        except ValueError:
            raise AuthenticationError("Invalid refresh token")

        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type")

        # Rotate: revoke old, issue new pair
        await self._tokens.update(stored, is_revoked=True)

        user_id = payload["sub"]
        new_access = create_access_token(user_id)
        new_refresh = create_refresh_token(user_id)

        new_hash = hashlib.sha256(new_refresh.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        await self._tokens.create(
            user_id=stored.user_id,
            token_hash=new_hash,
            expires_at=expires_at,
        )

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def logout(self, raw_refresh_token: str) -> None:
        token_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()
        stored = await self._tokens.get_by_hash(token_hash)
        if stored:
            await self._tokens.update(stored, is_revoked=True)
