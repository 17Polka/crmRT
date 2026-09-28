"""
workflow.py — Управление этапами жизненного цикла взаимодействия с вузами.
Соответствие требованиям ТЗ:
- 14 базовых этапов с возможностью перехода вперед и назад
- Обязательный комментарий при возврате назад
- Прикрепление файлов к этапам
- Переименование и создание этапов (руководитель/администратор)
- История всех действий и комментариев
"""
import os
import shutil
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Request, status
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    University, WorkflowStage, WorkflowHistory, Attachment, User, UserRole, AuditAction, Direction
)
from app.schemas import (
    StageOut, StageBase, TransitionRequest, HistoryOut, AttachmentOut, MessageResponse
)
from app.security import (
    get_current_user, require_manager, require_head, require_admin, write_audit
)

router = APIRouter(prefix="/api/workflow", tags=["Workflow взаимодействия"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {
    "png", "jpeg", "jpg", "pdf", "zip", "gzip", "gz", "rar", "doc", "docx", "xls", "xlsx"
}


# ---------------------------------------------------------------------------
# Список и создание этапов
# ---------------------------------------------------------------------------

@router.get("/stages", response_model=List[StageOut], summary="Получить все этапы workflow")
async def get_stages(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    query = select(WorkflowStage).where(WorkflowStage.is_active == True).order_by(WorkflowStage.order)
    result = await db.scalars(query)
    return list(result.all())


@router.put("/stages/{stage_id}", response_model=StageOut, summary="Переименовать/обновить этап (Head+)")
async def update_stage(
    stage_id: int,
    data: StageBase,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_head),
):
    stage = await db.get(WorkflowStage, stage_id)
    if not stage:
        raise HTTPException(status_code=404, detail="Этап не найден")
    
    stage.name = data.name
    stage.description = data.description
    stage.category = data.category
    
    await write_audit(
        db,
        action=AuditAction.workflow_transition,
        user=current_user,
        resource_type="workflow_stage",
        resource_id=str(stage_id),
        detail={"name": data.name},
        request=request,
    )
    await db.commit()
    await db.refresh(stage)
    return stage


# ---------------------------------------------------------------------------
# Доска workflow (вузы по этапам)
# ---------------------------------------------------------------------------

@router.get("/board", summary="Данные канбан-доски workflow")
async def get_workflow_board(
    direction_id: Optional[int] = Query(None),
    product_id: Optional[int] = Query(None),
    manager_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    stages = (await db.scalars(
        select(WorkflowStage).where(WorkflowStage.is_active == True).order_by(WorkflowStage.order)
    )).all()

    query = select(University).where(University.is_active == True)
    
    # Ограничение по роли
    if current_user.role == UserRole.manager:
        query = query.where(University.manager_id == current_user.id)
    elif manager_id:
        query = query.where(University.manager_id == manager_id)

    if direction_id:
        query = query.where(University.direction_id == direction_id)
    if product_id:
        query = query.where(University.product_id == product_id)

    unis = (await db.scalars(query)).all()
    dirs_dict = {d.id: d.name for d in (await db.scalars(select(Direction))).all()}

    board = []
    for s in stages:
        stage_unis = [u for u in unis if u.current_stage_order == s.order]
        board.append({
            "stage_id": s.id,
            "order": s.order,
            "name": s.name,
            "category": s.category,
            "count": len(stage_unis),
            "universities": [
                {
                    "id": u.id,
                    "name": u.name,
                    "city": u.city,
                    "direction": dirs_dict.get(u.direction_id, "DevOps & Cloud"),
                    "software": u.software,
                    "vendor": u.vendor,
                    "contract": u.contract_number,
                    "licence_year": u.licence_year,
                    "manager_id": u.manager_id,
                    "manager_fio": u.manager_fio,
                    "current_stage": u.current_stage_order,
                    "last_update": u.updated_at.strftime("%d.%m.%Y") if u.updated_at else None,
                }
                for u in stage_unis
            ]
        })
    return board


# ---------------------------------------------------------------------------
# Перевод вуза между этапами с комментарием и файлом
# ---------------------------------------------------------------------------

@router.post("/{university_id}/transition", summary="Сменить этап вуза (вперед/назад)")
async def transition_university(
    university_id: int,
    target_stage: int = Form(...),
    comment: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    uni = await db.get(University, university_id)
    if not uni:
        raise HTTPException(status_code=404, detail="Вуз не найден")
    
    # Проверка прав менеджера
    if current_user.role == UserRole.manager and uni.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Доступ только к своим вузам")

    current_order = uni.current_stage_order
    # При возврате назад комментарий обязателен
    if target_stage < current_order and not comment:
        raise HTTPException(
            status_code=400,
            detail="Комментарий обязателен при возврате на предыдущий этап"
        )

    # Валидация файла, если прикреплен
    attachment_record = None
    if file and file.filename:
        ext = file.filename.split(".")[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Ошибка 1002: неверный формат файла .{ext}. Допустимы: png, jpg, pdf, zip, rar, docx, xlsx"
            )
        
        safe_filename = f"uni_{uni.id}_st{target_stage}_{file.filename}"
        dest_path = os.path.join(UPLOAD_DIR, safe_filename)
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        attachment_record = Attachment(
            university_id=uni.id,
            stage_order=target_stage,
            filename=file.filename,
            stored_path=dest_path,
            file_size=os.path.getsize(dest_path),
            mime_type=file.content_type,
            uploaded_by=current_user.full_name,
        )
        db.add(attachment_record)

    # Обновляем этап вуза
    uni.current_stage_order = target_stage
    
    # Записываем историю
    history_entry = WorkflowHistory(
        university_id=uni.id,
        user_id=current_user.id,
        user_name=current_user.full_name,
        from_stage=current_order,
        to_stage=target_stage,
        comment=comment,
        action_type="transition" if not file else "transition_with_file",
    )
    db.add(history_entry)

    # Аудит
    await write_audit(
        db,
        action=AuditAction.workflow_transition,
        user=current_user,
        resource_type="university",
        resource_id=str(uni.id),
        detail={"from": current_order, "to": target_stage, "comment": comment},
        request=request,
    )
    await db.commit()

    return {
        "ok": True,
        "message": f"Вуз переведен на этап {target_stage}",
        "current_stage": target_stage
    }


# ---------------------------------------------------------------------------
# История и файлы карточки вуза
# ---------------------------------------------------------------------------

@router.get("/{university_id}/history", response_model=List[HistoryOut], summary="История взаимодействий")
async def get_university_history(
    university_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    uni = await db.get(University, university_id)
    if not uni:
        raise HTTPException(status_code=404, detail="Вуз не найден")
    if current_user.role == UserRole.manager and uni.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Доступ только к своим вузам")

    query = select(WorkflowHistory).where(
        WorkflowHistory.university_id == university_id
    ).order_by(WorkflowHistory.created_at.desc())
    return list((await db.scalars(query)).all())


@router.post("/{university_id}/comment", summary="Добавить комментарий в карточку")
async def add_comment(
    university_id: int,
    comment: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    uni = await db.get(University, university_id)
    if not uni:
        raise HTTPException(status_code=404, detail="Вуз не найден")
    if current_user.role == UserRole.manager and uni.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Доступ только к своим вузам")
    
    h = WorkflowHistory(
        university_id=uni.id,
        user_id=current_user.id,
        user_name=current_user.full_name,
        from_stage=uni.current_stage_order,
        to_stage=uni.current_stage_order,
        comment=comment,
        action_type="comment",
    )
    db.add(h)
    await db.commit()
    return {"ok": True, "message": "Комментарий добавлен"}


@router.get("/{university_id}/attachments", response_model=List[AttachmentOut], summary="Список прикрепленных файлов")
async def get_attachments(
    university_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    uni = await db.get(University, university_id)
    if not uni:
        raise HTTPException(status_code=404, detail="Вуз не найден")
    if current_user.role == UserRole.manager and uni.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Доступ только к своим вузам")

    query = select(Attachment).where(
        Attachment.university_id == university_id
    ).order_by(Attachment.created_at.desc())
    return list((await db.scalars(query)).all())


@router.post("/{university_id}/attachments", response_model=AttachmentOut, summary="Загрузить файл в карточку вуза")
async def upload_attachment(
    university_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    uni = await db.get(University, university_id)
    if not uni:
        raise HTTPException(status_code=404, detail="Вуз не найден")
    if current_user.role == UserRole.manager and uni.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Доступ только к своим вузам")

    ext = file.filename.split(".")[-1].lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Ошибка 1002: неверный формат файла .{ext}. Допустимы: png, jpg, pdf, zip, rar, docx, xlsx"
        )

    safe_filename = f"uni_{uni.id}_st{uni.current_stage_order}_{file.filename}"
    dest_path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    rec = Attachment(
        university_id=uni.id,
        stage_order=uni.current_stage_order,
        filename=file.filename,
        stored_path=dest_path,
        file_size=os.path.getsize(dest_path),
        mime_type=file.content_type,
        uploaded_by=current_user.full_name,
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return rec


@router.get("/{university_id}/attachments/{attachment_id}/download", summary="Скачать прикрепленный файл")
async def download_attachment(
    university_id: int,
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    uni = await db.get(University, university_id)
    if not uni:
        raise HTTPException(status_code=404, detail="Вуз не найден")
    if current_user.role == UserRole.manager and uni.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Доступ только к своим вузам")
    
    att = await db.get(Attachment, attachment_id)
    if not att or att.university_id != university_id:
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    if not os.path.exists(att.stored_path):
        raise HTTPException(status_code=404, detail="Файл на диске не найден")
        
    from fastapi.responses import FileResponse
    return FileResponse(
        path=att.stored_path,
        filename=att.filename,
        media_type=att.mime_type or "application/octet-stream"
    )
