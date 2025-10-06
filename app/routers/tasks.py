# app/routers/tasks.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
from sqlalchemy import select, update, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.deps import get_db, get_current_user
from app.models import (
    TaskCategory, TaskTemplate, TaskApplication,
    Resident, UserResidence, Residence, User, Bed
)
from app.schemas import (
    TaskCategoryCreate, TaskCategoryUpdate, TaskCategoryOut,
    TaskTemplateCreate, TaskTemplateUpdate, TaskTemplateOut,
    TaskApplicationCreate, TaskApplicationUpdate, TaskApplicationOut,
    TaskApplicationBatchRequest, TaskApplicationBatchResponse,
    TaskApplicationDailySummary, TaskApplicationDetail, TaskApplicationResidentDay, UserAssigner,
    VoiceParseRequest, VoiceParseResponse, VoiceApplicationRequest, VoiceApplicationResponse,
    PaginationParams, PaginatedResponse, FilterParams
)
from app.security import new_uuid, decrypt_data
from app.services.voice_service import VoiceService

router = APIRouter(prefix="/tasks", tags=["tasks"])

# -------------------- helpers --------------------

async def _set_residence_context(
    db: AsyncSession,
    current: dict,
    residence_id: str | None,
) -> str | None:
    """
    Fija app.residence_id si viene y valida pertenencia, salvo superadmin.
    Devuelve rid (puede ser None si superadmin no envía cabecera).
    """
    rid = residence_id
    if rid:
        if current["role"] != "superadmin":
            ok = await db.execute(
                select(UserResidence).where(
                    UserResidence.user_id == current["id"],
                    UserResidence.residence_id == rid,
                )
            )
            if ok.scalar_one_or_none() is None:
                raise HTTPException(status_code=403, detail="Residence not allowed for this user")
        await db.execute(text("SELECT set_config('app.residence_id', :rid, true)"), {"rid": rid})
    return rid

def _can_edit_delete(current: dict, owner_id: str | None = None) -> bool:
    if current["role"] == "superadmin":
        return True
    if current["role"] == "manager":
        return True
    # professional: sólo lo suyo (para aplicaciones)
    return owner_id is not None and current["id"] == owner_id

def _status_text_from_index(tpl: TaskTemplate, idx: int | None) -> str | None:
    if idx is None:
        return None
    if idx < 1 or idx > 6:
        raise HTTPException(status_code=400, detail="selected_status_index must be 1..6")
    mapping = {1: tpl.status1, 2: tpl.status2, 3: tpl.status3,
               4: tpl.status4, 5: tpl.status5, 6: tpl.status6}
    return mapping.get(idx)

