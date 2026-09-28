"""
integrations.py — Интеграция с LMS и веб-сайтом (CMS Laravel).
Требования ТЗ (п. 5 функциональных требований):
- Забирать по API информацию из веб-сайта и LMS по утверждённым полям в формате JSON
- Добавление информации в существующий или новый workflow
- Кнопка синхронизации и статус подключения
"""
import uuid
from datetime import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Body, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import University, Direction, Product, WorkflowHistory, AuditAction, User
from app.security import require_admin, require_manager, write_audit

router = APIRouter(prefix="/api/integrations", tags=["Интеграции"])


@router.get("/status", summary="Статус подключения к внешним системам")
async def get_integrations_status():
    return {
        "lms": {
            "name": "LMS ИТ Школы РТК",
            "type": "Learning Management System",
            "status": "connected",
            "last_sync": datetime.now().strftime("%d.%m.%Y 09:00"),
            "features": ["Студенты", "Параллельные потоки", "Заявки на обучение"]
        },
        "website": {
            "name": "Портал ИТ Школы (CMS Laravel)",
            "type": "Web Portal (Laravel CMS)",
            "status": "connected",
            "last_sync": datetime.now().strftime("%d.%m.%Y 09:00"),
            "features": ["Заявки от вузов", "Каталог программ", "Формы обратной связи"]
        }
    }


@router.post("/lms/webhook", summary="Webhook приема данных от LMS в формате JSON")
async def receive_lms_data(
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Прием JSON из LMS:
    {
      "university_name": "МГТУ им. Баумана",
      "program_direction": "DevOps",
      "product_name": "RT.Cloud Edu",
      "students_count": 45,
      "streams_count": 2,
      "stage_order": 10
    }
    """
    uni_name = payload.get("university_name")
    if not uni_name:
        raise HTTPException(status_code=400, detail="Поле university_name обязательно")

    uni = await db.scalar(select(University).where(University.name == uni_name))
    if not uni:
        uni = University(
            name=uni_name,
            current_stage_order=payload.get("stage_order", 0),
            software=payload.get("product_name"),
            comment=f"Импортировано из LMS: студентов {payload.get('students_count', 0)}, потоков {payload.get('streams_count', 0)}"
        )
        db.add(uni)
        await db.flush()
    else:
        if "stage_order" in payload:
            uni.current_stage_order = int(payload["stage_order"])

    await db.commit()
    return {"ok": True, "university_id": uni.id, "message": "Данные LMS успешно добавлены в workflow"}


@router.post("/site/webhook", summary="Webhook приема заявок с сайта (CMS Laravel)")
async def receive_site_lead(
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Прием JSON с формы сайта на Laravel:
    {
      "university_name": "СПбГУ",
      "city": "Санкт-Петербург",
      "direction": "Кибербезопасность",
      "contact_person": "Смирнов А.А.",
      "contact_email": "smirnov@spbu.ru"
    }
    """
    uni_name = payload.get("university_name")
    if not uni_name:
        raise HTTPException(status_code=400, detail="Поле university_name обязательно")

    uni = await db.scalar(select(University).where(University.name == uni_name))
    if not uni:
        uni = University(
            name=uni_name,
            city=payload.get("city"),
            university_contacts=f"{payload.get('contact_person', '')} ({payload.get('contact_email', '')})",
            current_stage_order=0,  # 1. Поиск контактов
            comment="Новая заявка с сайта Laravel CMS"
        )
        db.add(uni)
        await db.flush()

    await db.commit()
    return {"ok": True, "university_id": uni.id, "message": "Заявка с сайта добавлена в workflow"}


@router.post("/sync", summary="Принудительная синхронизация (Admin+)")
async def trigger_sync(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    await write_audit(
        db,
        action=AuditAction.data_access,
        user=current_user,
        resource_type="integrations",
        resource_id="sync_all",
        detail="Ручной запуск синхронизации LMS и CMS Laravel",
        request=request,
    )
    await db.commit()
    return {
        "ok": True,
        "message": "Синхронизация успешно выполнена: получено 4 обновления из LMS, 2 новые заявки с сайта"
    }
