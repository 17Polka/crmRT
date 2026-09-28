"""
routers/security_router.py — Раздел «Безопасность и compliance».

Эндпоинты:
  POST   /api/security/login           — получить JWT (dev-режим без Keycloak)
  POST   /api/security/logout          — отозвать токен (blacklist)
  GET    /api/security/me              — профиль текущего пользователя
  GET    /api/security/users           — список пользователей (head+)
  POST   /api/security/users           — создать пользователя (admin)
  GET    /api/security/users/{id}      — карточка пользователя (head+)
  PUT    /api/security/users/{id}      — обновить (admin)
  POST   /api/security/users/{id}/block   — заблокировать (admin)
  POST   /api/security/users/{id}/unblock — разблокировать (admin)
  GET    /api/security/audit           — журнал аудита (head+)
  GET    /api/security/audit/export    — выгрузка аудита в xlsx (admin)

Соответствие ТЗ:
  • Keycloak (п.10) — через security.py (OIDC/JWKS)
  • ФЗ-152 — аудит доступа к данным, блокировка, не удаляем логи
  • ФЗ-117 — журнал событий безопасности
"""
import io
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import openpyxl
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from jose import jwt as jose_jwt, JWTError
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AuditAction, AuditLog, BlockedToken, User, UserRole
from app.schemas import (
    AuditLogOut,
    LoginRequest,
    MessageResponse,
    PagedResponse,
    TokenOut,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    require_head,
    require_manager,
    verify_password,
    write_audit,
    KEYCLOAK_ENABLED,
    ACCESS_TOKEN_TTL,
)

router = APIRouter(prefix="/api/security", tags=["Безопасность"])


# ===========================================================================
# AUTH
# ===========================================================================

@router.post(
    "/login",
    response_model=TokenOut,
    summary="Войти (dev-режим, без Keycloak)",
    description=(
        "Используется только когда `KEYCLOAK_ENABLED=false`. "
        "В prod-среде аутентификация выполняется через Keycloak OIDC."
    ),
)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if KEYCLOAK_ENABLED:
        raise HTTPException(
            400,
            detail="Прямой логин отключён. Используйте Keycloak.",
        )

    user: User | None = await db.scalar(
        select(User).where(User.username == body.username)
    )

    if not user or not user.hashed_password:
        await write_audit(
            db, action=AuditAction.login_failed,
            detail={"username": body.username, "reason": "user_not_found"},
            request=request,
        )
        await db.commit()
        raise HTTPException(401, detail="Неверный логин или пароль.")

    if not verify_password(body.password, user.hashed_password):
        await write_audit(
            db, action=AuditAction.login_failed,
            user=user, detail={"reason": "wrong_password"},
            request=request,
        )
        await db.commit()
        raise HTTPException(401, detail="Неверный логин или пароль.")

    if user.is_blocked:
        raise HTTPException(403, detail="Учётная запись заблокирована.")
    if not user.is_active:
        raise HTTPException(403, detail="Учётная запись деактивирована.")

    token, expire_at = create_access_token(
        subject=user.username,
        role=user.role.value,
        user_id=str(user.id),
    )

    await write_audit(
        db, action=AuditAction.login,
        user=user, request=request,
    )
    await db.commit()

    ttl_seconds = int((expire_at - datetime.now(timezone.utc)).total_seconds())
    return TokenOut(access_token=token, expires_in=ttl_seconds, user=UserOut.model_validate(user))


@router.post("/logout", response_model=MessageResponse, summary="Выйти (отозвать токен)")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()

    try:
        payload = jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        exp = payload.get("exp")
    except JWTError:
        raise HTTPException(400, detail="Некорректный токен.")

    if jti:
        expire_dt = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else datetime.now(timezone.utc)
        db.add(BlockedToken(
            jti=jti,
            user_id=current_user.id,
            expire_at=expire_dt,
            reason="logout",
        ))

    await write_audit(
        db, action=AuditAction.logout,
        user=current_user, request=request,
    )
    await db.commit()
    return MessageResponse(ok=True, message="Выход выполнен.")


@router.get("/me", response_model=UserOut, summary="Профиль текущего пользователя")
async def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


# ===========================================================================
# USERS
# ===========================================================================

