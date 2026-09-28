"""
models.py — ORM-модели для разделов «Каталоги данных» и «Безопасность и compliance».

Таблицы:
  • users          — пользователи CRM (менеджеры, руководители, администраторы)
  • directions     — направления (ИТ-продукты / сегменты)
  • products       — ИТ-продукты Ростелекома
  • universities   — базовая ссылочная таблица на вузы-партнёры
  • audit_log      — лог действий (ФЗ-152, ФЗ-117, Keycloak-события)
  • blocked_tokens — таблица отозванных JWT (logout / блокировка)
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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    manager = "manager"   # менеджер по вузам (КАМ)
    head    = "head"      # руководитель — видит всё
    admin   = "admin"     # администратор — управляет системой


class AuditAction(str, enum.Enum):
    # Безопасность / compliance
    login            = "LOGIN"
    logout           = "LOGOUT"
    login_failed     = "LOGIN_FAILED"
    token_revoked    = "TOKEN_REVOKED"
    user_blocked     = "USER_BLOCKED"
    user_unblocked   = "USER_UNBLOCKED"
    role_changed     = "ROLE_CHANGED"
    password_changed = "PASSWORD_CHANGED"
    # Каталоги
    catalog_created  = "CATALOG_CREATED"
    catalog_updated  = "CATALOG_UPDATED"
    catalog_deleted  = "CATALOG_DELETED"
    catalog_imported = "CATALOG_IMPORTED"
    # Данные
    data_export      = "DATA_EXPORT"
    data_access      = "DATA_ACCESS"


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    keycloak_sub: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True,
        comment="Keycloak subject (sub) claim — внешний IdP"
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # Хэш пароля нужен только для режима без Keycloak (dev / fallback)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False, default=UserRole.manager
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_blocked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="ФЗ-152: временная блокировка при инциденте"
    )
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
# Каталог: направления
# ---------------------------------------------------------------------------

class Direction(Base):
    """Направление — группировка продуктов (напр. «Облака», «Безопасность»)."""
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
# Каталог: продукты
# ---------------------------------------------------------------------------

class Product(Base):
    """ИТ-продукт Ростелекома, привязанный к направлению."""
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
# Каталог: вузы-партнёры
# ---------------------------------------------------------------------------

class University(Base):
    """
    Справочник вузов-партнёров (карточка учебного заведения).
    История взаимодействий, этапы workflow и вложенные файлы
    хранятся в смежном сервисе — данная модель содержит только
    базовые реквизиты вуза.
    """
    __tablename__ = "universities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    inn: Mapped[str | None] = mapped_column(
        String(12), nullable=True, comment="ИНН юридического лица"
    )
    licence_year: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Год истечения лицензии"
    )
    direction_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("directions.id", ondelete="SET NULL"), nullable=True
    )
    product_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    # Ответственный менеджер
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Безопасность: аудит-лог
# ---------------------------------------------------------------------------

class AuditLog(Base):
    """
    Неизменяемый журнал действий пользователей.
    Требования: ФЗ-152 ст.19, ФЗ-117 (защита информации).
    Запись не удаляется и не изменяется — только INSERT.
    """
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action"), nullable=False
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="Тип ресурса: direction / product / university / user"
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="ID изменённого объекта"
    )
    detail: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="JSON-diff или произвольное описание"
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User | None"] = relationship(
        back_populates="audit_logs", lazy="noload"
    )


# ---------------------------------------------------------------------------
# Безопасность: отозванные токены (logout / блокировка пользователя)
# ---------------------------------------------------------------------------

class BlockedToken(Base):
    """
    Blacklist JTI (JWT Token ID) для реализации безопасного logout
    и мгновенной блокировки пользователя.
    Устаревшие записи чистятся планировщиком (expire_at < now()).
    """
    __tablename__ = "blocked_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expire_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        comment="Время истечения токена — для автоочистки"
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
