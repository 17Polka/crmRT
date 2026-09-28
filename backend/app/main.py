"""
main.py — точка входа FastAPI-приложения.

Запуск:
  uvicorn app.main:app --reload --port 8000
"""
import os
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routers.catalogs import router as catalogs_router
from app.routers.security_router import router as security_router


# ---------------------------------------------------------------------------
# Lifespan — создание таблиц при старте (dev), очистка old blacklisted tokens
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создаём таблицы если нет (в prod используй Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Фоновая задача: чистка истёкших заблокированных токенов каждые 10 минут
    async def _cleanup_tokens():
        from app.database import AsyncSessionLocal
        from app.models import BlockedToken
        from sqlalchemy import delete
        while True:
            await asyncio.sleep(600)
            try:
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        delete(BlockedToken).where(
                            BlockedToken.expire_at < datetime.now(timezone.utc)
                        )
                    )
                    await db.commit()
            except Exception:
                pass

    task = asyncio.create_task(_cleanup_tokens())
    yield
    task.cancel()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CRM ИТ Школы Ростелекома — Каталоги и Безопасность",
    description=(
        "Backend-сервис для разделов **Каталоги данных** и **Безопасность и compliance**.\n\n"
        "### Роли\n"
        "| Роль | Уровень | Возможности |\n"
        "|------|---------|-------------|\n"
        "| `manager` | 0 | Чтение справочников, просмотр своих вузов |\n"
        "| `head` | 1 | Всё выше + создание/редактирование каталогов, просмотр всех вузов и пользователей |\n"
        "| `admin` | 2 | Всё + удаление, импорт, управление пользователями, выгрузка аудита |\n\n"
        "### Соответствие требованиям\n"
        "- **ФЗ-152** (персональные данные): аудит доступа, блокировка пользователей\n"
        "- **ФЗ-117** (защита информации): журнал событий безопасности\n"
        "- **Keycloak** (п.10 ТЗ): OIDC/JWKS-верификация в prod (`KEYCLOAK_ENABLED=true`)\n"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — разрешаем запросы от фронтенд-сервисов (порт 3000 — workflow-сервис, 5173 — Vite dev)
origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:8080",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(catalogs_router)
app.include_router(security_router)


@app.get("/health", tags=["Служебные"], summary="Healthcheck")
async def health():
    return {"status": "ok", "service": "crm-catalogs-security", "time": datetime.now(timezone.utc)}