async def get_category_or_404(category_id: str, db: AsyncSession) -> TaskCategory:
    """Get category by ID or raise 404"""
    result = await db.execute(
        select(TaskCategory).where(TaskCategory.id == category_id, TaskCategory.deleted_at.is_(None))
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category

async def get_template_or_404(template_id: str, db: AsyncSession) -> TaskTemplate:
    """Get template by ID or raise 404"""
    result = await db.execute(
        select(TaskTemplate).where(TaskTemplate.id == template_id, TaskTemplate.deleted_at.is_(None))
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

async def get_application_or_404(application_id: str, db: AsyncSession) -> TaskApplication:
    """Get application by ID or raise 404"""
    result = await db.execute(
        select(TaskApplication).where(TaskApplication.id == application_id, TaskApplication.deleted_at.is_(None))
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application

async def paginate_query_tasks(
    query,
    db: AsyncSession,
    pagination: PaginationParams,
    filter_params: FilterParams = None
) -> PaginatedResponse:
    """Apply pagination and filters to a tasks query"""

    if filter_params:
        if filter_params.date_from:
            query = query.where(query.column_descriptions[0]['type'].created_at >= filter_params.date_from)
        if filter_params.date_to:
            query = query.where(query.column_descriptions[0]['type'].created_at <= filter_params.date_to)
        if filter_params.search:
            search_term = f"%{filter_params.search}%"
            if hasattr(query.column_descriptions[0]['type'], 'name'):
                query = query.where(query.column_descriptions[0]['type'].name.ilike(search_term))

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    if pagination.sort_by:
        sort_field = getattr(query.column_descriptions[0]['type'], pagination.sort_by, query.column_descriptions[0]['type'].created_at)
        if pagination.sort_order == 'desc':
            sort_field = sort_field.desc()
        query = query.order_by(sort_field)
    else:
        query = query.order_by(query.column_descriptions[0]['type'].created_at.desc())

    offset = (pagination.page - 1) * pagination.size
    query = query.offset(offset).limit(pagination.size)

    result = await db.execute(query)
    objects = result.scalars().all()
    
    # Convert model objects to dictionaries and add residence name
    items = []
    for obj in objects:
        if hasattr(obj, '__table__'):
            # Es un modelo SQLAlchemy
            item = {column.name: getattr(obj, column.name) for column in obj.__table__.columns}
            
            # Agregar nombre de residencia si es TaskCategory
            if hasattr(obj, 'residence_id'):
                residence_result = await db.execute(
                    select(Residence.name).where(Residence.id == obj.residence_id)
                )
                residence_name = residence_result.scalar()
                item['residence_name'] = residence_name
            
            # Agregar nombre de categoría si es TaskTemplate
            if hasattr(obj, 'task_category_id'):
                category_result = await db.execute(
                    select(TaskCategory.name).where(TaskCategory.id == obj.task_category_id)
                )
                category_name = category_result.scalar()
                item['category_name'] = category_name
            
            # Agregar información del creador si existe
            if hasattr(obj, 'created_by') and obj.created_by:
                creator_result = await db.execute(
                    select(User.name, User.alias_encrypted).where(User.id == obj.created_by)
                )
                creator = creator_result.first()
                if creator:
                    creator_alias = decrypt_data(creator[1]) if creator[1] else "N/A"
                    item['created_by_info'] = {
                        "id": obj.created_by,
                        "name": creator[0],
                        "alias": creator_alias
                    }
            
            items.append(item)
        else:
            # Es otro tipo de objeto
            items.append(dict(obj))

    pages = (total + pagination.size - 1) // pagination.size
    has_next = pagination.page < pages
    has_prev = pagination.page > 1

    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )

# -------------------- CATEGORIES --------------------

@router.post("/categories", response_model=TaskCategoryOut, status_code=201)
async def create_category(
    payload: TaskCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    if current["role"] not in ("superadmin", "manager"):
        raise HTTPException(status_code=403, detail="Only manager/superadmin can create categories")
    
    rid = payload.residence_id
    if not rid:
        raise HTTPException(status_code=428, detail="residence_id is required")

    # Validar que el usuario tenga acceso a esta residencia (salvo superadmin)
    if current["role"] != "superadmin":
        from app.models import UserResidence
        ok = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == rid,
            )
        )
        if ok.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Residence not allowed for this user")

    # Configurar el contexto de residencia para RLS
    rid = await _set_residence_context(db, current, rid)

    # nombre único por residencia
    exists = await db.scalar(
        select(TaskCategory.id).where(TaskCategory.residence_id == rid,
                                      TaskCategory.name == payload.name,
                                      TaskCategory.deleted_at.is_(None))
    )
    if exists:
        raise HTTPException(status_code=409, detail="Category name already exists in residence")

    tc = TaskCategory(
        id=new_uuid(), 
        residence_id=rid, 
        name=payload.name,
        created_by=current["id"]
    )
    db.add(tc)
    await db.commit()
    await db.refresh(tc)
    
    # Obtener información del usuario creador
    from app.models import User
    creator_result = await db.execute(
        select(User.name, User.alias_encrypted).where(User.id == current["id"])
    )
    creator = creator_result.first()
    created_by_info = None
    if creator:
        from app.security import decrypt_data
        creator_alias = decrypt_data(creator[1]) if creator[1] else "N/A"
        created_by_info = {
            "id": current["id"],
            "name": creator[0],
            "alias": creator_alias
        }
    
    # Construir respuesta manualmente
    return {
        "id": tc.id,
        "residence_id": tc.residence_id,
        "name": tc.name,
        "created_by_info": created_by_info,
        "created_at": tc.created_at,
        "updated_at": tc.updated_at,
        "deleted_at": tc.deleted_at
    }

@router.get("/categories", response_model=PaginatedResponse[TaskCategoryOut])
async def list_categories(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
) -> PaginatedResponse[TaskCategoryOut]:
    query = select(TaskCategory).where(TaskCategory.deleted_at.is_(None))

    if current["role"] != "superadmin":
        # Gestores y profesionales: mostrar categorías de sus residencias asignadas
        user_residences_result = await db.execute(
            select(UserResidence.residence_id).where(
                UserResidence.user_id == current["id"],
                UserResidence.deleted_at.is_(None)
            )
        )
        allowed_residence_ids = [row[0] for row in user_residences_result.all()]

        if not allowed_residence_ids:
            raise HTTPException(status_code=403, detail="No residences assigned")

        # Si se proporciona residence_id, verificar que el usuario tenga acceso
        if residence_id:
            if residence_id not in allowed_residence_ids:
                raise HTTPException(status_code=403, detail="Access denied to this residence")
            query = query.where(TaskCategory.residence_id == residence_id)
        else:
            # Sin residence_id: mostrar categorías de todas las residencias asignadas
            query = query.where(TaskCategory.residence_id.in_(allowed_residence_ids))
    elif residence_id:
        # Superadmin con residence_id específico: filtrar por esa residencia
        query = query.where(TaskCategory.residence_id == residence_id)

    if filters and filters.search:
        search_term = f"%{filters.search}%"
        query = query.where(TaskCategory.name.ilike(search_term))

    return await paginate_query_tasks(query, db, pagination, filters)

@router.get("/categories/simple", response_model=list[TaskCategoryOut])
async def list_categories_simple(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
):
    """Legacy endpoint: List categories without pagination"""
    conds = [TaskCategory.deleted_at.is_(None)]
    
    if current["role"] != "superadmin":
        # Gestores y profesionales: mostrar categorías de sus residencias asignadas
        user_residences_result = await db.execute(
            select(UserResidence.residence_id).where(
                UserResidence.user_id == current["id"],
                UserResidence.deleted_at.is_(None)
            )
        )
        allowed_residence_ids = [row[0] for row in user_residences_result.all()]

        if not allowed_residence_ids:
            raise HTTPException(status_code=403, detail="No residences assigned")

        # Si se proporciona residence_id, verificar que el usuario tenga acceso
        if residence_id:
            if residence_id not in allowed_residence_ids:
                raise HTTPException(status_code=403, detail="Access denied to this residence")
            conds.append(TaskCategory.residence_id == residence_id)
        else:
            # Sin residence_id: mostrar categorías de todas las residencias asignadas
            conds.append(TaskCategory.residence_id.in_(allowed_residence_ids))
    elif residence_id:
        # Superadmin con residence_id específico: filtrar por esa residencia
        conds.append(TaskCategory.residence_id == residence_id)

    q = await db.execute(select(TaskCategory).where(and_(*conds)).order_by(TaskCategory.name))
    return q.scalars().all()

@router.put("/categories/{category_id}", response_model=TaskCategoryOut)
async def update_category(
    category_id: str,
    payload: TaskCategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Update a category"""
    if current["role"] not in ("superadmin", "manager"):
        raise HTTPException(status_code=403, detail="Only manager/superadmin can update categories")

    category = await get_category_or_404(category_id, db)

    update_data = payload.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)

    await db.commit()
    await db.refresh(category)
    return category

@router.patch("/categories/{category_id}", response_model=TaskCategoryOut)
async def patch_category(
    category_id: str,
    payload: TaskCategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Patch a category (legacy endpoint)"""
    return await update_category(category_id, payload, db, current)

@router.delete("/categories/{category_id}", status_code=204)
async def delete_category(
    category_id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    if current["role"] not in ("superadmin", "manager"):
        raise HTTPException(status_code=403, detail="Only manager/superadmin can delete categories")

    q = await db.execute(select(TaskCategory).where(TaskCategory.id == category_id, TaskCategory.deleted_at.is_(None)))
    cat = q.scalar_one_or_none()
    if not cat:
        return
    await db.execute(
        update(TaskCategory).where(TaskCategory.id == category_id).values(deleted_at=func.now(), updated_at=func.now())
    )
    await db.commit()

# -------------------- TEMPLATES --------------------

@router.post("/templates", response_model=TaskTemplateOut, status_code=201)
async def create_template(
    payload: TaskTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    if current["role"] not in ("superadmin", "manager"):
        raise HTTPException(status_code=403, detail="Only manager/superadmin can create templates")
    
    rid = payload.residence_id
    if not rid:
        raise HTTPException(status_code=428, detail="residence_id is required")

    # Validar que el usuario tenga acceso a esta residencia (salvo superadmin)
    if current["role"] != "superadmin":
        from app.models import UserResidence
        ok = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == rid,
            )
        )
        if ok.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Residence not allowed for this user")

    # Configurar el contexto de residencia para RLS
    rid = await _set_residence_context(db, current, rid)

    # comprobar categoría pertenece a la misma residencia
    c = await db.scalar(
        select(TaskCategory.residence_id).where(TaskCategory.id == payload.task_category_id, TaskCategory.deleted_at.is_(None))
    )
    if not c or c != rid:
        raise HTTPException(status_code=400, detail="Category not found in this residence")

    # nombre único por categoría dentro de la residencia
    exists = await db.scalar(
        select(TaskTemplate.id).where(TaskTemplate.residence_id == rid,
                                      TaskTemplate.task_category_id == payload.task_category_id,
                                      TaskTemplate.name == payload.name,
                                      TaskTemplate.deleted_at.is_(None))
    )
    if exists:
        raise HTTPException(status_code=409, detail="Template name already exists in this category")

    t = TaskTemplate(
        id=new_uuid(),
        residence_id=rid,
        task_category_id=payload.task_category_id,
        name=payload.name,
        status1=payload.status1, status2=payload.status2, status3=payload.status3,
        status4=payload.status4, status5=payload.status5, status6=payload.status6,
        audio_phrase=payload.audio_phrase,
        is_block=payload.is_block,
        created_by=current["id"]
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    
    # Obtener información del usuario creador
    from app.models import User
    creator_result = await db.execute(
        select(User.name, User.alias_encrypted).where(User.id == current["id"])
    )
    creator = creator_result.first()
    created_by_info = None
    if creator:
        from app.security import decrypt_data
        creator_alias = decrypt_data(creator[1]) if creator[1] else "N/A"
        created_by_info = {
            "id": current["id"],
            "name": creator[0],
            "alias": creator_alias
        }
    
    # Construir respuesta manualmente
    return {
        "id": t.id,
        "residence_id": t.residence_id,
        "task_category_id": t.task_category_id,
        "name": t.name,
        "status1": t.status1,
        "status2": t.status2,
        "status3": t.status3,
        "status4": t.status4,
        "status5": t.status5,
        "status6": t.status6,
        "audio_phrase": t.audio_phrase,
        "is_block": t.is_block,
        "created_by_info": created_by_info,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
        "deleted_at": t.deleted_at
    }

@router.get("/templates", response_model=PaginatedResponse[TaskTemplateOut])
async def list_templates(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
    category_id: str | None = Query(None),
) -> PaginatedResponse[TaskTemplateOut]:
    query = select(TaskTemplate).where(TaskTemplate.deleted_at.is_(None))

    if current["role"] != "superadmin":
        # Gestores y profesionales: mostrar templates de sus residencias asignadas
        user_residences_result = await db.execute(
            select(UserResidence.residence_id).where(
                UserResidence.user_id == current["id"],
                UserResidence.deleted_at.is_(None)
            )
        )
        allowed_residence_ids = [row[0] for row in user_residences_result.all()]

        if not allowed_residence_ids:
            raise HTTPException(status_code=403, detail="No residences assigned")

        # Si se proporciona residence_id, verificar que el usuario tenga acceso
        if residence_id:
            if residence_id not in allowed_residence_ids:
                raise HTTPException(status_code=403, detail="Access denied to this residence")
            query = query.where(TaskTemplate.residence_id == residence_id)
        else:
            # Sin residence_id: mostrar templates de todas las residencias asignadas
            query = query.where(TaskTemplate.residence_id.in_(allowed_residence_ids))
    elif residence_id:
        # Superadmin con residence_id específico: filtrar por esa residencia
        query = query.where(TaskTemplate.residence_id == residence_id)
    if category_id:
        query = query.where(TaskTemplate.task_category_id == category_id)

    if filters and filters.search:
        search_term = f"%{filters.search}%"
        query = query.where(TaskTemplate.name.ilike(search_term))

    return await paginate_query_tasks(query, db, pagination, filters)

@router.get("/templates/simple", response_model=list[TaskTemplateOut])
async def list_templates_simple(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
    category_id: str | None = Query(None),
):
    """Legacy endpoint: List templates without pagination"""
    conds = [TaskTemplate.deleted_at.is_(None)]
    
    if current["role"] != "superadmin":
        # Gestores y profesionales: mostrar templates de sus residencias asignadas
        user_residences_result = await db.execute(
            select(UserResidence.residence_id).where(
                UserResidence.user_id == current["id"],
                UserResidence.deleted_at.is_(None)
            )
        )
        allowed_residence_ids = [row[0] for row in user_residences_result.all()]

        if not allowed_residence_ids:
            raise HTTPException(status_code=403, detail="No residences assigned")

        # Si se proporciona residence_id, verificar que el usuario tenga acceso
        if residence_id:
            if residence_id not in allowed_residence_ids:
                raise HTTPException(status_code=403, detail="Access denied to this residence")
            conds.append(TaskTemplate.residence_id == residence_id)
        else:
            # Sin residence_id: mostrar templates de todas las residencias asignadas
            conds.append(TaskTemplate.residence_id.in_(allowed_residence_ids))
    elif residence_id:
        # Superadmin con residence_id específico: filtrar por esa residencia
        conds.append(TaskTemplate.residence_id == residence_id)
    if category_id:
        conds.append(TaskTemplate.task_category_id == category_id)

    q = await db.execute(select(TaskTemplate).where(and_(*conds)).order_by(TaskTemplate.name))
    return q.scalars().all()

@router.patch("/templates/{template_id}", response_model=TaskTemplateOut)
async def update_template(
    template_id: str,
    payload: TaskTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    if current["role"] not in ("superadmin", "manager"):
        raise HTTPException(status_code=403, detail="Only manager/superadmin can update templates")

    q = await db.execute(select(TaskTemplate).where(TaskTemplate.id == template_id, TaskTemplate.deleted_at.is_(None)))
    tpl = q.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")

    # si cambia de categoría, validar que sea misma residencia
    new_cat = tpl.task_category_id if payload.task_category_id is None else payload.task_category_id
    if new_cat != tpl.task_category_id:
        c_res = await db.scalar(
            select(TaskCategory.residence_id).where(TaskCategory.id == new_cat, TaskCategory.deleted_at.is_(None))
        )
        if not c_res or c_res != tpl.residence_id:
            raise HTTPException(status_code=400, detail="New category not in same residence")

    values = {
        "task_category_id": new_cat,
        "name": payload.name if payload.name is not None else tpl.name,
        "status1": tpl.status1 if payload.status1 is None else payload.status1,
        "status2": tpl.status2 if payload.status2 is None else payload.status2,
        "status3": tpl.status3 if payload.status3 is None else payload.status3,
        "status4": tpl.status4 if payload.status4 is None else payload.status4,
        "status5": tpl.status5 if payload.status5 is None else payload.status5,
        "status6": tpl.status6 if payload.status6 is None else payload.status6,
        "audio_phrase": tpl.audio_phrase if payload.audio_phrase is None else payload.audio_phrase,
        "is_block": tpl.is_block if payload.is_block is None else payload.is_block,
        "updated_at": func.now(),
    }
    await db.execute(update(TaskTemplate).where(TaskTemplate.id == template_id).values(**values))
    await db.commit()
    q2 = await db.execute(select(TaskTemplate).where(TaskTemplate.id == template_id))
    return q2.scalar_one()

@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    if current["role"] not in ("superadmin", "manager"):
        raise HTTPException(status_code=403, detail="Only manager/superadmin can delete templates")

    q = await db.execute(select(TaskTemplate).where(TaskTemplate.id == template_id, TaskTemplate.deleted_at.is_(None)))
    tpl = q.scalar_one_or_none()
    if not tpl:
        return
    await db.execute(
        update(TaskTemplate).where(TaskTemplate.id == template_id).values(deleted_at=func.now(), updated_at=func.now())
    )
    await db.commit()

# -------------------- APPLICATIONS (aplicar tarea) --------------------

@router.post("/applications", response_model=TaskApplicationOut, status_code=201)
async def apply_task(
    payload: TaskApplicationCreate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
):
    # Fijar/validar residencia
    rid = await _set_residence_context(db, current, residence_id)
    if not rid and current["role"] != "superadmin":
        raise HTTPException(status_code=428, detail="Select a residence (residence_id)")

    # Validar residente pertenece a residencia
    r_res = await db.scalar(
        select(Resident.residence_id).where(Resident.id == payload.resident_id, Resident.deleted_at.is_(None))
    )
    if not r_res:
        raise HTTPException(status_code=400, detail="Resident not found")
    if rid and r_res != rid:
        raise HTTPException(status_code=400, detail="Resident not in selected residence")
    if not rid:
        # superadmin sin header: usar la del residente
        rid = r_res
        await db.execute(text("SELECT set_config('app.residence_id', :rid, true)"), {"rid": rid})

    # Validar template pertenece a misma residencia
    t_res = await db.scalar(
        select(TaskTemplate.residence_id).where(TaskTemplate.id == payload.task_template_id,
                                                TaskTemplate.deleted_at.is_(None))
    )
    if not t_res:
        raise HTTPException(status_code=400, detail="Template not found")
    if t_res != rid:
        raise HTTPException(status_code=400, detail="Template not in selected residence")

    # Resolver status text si se envió índice
    qtpl = await db.execute(select(TaskTemplate).where(TaskTemplate.id == payload.task_template_id))
    tpl = qtpl.scalar_one()
    status_text = payload.selected_status_text
    if payload.selected_status_index is not None and not status_text:
        status_text = _status_text_from_index(tpl, payload.selected_status_index)

    app = TaskApplication(
        id=new_uuid(),
        residence_id=rid,
        resident_id=payload.resident_id,
        task_template_id=payload.task_template_id,
        applied_by=current["id"],
        applied_at=payload.applied_at or func.now(),
        selected_status_index=payload.selected_status_index,
        selected_status_text=status_text,
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    
    # Obtener información del usuario que aplicó la tarea
    from app.models import User
    applier_result = await db.execute(
        select(User.name, User.alias_encrypted).where(User.id == current["id"])
    )
    applier = applier_result.first()
    applied_by_info = None
    if applier:
        from app.security import decrypt_data
        applier_alias = decrypt_data(applier[1]) if applier[1] else "N/A"
        applied_by_info = {
            "id": current["id"],
            "name": applier[0],
            "alias": applier_alias
        }
    
    # Construir respuesta manualmente
    return {
        "id": app.id,
        "residence_id": app.residence_id,
        "resident_id": app.resident_id,
        "task_template_id": app.task_template_id,
        "applied_by_info": applied_by_info,
        "applied_at": app.applied_at,
        "selected_status_index": app.selected_status_index,
        "selected_status_text": app.selected_status_text,
        "created_at": app.created_at,
        "updated_at": app.updated_at,
        "deleted_at": app.deleted_at
    }

@router.get("/applications", response_model=PaginatedResponse[TaskApplicationOut])
async def list_applications(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
    resident_id: str | None = Query(None, description="Filter by resident ID"),
    template_id: str | None = Query(None, description="Filter by template ID"),
    category_id: str | None = Query(None, description="Filter by category ID"),
) -> PaginatedResponse[TaskApplicationOut]:
    rid = await _set_residence_context(db, current, residence_id)

    # Si necesitamos filtrar por categoría, hacer JOIN con TaskTemplate
    if category_id:
        query = select(TaskApplication).join(TaskTemplate, TaskApplication.task_template_id == TaskTemplate.id).where(
            TaskApplication.deleted_at.is_(None),
            TaskTemplate.deleted_at.is_(None)
        )
    else:
        query = select(TaskApplication).where(TaskApplication.deleted_at.is_(None))

    if current["role"] != "superadmin":
        if rid:
            # Usuario con residence_id específico: filtrar por esa residencia
            query = query.where(TaskApplication.residence_id == rid)
        else:
            # Usuario sin residence_id: mostrar tareas de todas sus residencias asignadas
            user_residences_result = await db.execute(
                select(UserResidence.residence_id).where(
                    UserResidence.user_id == current["id"]
                )
            )
            allowed_residence_ids = [row[0] for row in user_residences_result.all()]
            
            if not allowed_residence_ids:
                raise HTTPException(status_code=403, detail="No residences assigned")
            
            query = query.where(TaskApplication.residence_id.in_(allowed_residence_ids))
    elif rid:
        # Superadmin con residence_id específico: filtrar por esa residencia
        query = query.where(TaskApplication.residence_id == rid)
    if resident_id:
        query = query.where(TaskApplication.resident_id == resident_id)
    if template_id:
        query = query.where(TaskApplication.task_template_id == template_id)
    if category_id:
        query = query.where(TaskTemplate.task_category_id == category_id)

    if filters and filters.date_from:
        query = query.where(TaskApplication.applied_at >= filters.date_from)
    if filters and filters.date_to:
        query = query.where(TaskApplication.applied_at <= filters.date_to)

    # Debug: verificar la consulta
    print(f"DEBUG: Query final: {query}")
    result = await db.execute(query.limit(5))  # Solo 5 para debug
    debug_items = result.scalars().all()
    print(f"DEBUG: Found {len(debug_items)} items")
    
    return await paginate_query_tasks(query, db, pagination, filters)

@router.get("/applications/simple", response_model=list[TaskApplicationOut])
async def list_applications_simple(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
    resident_id: str | None = Query(None, description="Filter by resident ID"),
    template_id: str | None = Query(None, description="Filter by template ID"),
    category_id: str | None = Query(None, description="Filter by category ID"),
    limit: int = Query(100, ge=1, le=1000),
):
    """Legacy endpoint: List applications without pagination"""
    rid = await _set_residence_context(db, current, residence_id)

    # Si necesitamos filtrar por categoría, hacer JOIN con TaskTemplate
    if category_id:
        query = select(TaskApplication).join(TaskTemplate, TaskApplication.task_template_id == TaskTemplate.id)
        conds = [
            TaskApplication.deleted_at.is_(None),
            TaskTemplate.deleted_at.is_(None)
        ]
    else:
        query = select(TaskApplication)
        conds = [TaskApplication.deleted_at.is_(None)]

    if current["role"] != "superadmin":
        if rid:
            # Usuario con residence_id específico: filtrar por esa residencia
            conds.append(TaskApplication.residence_id == rid)
        else:
            # Usuario sin residence_id: mostrar tareas de todas sus residencias asignadas
            user_residences_result = await db.execute(
                select(UserResidence.residence_id).where(
                    UserResidence.user_id == current["id"]
                )
            )
            allowed_residence_ids = [row[0] for row in user_residences_result.all()]
            
            if not allowed_residence_ids:
                raise HTTPException(status_code=403, detail="No residences assigned")
            
            conds.append(TaskApplication.residence_id.in_(allowed_residence_ids))
    elif rid:
        # Superadmin con residence_id específico: filtrar por esa residencia
        conds.append(TaskApplication.residence_id == rid)
    if resident_id:
        conds.append(TaskApplication.resident_id == resident_id)
    if template_id:
        conds.append(TaskApplication.task_template_id == template_id)
    if category_id:
        conds.append(TaskTemplate.task_category_id == category_id)

    q = await db.execute(
        query.where(and_(*conds)).order_by(TaskApplication.applied_at.desc()).limit(limit)
    )
    return q.scalars().all()

@router.patch("/applications/{application_id}", response_model=TaskApplicationOut)
async def update_application(
    application_id: str,
    payload: TaskApplicationUpdate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    q = await db.execute(select(TaskApplication).where(TaskApplication.id == application_id,
                                                       TaskApplication.deleted_at.is_(None)))
    app = q.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if not _can_edit_delete(current, owner_id=app.applied_by):
        raise HTTPException(status_code=403, detail="You cannot edit this application")

    new_index = app.selected_status_index if payload.selected_status_index is None else payload.selected_status_index
    new_text = app.selected_status_text if payload.selected_status_text is None else payload.selected_status_text

    if payload.selected_status_index is not None and payload.selected_status_text is None:
        # si sólo cambia el índice, recalcular texto desde el template
        qtpl = await db.execute(select(TaskTemplate).where(TaskTemplate.id == app.task_template_id))
        tpl = qtpl.scalar_one()
        new_text = _status_text_from_index(tpl, payload.selected_status_index)

    values = {
        "selected_status_index": new_index,
        "selected_status_text": new_text,
        "applied_at": payload.applied_at if payload.applied_at is not None else app.applied_at,
        "updated_at": func.now(),
    }
    await db.execute(update(TaskApplication).where(TaskApplication.id == application_id).values(**values))
    await db.commit()

    q2 = await db.execute(select(TaskApplication).where(TaskApplication.id == application_id))
    return q2.scalar_one()

@router.delete("/applications/{application_id}", status_code=204)
async def delete_application(
    application_id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    q = await db.execute(select(TaskApplication).where(TaskApplication.id == application_id,
                                                       TaskApplication.deleted_at.is_(None)))
    app = q.scalar_one_or_none()
    if not app:
        return
    if not _can_edit_delete(current, owner_id=app.applied_by):
        raise HTTPException(status_code=403, detail="You cannot delete this application")

    await db.execute(
        update(TaskApplication).where(TaskApplication.id == application_id).values(deleted_at=func.now(),
                                                                                   updated_at=func.now())
    )
    await db.commit()

# -------------------- Additional Endpoints --------------------

@router.get("/residents/{resident_id}/task-applications", response_model=PaginatedResponse[TaskApplicationOut])
async def get_task_applications_by_resident(
    resident_id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    pagination: PaginationParams = Depends(),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
    category_id: str | None = Query(None, description="Filter by category ID"),
    template_id: str | None = Query(None, description="Filter by template ID"),
    time_filter: str = Query("all", description="Time filter: 7d|15d|30d|1y|all"),
) -> PaginatedResponse[TaskApplicationOut]:
    """
    Get task applications for a specific resident with time filters and category information.
    
    Time filters:
    - 7d: Last 7 days
    - 15d: Last 15 days  
    - 30d: Last 30 days
    - 1y: Last year
    - all: All applications
    """
    from datetime import datetime, timedelta
    
    # Validate time filter
    valid_filters = ["7d", "15d", "30d", "1y", "all"]
    if time_filter not in valid_filters:
        raise HTTPException(status_code=400, detail=f"Invalid time_filter. Must be one of: {valid_filters}")
    
    # Apply residence context
    rid = await _set_residence_context(db, current, residence_id)
    
    # Validate resident exists and belongs to residence
    resident_check = await db.scalar(
        select(Resident.id).where(
            Resident.id == resident_id,
            Resident.deleted_at.is_(None)
        )
    )
    if not resident_check:
        raise HTTPException(status_code=404, detail="Resident not found")
    
    # Get resident's residence_id if not provided
    if not rid:
        resident_residence = await db.scalar(
            select(Resident.residence_id).where(Resident.id == resident_id)
        )
        rid = resident_residence
    
    # Validate user has access to this residence
    if current["role"] != "superadmin":
        user_residence_check = await db.scalar(
            select(UserResidence.residence_id).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == rid
            )
        )
        if not user_residence_check:
            raise HTTPException(status_code=403, detail="Access denied to this resident's residence")
    
    # Build query with joins to get category and resident information
    query = select(
        TaskApplication,
        TaskTemplate.name.label("task_template_name"),
        TaskTemplate.task_category_id.label("task_category_id"),
        TaskCategory.name.label("task_category_name"),
        Resident.full_name.label("resident_full_name")
    ).join(
        TaskTemplate, TaskApplication.task_template_id == TaskTemplate.id
    ).join(
        TaskCategory, TaskTemplate.task_category_id == TaskCategory.id
    ).join(
        Resident, TaskApplication.resident_id == Resident.id
    ).where(
        TaskApplication.resident_id == resident_id,
        TaskApplication.residence_id == rid,
        TaskApplication.deleted_at.is_(None),
        TaskTemplate.deleted_at.is_(None),
        TaskCategory.deleted_at.is_(None),
        Resident.deleted_at.is_(None)
    )
    
    # Apply time filter
    if time_filter != "all":
        now = datetime.utcnow()
        time_deltas = {
            "7d": timedelta(days=7),
            "15d": timedelta(days=15),
            "30d": timedelta(days=30),
            "1y": timedelta(days=365)
        }
        date_from = now - time_deltas[time_filter]
        query = query.where(TaskApplication.applied_at >= date_from)
    
    # Apply category filter
    if category_id:
        query = query.where(TaskCategory.id == category_id)
    
    # Apply template filter
    if template_id:
        query = query.where(TaskTemplate.id == template_id)
    
    # Order by most recent first
    query = query.order_by(TaskApplication.applied_at.desc())
    
    # Execute query with pagination
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    offset = (pagination.page - 1) * pagination.size
    result = await db.execute(query.offset(offset).limit(pagination.size))
    
    items = []
    for row in result.all():
        app, template_name, category_id_val, category_name, resident_full_name = row
        
        # Get applied_by_info
        applied_by_info = None
        if app.applied_by:
            applier_result = await db.execute(
                select(User.name, User.alias_encrypted).where(User.id == app.applied_by)
            )
            applier = applier_result.first()
            if applier:
                from app.security import decrypt_data
                applier_alias = decrypt_data(applier[1]) if applier[1] else "N/A"
                applied_by_info = {
                    "id": app.applied_by,
                    "name": applier[0],
                    "alias": applier_alias
                }
        
        # Build item dictionary
        item_dict = {
            "id": app.id,
            "residence_id": app.residence_id,
            "resident_id": app.resident_id,
            "resident_full_name": resident_full_name,
            "task_template_id": app.task_template_id,
            "task_template_name": template_name,
            "task_category_id": category_id_val,
            "task_category_name": category_name,
            "applied_by_info": applied_by_info,
            "applied_at": app.applied_at,
            "selected_status_index": app.selected_status_index,
            "selected_status_text": app.selected_status_text,
            "created_at": app.created_at,
            "updated_at": app.updated_at,
            "deleted_at": app.deleted_at
        }
        items.append(item_dict)
    
    # Calculate pagination metadata
    pages = (total + pagination.size - 1) // pagination.size
    has_next = pagination.page < pages
    has_prev = pagination.page > 1
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.post("/applications/batch", response_model=TaskApplicationBatchResponse)
async def create_task_applications_batch(
    payload: TaskApplicationBatchRequest,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user)
) -> TaskApplicationBatchResponse:
    """
    Crea aplicaciones de tareas en lote para múltiples residentes.
    
    Crea una aplicación de tarea por cada combinación de resident_id × task_template_id.
    Ejemplo: 3 residentes × 3 tareas = 9 registros creados.
    
    Args:
        payload: Solicitud con resident_ids, task_template_ids y residence_id
    """
    # Validar que todos los resident_ids pertenecen a la residencia
    residents_query = select(Resident).where(
        Resident.id.in_(payload.resident_ids),
        Resident.residence_id == payload.residence_id,
        Resident.deleted_at.is_(None)
    )
    residents_result = await db.execute(residents_query)
    valid_residents = residents_result.scalars().all()
    
    if len(valid_residents) != len(payload.resident_ids):
        raise HTTPException(
            status_code=400, 
            detail="Algunos resident_ids no pertenecen a la residencia especificada o no existen"
        )
    
    # Validar que todas las task_template_ids existen
    templates_query = select(TaskTemplate).where(
        TaskTemplate.id.in_(payload.task_template_ids),
        TaskTemplate.residence_id == payload.residence_id,
        TaskTemplate.deleted_at.is_(None)
    )
    templates_result = await db.execute(templates_query)
    valid_templates = templates_result.scalars().all()
    
    if len(valid_templates) != len(payload.task_template_ids):
        raise HTTPException(
            status_code=400, 
            detail="Algunas task_template_ids no existen en la residencia especificada"
        )
    
    # Usar transacción para rollback en caso de error
    try:
        applications = []
        
        # Crear aplicación por cada combinación resident × template
        for resident in valid_residents:
            for template in valid_templates:
                # 1. Obtener el status seleccionado por el usuario (si existe)
                status_text = None
                status_index = None
                
                if payload.task_statuses:
                    status_text = payload.task_statuses.get(template.id)
                    
                    # 2. Buscar en qué campo (status1-6) está ese texto
                    if status_text:
                        if template.status1 == status_text:
                            status_index = 1
                        elif template.status2 == status_text:
                            status_index = 2
                        elif template.status3 == status_text:
                            status_index = 3
                        elif template.status4 == status_text:
                            status_index = 4
                        elif template.status5 == status_text:
                            status_index = 5
                        elif template.status6 == status_text:
                            status_index = 6
                
                # 3. Crear la aplicación con el status seleccionado (o sin status)
                application = TaskApplication(
                    id=str(uuid.uuid4()),
                    residence_id=payload.residence_id,
                    resident_id=resident.id,
                    task_template_id=template.id,
                    applied_by=current["id"],
                    selected_status_index=status_index,  # Índice del campo (1-6) o None
                    selected_status_text=status_text,    # Texto del status o None
                    applied_at=datetime.now(timezone.utc)
                )
                db.add(application)
                applications.append(application)
        
        # Commit de la transacción
        await db.commit()
        
        # Consultar las aplicaciones creadas con datos completos para la respuesta
        applications_query = select(
            TaskApplication,
            Resident.full_name.label("resident_name"),
            TaskTemplate.name.label("task_template_name"),
            TaskCategory.name.label("task_category_name"),
            User.name.label("applied_by_name")
        ).join(
            Resident, TaskApplication.resident_id == Resident.id
        ).join(
            TaskTemplate, TaskApplication.task_template_id == TaskTemplate.id
        ).join(
            TaskCategory, TaskTemplate.task_category_id == TaskCategory.id
        ).join(
            User, TaskApplication.applied_by == User.id
        ).where(
            TaskApplication.residence_id == payload.residence_id,
            TaskApplication.resident_id.in_(payload.resident_ids),
            TaskApplication.task_template_id.in_(payload.task_template_ids)
        ).order_by(TaskApplication.applied_at.desc())
        
        result = await db.execute(applications_query)
        rows = result.all()
        
        # Convertir a TaskApplicationOut
        response_applications = []
        for row in rows:
            application, resident_name, template_name, category_name, applied_by_name = row
            app_dict = {
                "id": application.id,
                "residence_id": application.residence_id,
                "resident_id": application.resident_id,
                "resident_name": resident_name,
                "task_template_id": application.task_template_id,
                "task_template_name": template_name,
                "task_category_id": None,  # Se puede obtener del template si es necesario
                "task_category_name": category_name,
                "applied_by": application.applied_by,
                "applied_by_name": applied_by_name,
                "status": application.selected_status_text,
                "comments": None,  # Campo no existe en el modelo
                "applied_at": application.applied_at,
                "selected_status_index": application.selected_status_index,
                "selected_status_text": application.selected_status_text,
                "created_at": application.created_at,
                "updated_at": application.updated_at,
                "deleted_at": application.deleted_at
            }
            response_applications.append(TaskApplicationOut(**app_dict))
        
        return TaskApplicationBatchResponse(
            created_count=len(response_applications),
            applications=response_applications
        )
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear aplicaciones en lote: {str(e)}"
        )


# -------------------- ENDPOINTS DE HISTORIAL --------------------

@router.get("/applications/daily-summary", response_model=PaginatedResponse[TaskApplicationDailySummary])
async def get_task_applications_daily_summary(
    residence_id: str = Query(..., description="ID de la residencia"),
    date_from: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    assigned_by_id: Optional[str] = Query(None, description="ID del profesional/gestor que asignó"),
    search: Optional[str] = Query(None, description="Buscar por nombre de residente"),
    page: int = Query(1, ge=1, description="Número de página"),
    size: int = Query(20, ge=1, le=100, description="Tamaño de página"),
    sort_by: Optional[str] = Query(None, description="Campo para ordenar"),
    sort_order: Optional[str] = Query("desc", description="Orden: asc o desc"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user)
) -> PaginatedResponse[TaskApplicationDailySummary]:
    """
    Obtiene resumen diario de aplicaciones de tareas por residente.
    
    Agrupa las aplicaciones por residente y fecha, mostrando estadísticas
    de cuántas tareas se aplicaron cada día.
    
    Si no se proporcionan date_from y date_to, retorna TODO el historial.
    """
    # Validar formato de fechas solo si se proporcionan
    start_date = None
    end_date = None
    
    if date_from:
        try:
            start_date = datetime.strptime(date_from, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="date_from debe estar en formato YYYY-MM-DD")
    
    if date_to:
        try:
            end_date = datetime.strptime(date_to, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="date_to debe estar en formato YYYY-MM-DD")
    
    # Construir query base con JOINs
    query = select(
        Resident.id.label("resident_id"),
        Resident.full_name.label("resident_full_name"),
        Bed.name.label("bed_name"),
        func.date(TaskApplication.applied_at).label("date"),
        func.count(TaskApplication.id).label("task_count"),
        func.array_agg(func.distinct(TaskTemplate.name)).label("task_types"),
        func.min(func.to_char(TaskApplication.applied_at, 'HH24:MI:SS')).label("first_application_time"),
        func.max(func.to_char(TaskApplication.applied_at, 'HH24:MI:SS')).label("last_application_time")
    ).select_from(
        TaskApplication.__table__
        .join(Resident.__table__, TaskApplication.resident_id == Resident.id)
        .join(Bed.__table__, Resident.bed_id == Bed.id, isouter=True)
        .join(TaskTemplate.__table__, TaskApplication.task_template_id == TaskTemplate.id)
    ).where(
        TaskApplication.residence_id == residence_id,
        TaskApplication.deleted_at.is_(None),
        Resident.deleted_at.is_(None)
    )
    
    # Aplicar filtros de fecha solo si se proporcionan
    if start_date:
        query = query.where(func.date(TaskApplication.applied_at) >= start_date)
    
    if end_date:
        query = query.where(func.date(TaskApplication.applied_at) <= end_date)
    
    # Filtrar por assigned_by_id si se proporciona
    if assigned_by_id:
        query = query.where(TaskApplication.applied_by == assigned_by_id)
    
    # Filtrar por búsqueda de nombre de residente
    if search:
        search_term = f"%{search}%"
        query = query.where(Resident.full_name.ilike(search_term))
    
    # Agrupar y ordenar
    query = query.group_by(
        Resident.id,
        Resident.full_name,
        Bed.name,
        func.date(TaskApplication.applied_at)
    )
    
    # Aplicar ordenamiento
    if sort_by == "resident_name":
        if sort_order == "asc":
            query = query.order_by(Resident.full_name.asc(), func.date(TaskApplication.applied_at).desc())
        else:
            query = query.order_by(Resident.full_name.desc(), func.date(TaskApplication.applied_at).desc())
    elif sort_by == "task_count":
        if sort_order == "asc":
            query = query.order_by(func.count(TaskApplication.id).asc(), func.date(TaskApplication.applied_at).desc())
        else:
            query = query.order_by(func.count(TaskApplication.id).desc(), func.date(TaskApplication.applied_at).desc())
    else:
        # Ordenamiento por defecto: fecha DESC, luego nombre ASC
        query = query.order_by(
            func.date(TaskApplication.applied_at).desc(),
            Resident.full_name.asc()
        )
    
    # Usar parámetros de paginación directos en lugar de PaginationParams
    offset = (page - 1) * size
    query = query.offset(offset).limit(size)
    
    # Ejecutar query
    result = await db.execute(query)
    rows = result.all()
    
    # Contar total para paginación
    count_query = select(func.count()).select_from(
        TaskApplication.__table__
        .join(Resident.__table__, TaskApplication.resident_id == Resident.id)
        .join(TaskTemplate.__table__, TaskApplication.task_template_id == TaskTemplate.id)
    ).where(
        TaskApplication.residence_id == residence_id,
        TaskApplication.deleted_at.is_(None),
        Resident.deleted_at.is_(None)
    )
    
    # Aplicar los mismos filtros al count
    if start_date:
        count_query = count_query.where(func.date(TaskApplication.applied_at) >= start_date)
    
    if end_date:
        count_query = count_query.where(func.date(TaskApplication.applied_at) <= end_date)
    
    if assigned_by_id:
        count_query = count_query.where(TaskApplication.applied_by == assigned_by_id)
    
    if search:
        search_term = f"%{search}%"
        count_query = count_query.where(Resident.full_name.ilike(search_term))
    
    count_query = count_query.group_by(
        Resident.id,
        func.date(TaskApplication.applied_at)
    )
    
    count_result = await db.execute(count_query)
    total = len(count_result.all())
    
    # Convertir a objetos TaskApplicationDailySummary
    items = []
    for row in rows:
        summary_dict = {
            "resident_id": str(row.resident_id),
            "resident_full_name": row.resident_full_name,
            "bed_name": row.bed_name,
            "date": str(row.date),
            "task_count": row.task_count,
            "task_types": row.task_types or [],
            "first_application_time": row.first_application_time,
            "last_application_time": row.last_application_time
        }
        items.append(TaskApplicationDailySummary(**summary_dict))
    
    # Calcular metadatos de paginación
    pages = (total + size - 1) // size
    has_next = page < pages
    has_prev = page > 1
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.get("/applications/resident/{resident_id}/date/{date}", response_model=TaskApplicationResidentDay)
async def get_task_applications_by_resident_date(
    resident_id: str,
    date: str,
    assigned_by_id: Optional[str] = Query(None, description="ID del profesional/gestor que asignó las tareas"),
    residence_id: str = Query(..., description="ID de la residencia"),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user)
) -> TaskApplicationResidentDay:
    """
    Obtiene todas las aplicaciones de tareas de un residente en una fecha específica.
    
    Muestra el detalle completo de todas las tareas asignadas al residente
    en el día especificado, ordenadas por hora de asignación.
    
    Si assigned_by_id está presente, solo retorna las tareas creadas/asignadas
    por ese profesional o gestor específico.
    
    Si assigned_by_id es None, retorna todas las tareas de ese día.
    """
    # Validar formato de fecha
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="La fecha debe estar en formato YYYY-MM-DD")
    
    # Construir query con JOINs para obtener datos completos
    query = select(
        TaskApplication,
        Resident.full_name.label("resident_full_name"),
        Bed.name.label("bed_name"),
        TaskTemplate.name.label("task_name"),
        TaskCategory.name.label("task_category"),
        User.name.label("assigned_by_name"),
        User.role.label("assigned_by_role")
    ).join(
        Resident, TaskApplication.resident_id == Resident.id
    ).join(
        Bed, Resident.bed_id == Bed.id, isouter=True
    ).join(
        TaskTemplate, TaskApplication.task_template_id == TaskTemplate.id
    ).join(
        TaskCategory, TaskTemplate.task_category_id == TaskCategory.id
    ).join(
        User, TaskApplication.applied_by == User.id
    ).where(
        TaskApplication.residence_id == residence_id,
        TaskApplication.resident_id == resident_id,
        func.date(TaskApplication.applied_at) == target_date,
        TaskApplication.deleted_at.is_(None),
        Resident.deleted_at.is_(None),
        User.deleted_at.is_(None)
    )
    
    # Filtrar por assigned_by_id si se proporciona
    if assigned_by_id:
        query = query.where(TaskApplication.applied_by == assigned_by_id)
    
    query = query.order_by(TaskApplication.applied_at.asc())
    
    # Ejecutar query
    result = await db.execute(query)
    rows = result.all()
    
    if not rows:
        raise HTTPException(status_code=404, detail="No se encontraron aplicaciones para este residente en la fecha especificada")
    
    # Obtener información del residente del primer resultado
    first_row = rows[0]
    resident_name = first_row.resident_full_name
    bed_name = first_row.bed_name
    
    # Convertir aplicaciones a TaskApplicationDetail
    applications = []
    for row in rows:
        application, _, _, task_name, task_category, assigned_by_name, assigned_by_role = row
        app_dict = {
            "id": application.id,
            "task_template_id": application.task_template_id,
            "task_name": task_name,
            "task_category": task_category,
            "status": application.selected_status_text,
            "assigned_at": application.applied_at,
            "assigned_by_id": application.applied_by,
            "assigned_by_name": assigned_by_name,
            "assigned_by_role": assigned_by_role
        }
        applications.append(TaskApplicationDetail(**app_dict))
    
    # Crear respuesta
    response_dict = {
        "resident_id": resident_id,
        "resident_full_name": resident_name,
        "bed_name": bed_name,
        "date": date,
        "applications": applications
    }
    
    return TaskApplicationResidentDay(**response_dict)


@router.get("/users/assigners", response_model=List[UserAssigner])
async def get_user_assigners(
    residence_id: str = Query(..., description="ID de la residencia"),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user)
) -> List[UserAssigner]:
    """
    Obtiene lista de usuarios que pueden asignar tareas en la residencia.
    
    Retorna profesionales y gestores que tienen permisos para asignar tareas.
    """
    # Query para obtener usuarios con roles que pueden asignar tareas
    query = select(
        User.id,
        User.name,
        User.role
    ).join(
        UserResidence, User.id == UserResidence.user_id
    ).where(
        UserResidence.residence_id == residence_id,
        User.role.in_(["professional", "manager", "superadmin"]),
        User.deleted_at.is_(None),
        UserResidence.deleted_at.is_(None)
    ).order_by(User.name.asc())
    
    result = await db.execute(query)
    rows = result.all()
    
    # Convertir a UserAssigner
    assigners = []
    for row in rows:
        assigner_dict = {
            "id": row.id,
            "full_name": row.name,
            "role": row.role
        }
        assigners.append(UserAssigner(**assigner_dict))
    
    return assigners


# -------------------- VOICE RECOGNITION ENDPOINTS --------------------

@router.post("/applications/parse-voice", response_model=VoiceParseResponse)
async def parse_voice_transcript(
    payload: VoiceParseRequest,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user)
) -> VoiceParseResponse:
    """
    Parsea un transcript de voz usando Dialogflow y encuentra residente/tarea con fuzzy matching
    """
    try:
        # Validar que el usuario tenga acceso a la residencia
        if current["role"] != "superadmin":
            user_residence_check = await db.scalar(
                select(UserResidence.residence_id).where(
                    UserResidence.user_id == current["id"],
                    UserResidence.residence_id == payload.residence_id
                )
            )
            if not user_residence_check:
                return VoiceParseResponse(
                    success=False,
                    error="No tienes acceso a esta residencia"
                )
        
        # Inicializar servicio de voz
        voice_service = VoiceService()
        
        # Parsear transcript con Dialogflow
        dialogflow_result = await voice_service.parse_transcript(payload.transcript)
        
        resident_name = dialogflow_result.get("resident_name", "")
        task_name = dialogflow_result.get("task_name", "")
        status = dialogflow_result.get("status", "")
        
        # Validar que se extrajeron las entidades requeridas
        if not resident_name:
            return VoiceParseResponse(
                success=False,
                error="No se pudo identificar el nombre del residente en el audio"
            )
        
        if not task_name:
            return VoiceParseResponse(
                success=False,
                error="No se pudo identificar el nombre de la tarea en el audio"
            )
        
        # Buscar residente con fuzzy matching
        resident_match = await voice_service.find_resident_by_name(
            resident_name, payload.residence_id, db
        )

        if not resident_match:
            return VoiceParseResponse(
                success=False,
                error=f"No se encontró residente con el nombre '{resident_name}' en esta residencia"
            )

        # Verificar tipo de resultado: (id, name, None) | (None, error, None) | (None, None, options)
        if resident_match[0] is None and resident_match[1] is not None:
            # Error de validación
            return VoiceParseResponse(
                success=False,
                error=resident_match[1]
            )

        if resident_match[0] is None and resident_match[2] is not None:
            # Ambigüedad - retornar opciones
            return VoiceParseResponse(
                success=False,
                resident_options=resident_match[2]
            )

        resident_id, matched_resident_name, _ = resident_match

        # Buscar tarea con fuzzy matching
        task_match = await voice_service.find_task_by_name(
            task_name, payload.residence_id, db
        )

        if not task_match:
            return VoiceParseResponse(
                success=False,
                error=f"No se encontró tarea con el nombre '{task_name}' en esta residencia"
            )

        # Verificar tipo de resultado
        if task_match[0] is None and task_match[2] is not None:
            # Ambigüedad - retornar opciones
            return VoiceParseResponse(
                success=False,
                task_options=task_match[2]
            )

        task_id, matched_task_name, _ = task_match

        # Validar status si se proporcionó
        matched_status = None
        if status:
            status_result = await voice_service.validate_task_status(task_id, status, db)

            if status_result:
                # Verificar tipo de resultado: (matched, None, None) | (None, error, None) | (None, None, options)
                if status_result[0] is None and status_result[1] is not None:
                    # Error de validación
                    return VoiceParseResponse(
                        success=False,
                        error=status_result[1]
                    )

                if status_result[0] is None and status_result[2] is not None:
                    # Ambigüedad - retornar opciones
                    return VoiceParseResponse(
                        success=False,
                        status_options=status_result[2]
                    )

                matched_status = status_result[0]

        # Verificar si la tarea tiene estados definidos
        template_query = select(TaskTemplate).where(TaskTemplate.id == task_id)
        template_result = await db.execute(template_query)
        template = template_result.scalar_one()

        has_statuses = any([
            template.status1, template.status2, template.status3,
            template.status4, template.status5, template.status6
        ])

        # Generar mensaje de confirmación con el estado matched (no el original)
        confirmation_message = voice_service.generate_confirmation_message(
            matched_resident_name, matched_task_name, matched_status, has_statuses
        )

        return VoiceParseResponse(
            success=True,
            resident_id=resident_id,
            resident_name=matched_resident_name,
            task_id=task_id,
            task_name=matched_task_name,
            status=matched_status,
            confirmation_message=confirmation_message
        )
        
    except Exception as e:
        return VoiceParseResponse(
            success=False,
            error=f"Error al procesar el audio: {str(e)}"
        )


