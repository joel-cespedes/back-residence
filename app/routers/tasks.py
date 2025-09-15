# app/routers/tasks.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
from sqlalchemy import select, update, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user
from app.models import (
    TaskCategory, TaskTemplate, TaskApplication,
    Resident, UserResidence
)
from app.schemas import (
    TaskCategoryCreate, TaskCategoryUpdate, TaskCategoryOut,
    TaskTemplateCreate, TaskTemplateUpdate, TaskTemplateOut,
    TaskApplicationCreate, TaskApplicationUpdate, TaskApplicationOut,
)
from app.security import new_uuid

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

# -------------------- CATEGORIES --------------------

@router.post("/categories", response_model=TaskCategoryOut, status_code=201)
async def create_category(
    payload: TaskCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Header(None, alias="X-Residence-Id"),
):
    rid = await _set_residence_context(db, current, residence_id)
    if current["role"] not in ("superadmin", "manager"):
        raise HTTPException(status_code=403, detail="Only manager/superadmin can create categories")
    if not rid:
        raise HTTPException(status_code=428, detail="Select a residence (X-Residence-Id)")

    # nombre único por residencia
    exists = await db.scalar(
        select(TaskCategory.id).where(TaskCategory.residence_id == rid,
                                      TaskCategory.name == payload.name,
                                      TaskCategory.deleted_at.is_(None))
    )
    if exists:
        raise HTTPException(status_code=409, detail="Category name already exists in residence")

    tc = TaskCategory(id=new_uuid(), residence_id=rid, name=payload.name)
    db.add(tc)
    await db.commit()
    await db.refresh(tc)
    return tc

@router.get("/categories", response_model=list[TaskCategoryOut])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Header(None, alias="X-Residence-Id"),
):
    rid = await _set_residence_context(db, current, residence_id)
    conds = [TaskCategory.deleted_at.is_(None)]
    if current["role"] != "superadmin":
        if not rid:
            raise HTTPException(status_code=428, detail="Select a residence (X-Residence-Id)")
        conds.append(TaskCategory.residence_id == rid)

    q = await db.execute(select(TaskCategory).where(and_(*conds)).order_by(TaskCategory.name))
    return q.scalars().all()

@router.patch("/categories/{category_id}", response_model=TaskCategoryOut)
async def update_category(
    category_id: str,
    payload: TaskCategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    if current["role"] not in ("superadmin", "manager"):
        raise HTTPException(status_code=403, detail="Only manager/superadmin can update categories")

    q = await db.execute(select(TaskCategory).where(TaskCategory.id == category_id, TaskCategory.deleted_at.is_(None)))
    cat = q.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    values = {
        "name": payload.name if payload.name is not None else cat.name,
        "updated_at": func.now(),
    }
    await db.execute(update(TaskCategory).where(TaskCategory.id == category_id).values(**values))
    await db.commit()
    q2 = await db.execute(select(TaskCategory).where(TaskCategory.id == category_id))
    return q2.scalar_one()

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
    residence_id: str | None = Header(None, alias="X-Residence-Id"),
):
    rid = await _set_residence_context(db, current, residence_id)
    if current["role"] not in ("superadmin", "manager"):
        raise HTTPException(status_code=403, detail="Only manager/superadmin can create templates")
    if not rid:
        raise HTTPException(status_code=428, detail="Select a residence (X-Residence-Id)")

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
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t

@router.get("/templates", response_model=list[TaskTemplateOut])
async def list_templates(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Header(None, alias="X-Residence-Id"),
    category_id: str | None = Query(None),
):
    rid = await _set_residence_context(db, current, residence_id)
    conds = [TaskTemplate.deleted_at.is_(None)]
    if current["role"] != "superadmin":
        if not rid:
            raise HTTPException(status_code=428, detail="Select a residence (X-Residence-Id)")
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
    residence_id: str | None = Header(None, alias="X-Residence-Id"),
):
    # Fijar/validar residencia
    rid = await _set_residence_context(db, current, residence_id)
    if not rid and current["role"] != "superadmin":
        raise HTTPException(status_code=428, detail="Select a residence (X-Residence-Id)")

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
    return app

@router.get("/applications", response_model=list[TaskApplicationOut])
async def list_applications(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Header(None, alias="X-Residence-Id"),
    resident_id: str | None = Query(None),
    template_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    rid = await _set_residence_context(db, current, residence_id)

    conds = [TaskApplication.deleted_at.is_(None)]
    if current["role"] != "superadmin":
        if not rid:
            raise HTTPException(status_code=428, detail="Select a residence (X-Residence-Id)")
        conds.append(TaskApplication.residence_id == rid)
    if resident_id:
        conds.append(TaskApplication.resident_id == resident_id)
    if template_id:
        conds.append(TaskApplication.task_template_id == template_id)

    q = await db.execute(
        select(TaskApplication).where(and_(*conds)).order_by(TaskApplication.applied_at.desc()).limit(limit)
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
