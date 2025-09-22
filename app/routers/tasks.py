# app/routers/tasks.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
from sqlalchemy import select, update, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user
from app.models import (
    TaskCategory, TaskTemplate, TaskApplication,
    Resident, UserResidence, Residence, User
)
from app.schemas import (
    TaskCategoryCreate, TaskCategoryUpdate, TaskCategoryOut,
    TaskTemplateCreate, TaskTemplateUpdate, TaskTemplateOut,
    TaskApplicationCreate, TaskApplicationUpdate, TaskApplicationOut,
    PaginationParams, PaginatedResponse, FilterParams
)
from app.security import new_uuid, decrypt_data

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

@router.get("/categories", response_model=PaginatedResponse)
async def list_categories(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
):
    rid = await _set_residence_context(db, current, residence_id)
    query = select(TaskCategory).where(TaskCategory.deleted_at.is_(None))

    if current["role"] != "superadmin":
        if not rid:
            raise HTTPException(status_code=428, detail="Select a residence (residence_id)")
        query = query.where(TaskCategory.residence_id == rid)
    elif rid:
        # Superadmin con residence_id específico: filtrar por esa residencia
        query = query.where(TaskCategory.residence_id == rid)

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
    rid = await _set_residence_context(db, current, residence_id)
    conds = [TaskCategory.deleted_at.is_(None)]
    if current["role"] != "superadmin":
        if not rid:
            raise HTTPException(status_code=428, detail="Select a residence (residence_id)")
        conds.append(TaskCategory.residence_id == rid)

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
    residence_id: str | None = Query(None, description="Filter by residence ID"),
):
    rid = await _set_residence_context(db, current, residence_id)
    if current["role"] not in ("superadmin", "manager"):
        raise HTTPException(status_code=403, detail="Only manager/superadmin can create templates")
    if not rid:
        raise HTTPException(status_code=428, detail="Select a residence (residence_id)")

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

@router.get("/templates", response_model=PaginatedResponse)
async def list_templates(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
    category_id: str | None = Query(None),
):
    rid = await _set_residence_context(db, current, residence_id)
    query = select(TaskTemplate).where(TaskTemplate.deleted_at.is_(None))

    if current["role"] != "superadmin":
        if not rid:
            raise HTTPException(status_code=428, detail="Select a residence (residence_id)")
        query = query.where(TaskTemplate.residence_id == rid)
    elif rid:
        # Superadmin con residence_id específico: filtrar por esa residencia
        query = query.where(TaskTemplate.residence_id == rid)
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
    rid = await _set_residence_context(db, current, residence_id)
    conds = [TaskTemplate.deleted_at.is_(None)]
    if current["role"] != "superadmin":
        if not rid:
            raise HTTPException(status_code=428, detail="Select a residence (residence_id)")
        conds.append(TaskTemplate.residence_id == rid)
    elif rid:
        # Superadmin con residence_id específico: filtrar por esa residencia
        conds.append(TaskTemplate.residence_id == rid)
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

@router.get("/applications", response_model=PaginatedResponse)
async def list_applications(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
    resident_id: str | None = Query(None, description="Filter by resident ID"),
    template_id: str | None = Query(None, description="Filter by template ID"),
    category_id: str | None = Query(None, description="Filter by category ID"),
):
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