@router.post("/applications/voice", response_model=VoiceApplicationResponse)
async def create_voice_application(
    payload: VoiceApplicationRequest,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user)
) -> VoiceApplicationResponse:
    """
    Crea una aplicación de tarea basada en los datos parseados por voz
    """
    try:
        # Validar que el usuario tenga acceso a la residencia
        if current["role"] != "superadmin":
            user_residence_check = await db.scalar(
                select(UserResidence.residence_id).where(
                    UserResidence.user_id == current["id"],
                    UserResidence.residence_id == payload.residence_id
                )
            )
            if not user_residence_check:
                return VoiceApplicationResponse(
                    success=False,
                    error="No tienes acceso a esta residencia"
                )
        
        # Validar que el residente existe y pertenece a la residencia
        resident_query = select(Resident).where(
            Resident.id == payload.resident_id,
            Resident.residence_id == payload.residence_id,
            Resident.deleted_at.is_(None)
        )
        resident_result = await db.execute(resident_query)
        resident = resident_result.scalar_one_or_none()
        
        if not resident:
            return VoiceApplicationResponse(
                success=False,
                error="Residente no encontrado o no pertenece a esta residencia"
            )
        
        # Validar que la tarea existe y pertenece a la residencia
        task_query = select(TaskTemplate).where(
            TaskTemplate.id == payload.task_id,
            TaskTemplate.residence_id == payload.residence_id,
            TaskTemplate.deleted_at.is_(None)
        )
        task_result = await db.execute(task_query)
        task_template = task_result.scalar_one_or_none()
        
        if not task_template:
            return VoiceApplicationResponse(
                success=False,
                error="Tarea no encontrada o no pertenece a esta residencia"
            )
        
        # Determinar status_index si se proporcionó status
        status_index = None
        if payload.status:
            if task_template.status1 == payload.status: status_index = 1
            elif task_template.status2 == payload.status: status_index = 2
            elif task_template.status3 == payload.status: status_index = 3
            elif task_template.status4 == payload.status: status_index = 4
            elif task_template.status5 == payload.status: status_index = 5
            elif task_template.status6 == payload.status: status_index = 6
        
        # Crear la aplicación de tarea
        application = TaskApplication(
            id=str(uuid.uuid4()),
            residence_id=payload.residence_id,
            resident_id=payload.resident_id,
            task_template_id=payload.task_id,
            applied_by=current["id"],
            applied_at=datetime.now(timezone.utc),
            selected_status_index=status_index,
            selected_status_text=payload.status,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        db.add(application)
        await db.commit()
        await db.refresh(application)
        
        return VoiceApplicationResponse(
            success=True,
            application_id=application.id
        )
        
    except Exception as e:
        await db.rollback()
        return VoiceApplicationResponse(
            success=False,
            error=f"Error al crear la aplicación: {str(e)}"
        )
