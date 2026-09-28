"""
security.py — Аутентификация, авторизация, Keycloak OIDC, аудит.

Поддерживает два режима:
  1. KEYCLOAK_ENABLED=true  — проверка JWT через Keycloak JWKS (prod).
  2. KEYCLOAK_ENABLED=false — локальный bcrypt + HS256 JWT (dev / тесты).

Соответствие требованиям ТЗ:
  • Роли: manager < head < admin
  • Keycloak (п.10 ТЗ)
  • ФЗ-152, ФЗ-117 — аудит-лог всех значимых событий
  • Отзыв токенов (logout, блокировка пользователя)
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt
import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AuditAction, AuditLog, BlockedToken, User, UserRole

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SECRET_KEY: str     = os.getenv("SECRET_KEY", "CHANGE_ME_in_production_32chars!!")
ALGORITHM: str      = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_TTL    = int(os.getenv("ACCESS_TOKEN_TTL_MINUTES", "60"))

KEYCLOAK_ENABLED: bool = os.getenv("KEYCLOAK_ENABLED", "false").lower() == "true"
KEYCLOAK_URL: str      = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
KEYCLOAK_REALM: str    = os.getenv("KEYCLOAK_REALM", "crmrt")
KEYCLOAK_CLIENT_ID: str = os.getenv("KEYCLOAK_CLIENT_ID", "crm-backend")

bearer_scheme = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Password utils (dev mode) — используем bcrypt напрямую (совместимо с bcrypt 5.x)
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT (dev mode — HS256)
# ---------------------------------------------------------------------------

def create_access_token(
    subject: str,
    role: str,
    user_id: str,
    extra: Optional[dict] = None,
) -> tuple[str, datetime]:
    """Возвращает (token, expire_at)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_TTL)
    jti = str(uuid.uuid4())
    payload = {
        "sub": subject,
        "role": role,
        "uid": user_id,
        "jti": jti,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, expire


# ---------------------------------------------------------------------------
# Keycloak JWKS (prod mode)
# ---------------------------------------------------------------------------

_jwks_cache: dict = {}


async def _get_keycloak_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    jwks_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
    _jwks_cache = resp.json()
    return _jwks_cache


async def _verify_keycloak_token(token: str) -> dict:
    """Проверяет подпись через Keycloak JWKS, возвращает payload."""
    try:
        jwks = await _get_keycloak_jwks()
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=KEYCLOAK_CLIENT_ID,
        )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Невалидный токен Keycloak: {exc}",
        )


# ---------------------------------------------------------------------------
# Общая верификация токена (авто-выбор режима)
# ---------------------------------------------------------------------------

async def _decode_token(token: str, db: AsyncSession) -> dict:
    """Декодирует токен + проверяет blacklist."""
    if KEYCLOAK_ENABLED:
        payload = await _verify_keycloak_token(token)
    else:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Невалидный токен: {exc}",
            )

    # Проверяем blacklist
    jti = payload.get("jti")
    if jti:
        blocked = await db.scalar(
            select(BlockedToken).where(BlockedToken.jti == jti)
        )
        if blocked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Токен отозван. Выполните вход заново.",
            )
    return payload


# ---------------------------------------------------------------------------
# FastAPI dependency — текущий пользователь
# ---------------------------------------------------------------------------

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация (Bearer token).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = await _decode_token(credentials.credentials, db)

    # Ищем пользователя
    user_id_raw = payload.get("uid") or payload.get("sub")
    user: User | None = None

    if KEYCLOAK_ENABLED:
        # В Keycloak sub — это UUID пользователя в Keycloak
        keycloak_sub = payload["sub"]
        user = await db.scalar(
            select(User).where(User.keycloak_sub == keycloak_sub)
        )
        if user is None:
            raise HTTPException(status_code=404, detail="Пользователь не найден в CRM.")
    else:
        try:
            uid = uuid.UUID(user_id_raw)
        except (ValueError, TypeError):
            raise HTTPException(status_code=401, detail="Некорректный UID в токене.")
        user = await db.get(User, uid)

    if user is None:
        raise HTTPException(status_code=401, detail="Пользователь не найден.")
    if user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Учётная запись заблокирована. Обратитесь к администратору.",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Учётная запись деактивирована.")

    return user


# ---------------------------------------------------------------------------
# Role guards
# ---------------------------------------------------------------------------

ROLE_LEVEL = {
    UserRole.manager: 0,
    UserRole.head:    1,
    UserRole.admin:   2,
}


def require_role(min_role: UserRole):
    """Dependency factory — проверяет минимальный уровень роли."""
    async def _dep(current_user: User = Depends(get_current_user)) -> User:
        if ROLE_LEVEL[current_user.role] < ROLE_LEVEL[min_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Требуется роль '{min_role.value}' или выше.",
            )
        return current_user
    return _dep


# Готовые зависимости
require_manager = require_role(UserRole.manager)
require_head    = require_role(UserRole.head)
require_admin   = require_role(UserRole.admin)


# ---------------------------------------------------------------------------
# Audit log helper
# ---------------------------------------------------------------------------

async def write_audit(
    db: AsyncSession,
    *,
    action: AuditAction,
    user: Optional[User] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    detail: Optional[dict | str] = None,
    request: Optional[Request] = None,
) -> None:
    """Записывает событие в audit_log. Не коммитит — вызывать до commit сессии."""
    ip = None
    ua = None
    if request:
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent")

    detail_str: str | None = None
    if isinstance(detail, dict):
        detail_str = json.dumps(detail, ensure_ascii=False, default=str)
    elif isinstance(detail, str):
        detail_str = detail

    log_entry = AuditLog(
        user_id=user.id if user else None,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        detail=detail_str,
        ip_address=ip,
        user_agent=ua,
    )
    db.add(log_entry)