@router.get("/users", response_model=PagedResponse, summary="Список пользователей")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: Optional[str] = None,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_head),
):
    stmt = select(User)
    if q:
        stmt = stmt.where(
            User.full_name.ilike(f"%{q}%") | User.username.ilike(f"%{q}%")
        )
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (
        await db.scalars(
            stmt.order_by(User.full_name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    return PagedResponse(
        total=total or 0, page=page, page_size=page_size,
        items=[UserOut.model_validate(u) for u in rows],
    )


@router.post("/users", response_model=UserOut, status_code=201,
             summary="Создать пользователя")
async def create_user(
    body: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    exists = await db.scalar(
        select(User).where(
            (User.username == body.username) | (User.email == body.email)
        )
    )
    if exists:
        raise HTTPException(400, detail="Пользователь с таким логином или email уже существует.")

    hashed = hash_password(body.password) if body.password else None
    user = User(
        username=body.username,
        full_name=body.full_name,
        email=body.email,
        role=body.role,
        hashed_password=hashed,
    )
    db.add(user)
    await db.flush()

    await write_audit(
        db, action=AuditAction.role_changed,
        user=current_user, resource_type="user", resource_id=str(user.id),
        detail={"action": "created", "role": body.role.value},
        request=request,
    )
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/users/{user_id}", response_model=UserOut, summary="Карточка пользователя")
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_head),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, detail="Пользователь не найден.")
    return UserOut.model_validate(user)


@router.put("/users/{user_id}", response_model=UserOut, summary="Обновить пользователя")
async def update_user(
    user_id: str,
    body: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, detail="Пользователь не найден.")

    changes = body.model_dump(exclude_unset=True)
    old_role = user.role

    for k, v in changes.items():
        setattr(user, k, v)

    detail: dict = {"changes": changes}
    if "role" in changes and changes["role"] != old_role:
        detail["old_role"] = old_role.value

    await write_audit(
        db, action=AuditAction.role_changed,
        user=current_user, resource_type="user", resource_id=str(user_id),
        detail=detail, request=request,
    )
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/users/{user_id}/block", response_model=MessageResponse,
             summary="Заблокировать пользователя (ФЗ-152)")
async def block_user(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, detail="Пользователь не найден.")
    if user.id == current_user.id:
        raise HTTPException(400, detail="Нельзя заблокировать самого себя.")

    user.is_blocked = True
    await write_audit(
        db, action=AuditAction.user_blocked,
        user=current_user, resource_type="user", resource_id=str(user_id),
        detail={"target_username": user.username},
        request=request,
    )
    await db.commit()
    return MessageResponse(ok=True, message=f"Пользователь '{user.username}' заблокирован.")


@router.post("/users/{user_id}/unblock", response_model=MessageResponse,
             summary="Разблокировать пользователя")
async def unblock_user(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, detail="Пользователь не найден.")

    user.is_blocked = False
    await write_audit(
        db, action=AuditAction.user_unblocked,
        user=current_user, resource_type="user", resource_id=str(user_id),
        detail={"target_username": user.username},
        request=request,
    )
    await db.commit()
    return MessageResponse(ok=True, message=f"Пользователь '{user.username}' разблокирован.")


# ===========================================================================
# AUDIT LOG (Только Руководитель и Администратор, КАМ доступа не имеет)
# ===========================================================================

@router.get("/audit", response_model=PagedResponse, summary="Журнал аудита (ФЗ-152 / ФЗ-117)")
async def list_audit(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    user_id: Optional[str] = None,
    action: Optional[AuditAction] = None,
    resource_type: Optional[str] = None,
    date_from: Optional[str] = Query(None, description="ISO date: 2026-09-01"),
    date_to: Optional[str] = Query(None, description="ISO date: 2026-09-30"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_head),
):
    stmt = select(AuditLog)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        stmt = stmt.where(AuditLog.created_at <= datetime.fromisoformat(date_to + "T23:59:59"))

    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (
        await db.scalars(
            stmt.order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    # Подгружаем username
    items_out = []
    user_cache: dict[str, str] = {}
    for log in rows:
        out = AuditLogOut.model_validate(log)
        if log.user_id:
            if log.user_id not in user_cache:
                u = await db.get(User, log.user_id)
                user_cache[log.user_id] = u.username if u else "unknown"
            out.username = user_cache[log.user_id]
        items_out.append(out)

    return PagedResponse(
        total=total or 0, page=page, page_size=page_size, items=items_out
    )


@router.get(
    "/audit/export",
    summary="Выгрузка журнала аудита в xlsx (admin)",
    response_class=StreamingResponse,
)
async def export_audit_xlsx(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    action: Optional[AuditAction] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
    request: Request = None,
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        stmt = stmt.where(AuditLog.created_at <= datetime.fromisoformat(date_to + "T23:59:59"))
    if action:
        stmt = stmt.where(AuditLog.action == action)

    rows = (await db.scalars(stmt)).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Журнал аудита"

    headers = ["ID", "Дата", "Пользователь", "Действие",
               "Тип ресурса", "ID ресурса", "Детали", "IP"]
    ws.append(headers)

    user_cache: dict[str, str] = {}
    for log in rows:
        username = ""
        if log.user_id:
            if log.user_id not in user_cache:
                u = await db.get(User, log.user_id)
                user_cache[log.user_id] = u.username if u else "unknown"
            username = user_cache[log.user_id]
        ws.append([
            log.id,
            log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "",
            username,
            log.action.value,
            log.resource_type or "",
            log.resource_id or "",
            log.detail or "",
            log.ip_address or "",
        ])

    await write_audit(
        db, action=AuditAction.data_export,
        user=current_user, resource_type="audit_log",
        detail={"rows": len(rows)}, request=request,
    )
    await db.commit()

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
