"""
main.py — Точка входа объединенного FastAPI-бэкенда CRM ИТ Школы Ростелекома.
Соответствие ТЗ:
- Каталоги: вузы, направления, продукты
- Workflow: 14 этапов жизненного цикла взаимодействия
- Отчёты: выгрузка в XLSX, PDF, JSON
- Безопасность: Keycloak OIDC + JWT, роли (КАМ, Руководитель, Администратор), ФЗ-152, ФСТЭК №117
- Интеграции: LMS и портал на CMS Laravel
- Статика: раздача файлов вложений и фронтенда
"""
import os
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import engine, Base
from app.routers.catalogs import router as catalogs_router
from app.routers.security_router import router as security_router
from app.routers.workflow import router as workflow_router
from app.routers.reports import router as reports_router
from app.routers.integrations import router as integrations_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создаём таблицы при старте
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Фоновая очистка отозванных токенов
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


app = FastAPI(
    title="CRM ИТ Школы Ростелекома — Единая платформа",
    description=(
        "Комплексная система контроля и обработки статистических данных по обучению студентов ВУЗов и школ по ИТ направлениям.\n\n"
        "### Соответствие ТЗ:\n"
        "• **14 этапов Workflow** взаимодействия с вузами\n"
        "• **Каталоги**: Вузы, ИТ-направления, Продукты, Ответственные менеджеры (КАМ)\n"
        "• **Отчёты**: генерация за период в XLSX, PDF и результирующем JSON\n"
        "• **Файлы**: вложения к этапам (png, jpeg, pdf, zip, docx, xlsx)\n"
        "• **Безопасность**: ФЗ-152, ФСТЭК №117 (аудит-лог), Keycloak OIDC SSO\n"
        "• **Интеграции**: API для LMS и веб-сайта на CMS Laravel\n"
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Разрешаем все origins для удобства тестирования и интеграции
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(workflow_router)
app.include_router(catalogs_router)
app.include_router(reports_router)
app.include_router(security_router)
app.include_router(integrations_router)

# Раздача загруженных вложений
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


from fastapi.responses import FileResponse

# Раздача фронтенда (HTML, CSS, JS) для работы на ПК и мобильных устройствах
FRONTEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if not os.path.exists(os.path.join(FRONTEND_DIR, "head.html")):
    for cand in [os.getcwd(), os.path.dirname(os.path.dirname(__file__)), "/app"]:
        if os.path.exists(os.path.join(cand, "head.html")):
            FRONTEND_DIR = cand
            break

@app.get("/", summary="Главная страница CRM")
async def index():
    index_path = os.path.join(FRONTEND_DIR, "head.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "CRM API backend is running"}

@app.get("/head.html", summary="Главная страница CRM")
async def head_html():
    return FileResponse(os.path.join(FRONTEND_DIR, "head.html"))

@app.get("/css_styles.css", summary="Стили интерфейса")
async def css_styles():
    return FileResponse(os.path.join(FRONTEND_DIR, "css_styles.css"), media_type="text/css")

@app.get("/logic.js", summary="Скрипт логики интерфейса")
async def logic_js():
    return FileResponse(os.path.join(FRONTEND_DIR, "logic.js"), media_type="application/javascript")


@app.get("/health", tags=["Служебные"], summary="Healthcheck")
async def health():
    return {
        "status": "ok",
        "service": "crm-rt-unified",
        "version": "2.0.0",
        "time": datetime.now(timezone.utc).isoformat()
    }
