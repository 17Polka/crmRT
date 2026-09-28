"""
models.py — ORM-модели для CRM ИТ Школы Ростелекома.

Таблицы:
  • users                  — пользователи CRM (КАМ, Руководитель, Администратор)
  • directions             — каталоги: направления обучения
  • products               — каталоги: ИТ-продукты
  • universities           — каталоги: вузы-партнеры
  • workflow_stages        — этапы workflow (14 базовых + кастомные)
  • university_workflows   — статус взаимодействия вуза с продуктом и этапом
  • workflow_history       — история переходов, комментарии и дедлайны
  • attachments            — прикрепленные файлы (документы, лицензии)
  • audit_log              — лог безопасности (ФЗ-152, ФСТЭК №117)
  • blocked_tokens         — черный список JWT
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    manager = "manager"   # Менеджер (КАМ)
    head    = "head"      # Руководитель
    admin   = "admin"     # Администратор


class AuditAction(str, enum.Enum):
    login            = "LOGIN"
    logout           = "LOGOUT"
    login_failed     = "LOGIN_FAILED"
    token_revoked    = "TOKEN_REVOKED"
    user_blocked     = "USER_BLOCKED"
    user_unblocked   = "USER_UNBLOCKED"
    role_changed     = "ROLE_CHANGED"
    password_changed = "PASSWORD_CHANGED"
    catalog_created  = "CATALOG_CREATED"
    catalog_updated  = "CATALOG_UPDATED"
    catalog_deleted  = "CATALOG_DELETED"
    catalog_imported = "CATALOG_IMPORTED"
    workflow_transition = "WORKFLOW_TRANSITION"
    data_export      = "DATA_EXPORT"
    data_access      = "DATA_ACCESS"


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    keycloak_sub: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True,
        comment="Keycloak subject (sub)"
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False, default=UserRole.manager
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="user", lazy="noload"
    )


# ---------------------------------------------------------------------------
# Каталоги: Направления
# ---------------------------------------------------------------------------

class Direction(Base):
    __tablename__ = "directions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    products: Mapped[list["Product"]] = relationship(
        back_populates="direction", lazy="noload"
    )


# ---------------------------------------------------------------------------
# Каталоги: Продукты
# ---------------------------------------------------------------------------

class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    direction_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("directions.id", ondelete="RESTRICT"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    direction: Mapped["Direction"] = relationship(
        back_populates="products", lazy="noload"
    )


# ---------------------------------------------------------------------------
# Каталоги: Вузы
# ---------------------------------------------------------------------------

class University(Base):
    __tablename__ = "universities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    inn: Mapped[str | None] = mapped_column(String(12), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    software: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contract_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    licence_signed: Mapped[bool] = mapped_column(Boolean, default=False)
    licence_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transfer_status: Mapped[str | None] = mapped_column(String(128), nullable=True, default="Не передано")
    manager_fio: Mapped[str | None] = mapped_column(String(255), nullable=True)
    university_contacts: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    direction_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("directions.id", ondelete="SET NULL"), nullable=True
    )
    product_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    manager_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    current_stage_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Workflow: Этапы (14 базовых по ТЗ + кастомные)
# ---------------------------------------------------------------------------

class WorkflowStage(Base):
    __tablename__ = "workflow_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True, default="Общий")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ---------------------------------------------------------------------------
# Workflow: История переходов, комментарии
# ---------------------------------------------------------------------------

class WorkflowHistory(Base):
    __tablename__ = "workflow_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    university_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("universities.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    from_stage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_stage: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_type: Mapped[str] = mapped_column(String(32), default="transition") # transition, comment, file
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ---------------------------------------------------------------------------
# Вложения / Файлы (п. 3 функциональных требований)
# ---------------------------------------------------------------------------

class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    university_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("universities.id", ondelete="CASCADE"), nullable=False
    )
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ---------------------------------------------------------------------------
# Безопасность: Аудит-лог (152-ФЗ, ФСТЭК №117)
# ---------------------------------------------------------------------------

class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action"), nullable=False
    )
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User | None"] = relationship(
        back_populates="audit_logs", lazy="noload"
    )


# ---------------------------------------------------------------------------
# Безопасность: Отозванные токены
# ---------------------------------------------------------------------------

class BlockedToken(Base):
    __tablename__ = "blocked_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expire_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
