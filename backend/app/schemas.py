"""
schemas.py — Pydantic v2 схемы для разделов «Каталоги» и «Безопасность».
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models import AuditAction, UserRole


# ---------------------------------------------------------------------------
# Shared mixin
# ---------------------------------------------------------------------------

class _TimestampMixin(BaseModel):
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    full_name: str = Field(..., max_length=255)
    email: EmailStr
    role: UserRole = UserRole.manager


class UserCreate(UserBase):
    password: Optional[str] = Field(None, min_length=8,
                                    description="Пароль нужен только в dev-режиме (без Keycloak)")


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserOut(UserBase, _TimestampMixin):
    id: uuid.UUID
    is_active: bool
    is_blocked: bool
    keycloak_sub: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Direction
# ---------------------------------------------------------------------------

class DirectionBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    is_active: bool = True


class DirectionCreate(DirectionBase):
    pass


class DirectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class DirectionOut(DirectionBase, _TimestampMixin):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

class ProductBase(BaseModel):
    name: str = Field(..., max_length=255)
    vendor: Optional[str] = None
    description: Optional[str] = None
    direction_id: int
    is_active: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    vendor: Optional[str] = None
    description: Optional[str] = None
    direction_id: Optional[int] = None
    is_active: Optional[bool] = None


class ProductOut(ProductBase, _TimestampMixin):
    id: int
    direction_name: Optional[str] = None  # JOIN-поле

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# University (справочник)
# ---------------------------------------------------------------------------

class UniversityBase(BaseModel):
    name: str = Field(..., max_length=512)
    short_name: Optional[str] = None
    city: Optional[str] = None
    inn: Optional[str] = Field(None, max_length=12)
    licence_year: Optional[int] = None
    direction_id: Optional[int] = None
    product_id: Optional[int] = None
    manager_id: Optional[uuid.UUID] = None
    stage_index: int = 0
    contract: Optional[str] = None
    is_active: bool = True


class UniversityCreate(UniversityBase):
    pass


class UniversityUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    city: Optional[str] = None
    inn: Optional[str] = None
    licence_year: Optional[int] = None
    direction_id: Optional[int] = None
    product_id: Optional[int] = None
    manager_id: Optional[uuid.UUID] = None
    stage_index: Optional[int] = None
    contract: Optional[str] = None
    is_active: Optional[bool] = None


class UniversityOut(UniversityBase, _TimestampMixin):
    id: int
    direction_name: Optional[str] = None
    product_name: Optional[str] = None
    manager_name: Optional[str] = None
    history_json: Optional[str] = None
    comments_json: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class AuditLogOut(BaseModel):
    id: int
    user_id: Optional[uuid.UUID] = None
    username: Optional[str] = None
    action: AuditAction
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    detail: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Auth / tokens
# ---------------------------------------------------------------------------

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # секунды


class LoginRequest(BaseModel):
    username: str
    password: str


# ---------------------------------------------------------------------------
# Generic responses
# ---------------------------------------------------------------------------

class PagedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list


class MessageResponse(BaseModel):
    ok: bool
    message: str


class ImportResult(BaseModel):
    ok: bool
    created: int
    updated: int
    skipped: int
    errors: list[str] = []
