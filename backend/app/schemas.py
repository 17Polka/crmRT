"""
schemas.py — Pydantic v2 схемы для всех разделов CRM:
- Каталоги (Вузы, направления, продукты)
- Безопасность (Пользователи, логин, аудит)
- Workflow (Этапы, смена статуса, комментарии, файлы)
- Отчеты (Параметры фильтрации и выгрузки)
- Интеграции (LMS, Laravel сайт)
"""
from datetime import datetime
from typing import Optional, Any
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
    password: Optional[str] = Field(None, min_length=4,
                                    description="Пароль для входа (dev/fallback)")


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserOut(UserBase, _TimestampMixin):
    id: str
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
    direction_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# University (справочник и карточка)
# ---------------------------------------------------------------------------

class UniversityBase(BaseModel):
    name: str = Field(..., max_length=512)
    short_name: Optional[str] = None
    city: Optional[str] = None
    inn: Optional[str] = Field(None, max_length=12)
    vendor: Optional[str] = None
    software: Optional[str] = None
    contract_number: Optional[str] = None
    licence_signed: bool = False
    licence_year: Optional[int] = None
    transfer_status: Optional[str] = "Не передано"
    manager_fio: Optional[str] = None
    university_contacts: Optional[str] = None
    comment: Optional[str] = None
    direction_id: Optional[int] = None
    product_id: Optional[int] = None
    manager_id: Optional[str] = None
    current_stage_order: int = 0
    is_active: bool = True


class UniversityCreate(UniversityBase):
    pass


class UniversityUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    city: Optional[str] = None
    inn: Optional[str] = None
    vendor: Optional[str] = None
    software: Optional[str] = None
    contract_number: Optional[str] = None
    licence_signed: Optional[bool] = None
    licence_year: Optional[int] = None
    transfer_status: Optional[str] = None
    manager_fio: Optional[str] = None
    university_contacts: Optional[str] = None
    comment: Optional[str] = None
    direction_id: Optional[int] = None
    product_id: Optional[int] = None
    manager_id: Optional[str] = None
    current_stage_order: Optional[int] = None
    is_active: Optional[bool] = None


class UniversityOut(UniversityBase, _TimestampMixin):
    id: int
    direction_name: Optional[str] = None
    product_name: Optional[str] = None
    manager_name: Optional[str] = None
    stage_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Workflow Schemas
# ---------------------------------------------------------------------------

class StageBase(BaseModel):
    order: int
    name: str
    description: Optional[str] = None
    category: Optional[str] = "Общий"
    is_active: bool = True


class StageOut(StageBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class TransitionRequest(BaseModel):
    target_stage: int
    comment: Optional[str] = None


class CommentCreate(BaseModel):
    comment: str


class HistoryOut(BaseModel):
    id: int
    university_id: int
    user_name: Optional[str] = None
    from_stage: Optional[int] = None
    to_stage: int
    comment: Optional[str] = None
    action_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttachmentOut(BaseModel):
    id: int
    university_id: int
    stage_order: int
    filename: str
    file_size: int
    mime_type: Optional[str] = None
    uploaded_by: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

class ReportFilterRequest(BaseModel):
    period_from: Optional[str] = None
    period_to: Optional[str] = None
    direction_id: Optional[int] = None
    product_id: Optional[int] = None
    manager_id: Optional[str] = None
    columns: list[str] = ["name", "direction", "product", "stage", "manager"]
    format: str = "xlsx"  # xlsx, pdf, json


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class AuditLogOut(BaseModel):
    id: int
    user_id: Optional[str] = None
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
    expires_in: int
    user: Optional[UserOut] = None


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
    items: list[Any]


class MessageResponse(BaseModel):
    ok: bool
    message: str


class ImportResult(BaseModel):
    ok: bool
    created: int
    updated: int
    skipped: int
    errors: list[str] = []
