from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator


class URLCreateRequest(BaseModel):
    original_url: AnyHttpUrl
    custom_alias: Optional[str] = Field(
        default=None, min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    title: Optional[str] = Field(default=None, max_length=255)
    expires_at: Optional[datetime] = None
    is_public: bool = True

    @field_validator("expires_at")
    @classmethod
    def expiry_must_be_future(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None:
            from datetime import timezone
            if v <= datetime.now(timezone.utc):
                raise ValueError("Expiration date must be in the future")
        return v


class URLUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None


class URLResponse(BaseModel):
    id: uuid.UUID
    original_url: str
    short_code: str
    custom_alias: Optional[str]
    title: Optional[str]
    short_url: str
    owner_id: Optional[uuid.UUID]
    is_active: bool
    is_public: bool
    expires_at: Optional[datetime]
    click_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class URLListResponse(BaseModel):
    items: list[URLResponse]
    total: int
    page: int
    size: int
    pages: int
