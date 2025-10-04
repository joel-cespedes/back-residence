# =====================================================================
# ESQUEMAS DE TAREAS (Plantillas y Aplicaciones)
# =====================================================================

from __future__ import annotations

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

# =========================================================
# ESQUEMAS DE CATEGORÍAS DE TAREAS
# =========================================================

class TaskCategoryCreate(BaseModel):
    """
    Esquema para la creación de una nueva categoría de tareas.

    Attributes:
        name (str): Nombre de la categoría de tareas
        residence_id (str): ID de la residencia a la que pertenece
    """
    name: str
    residence_id: str


class TaskCategoryUpdate(BaseModel):
    """
    Esquema para la actualización de una categoría de tareas existente.

    Attributes:
        name (Optional[str]): Nuevo nombre de la categoría
    """
    name: Optional[str] = None


class TaskCategoryOut(BaseModel):
    """
    Esquema para la salida de datos de categoría de tareas.

    Attributes:
        id (str): Identificador único de la categoría
        residence_id (str): ID de la residencia a la que pertenece
        name (str): Nombre de la categoría
        created_by_info (Optional[Dict[str, Any]]): Información del usuario que creó la categoría
        created_at (datetime): Fecha de creación del registro
        updated_at (datetime): Fecha de última actualización
        deleted_at (Optional[datetime]): Fecha de eliminación (soft delete)
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    residence_id: str
    name: str
    created_by_info: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


# =========================================================
# ESQUEMAS DE PLANTILLAS DE TAREAS
# =========================================================

class TaskTemplateCreate(BaseModel):
    """
    Esquema para la creación de una nueva plantilla de tarea.

    Attributes:
        residence_id (str): ID de la residencia a la que pertenece
        task_category_id (str): ID de la categoría a la que pertenece
        name (str): Nombre de la plantilla de tarea
        status1 (Optional[str]): Texto para estado 1
        status2 (Optional[str]): Texto para estado 2
        status3 (Optional[str]): Texto para estado 3
        status4 (Optional[str]): Texto para estado 4
        status5 (Optional[str]): Texto para estado 5
        status6 (Optional[str]): Texto para estado 6
        audio_phrase (Optional[str]): Frase de audio asociada
        is_block (Optional[bool]): Indica si es una tarea de bloqueo
    """
    residence_id: str
    task_category_id: str
    name: str
    status1: Optional[str] = None
    status2: Optional[str] = None
    status3: Optional[str] = None
    status4: Optional[str] = None
    status5: Optional[str] = None
    status6: Optional[str] = None
    audio_phrase: Optional[str] = None
    is_block: Optional[bool] = None


class TaskTemplateUpdate(BaseModel):
    """
    Esquema para la actualización de una plantilla de tarea existente.

    Attributes:
        task_category_id (Optional[str]): Nueva categoría de la plantilla
        name (Optional[str]): Nuevo nombre de la plantilla
        status1-6 (Optional[str]): Nuevos textos para estados
        audio_phrase (Optional[str]): Nueva frase de audio
        is_block (Optional[bool]): Nuevo estado de bloqueo
    """
    task_category_id: Optional[str] = None
    name: Optional[str] = None
    status1: Optional[str] = None
    status2: Optional[str] = None
    status3: Optional[str] = None
    status4: Optional[str] = None
    status5: Optional[str] = None
    status6: Optional[str] = None
    audio_phrase: Optional[str] = None
    is_block: Optional[bool] = None


class TaskTemplateOut(BaseModel):
    """
    Esquema para la salida de datos de plantilla de tarea.

    Attributes:
        id (str): Identificador único de la plantilla
        residence_id (str): ID de la residencia a la que pertenece
        task_category_id (str): ID de la categoría a la que pertenece
        name (str): Nombre de la plantilla
        status1-6 (Optional[str]): Textos para estados
        audio_phrase (Optional[str]): Frase de audio asociada
        is_block (Optional[bool]): Estado de bloqueo
        created_by_info (Optional[Dict[str, Any]]): Información del usuario que creó la plantilla
        created_at (datetime): Fecha de creación del registro
        updated_at (datetime): Fecha de última actualización
        deleted_at (Optional[datetime]): Fecha de eliminación (soft delete)
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    residence_id: str
    task_category_id: str
    name: str
    status1: Optional[str] = None
    status2: Optional[str] = None
    status3: Optional[str] = None
    status4: Optional[str] = None
    status5: Optional[str] = None
    status6: Optional[str] = None
    audio_phrase: Optional[str] = None
    is_block: Optional[bool] = None
    created_by_info: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


# =========================================================
# ESQUEMAS DE APLICACIONES DE TAREAS
# =========================================================

class TaskApplicationCreate(BaseModel):
    """
    Esquema para la creación de una nueva aplicación de tarea.

    Attributes:
        resident_id (str): ID del residente al que se aplica
        task_template_id (str): ID de la plantilla utilizada
        selected_status_index (Optional[int]): Índice del estado seleccionado (1-6)
        selected_status_text (Optional[str]): Texto del estado seleccionado
        applied_at (Optional[datetime]): Fecha de aplicación (default: ahora)
    """
    resident_id: str
    task_template_id: str
    selected_status_index: Optional[int] = Field(None, ge=1, le=6)
    selected_status_text: Optional[str] = None
    applied_at: Optional[datetime] = None


class TaskApplicationUpdate(BaseModel):
    """
    Esquema para la actualización de una aplicación de tarea existente.

    Attributes:
        selected_status_index (Optional[int]): Nuevo índice del estado (1-6)
        selected_status_text (Optional[str]): Nuevo texto del estado
        applied_at (Optional[datetime]): Nueva fecha de aplicación
    """
    selected_status_index: Optional[int] = Field(None, ge=1, le=6)
    selected_status_text: Optional[str] = None
    applied_at: Optional[datetime] = None


class TaskApplicationOut(BaseModel):
    """
    Esquema para la salida de datos de aplicación de tarea.

    Attributes:
        id (str): Identificador único de la aplicación
        residence_id (str): ID de la residencia a la que pertenece
        resident_id (str): ID del residente al que se aplica
        resident_full_name (Optional[str]): Nombre completo del residente
        task_template_id (str): ID de la plantilla utilizada
        task_template_name (Optional[str]): Nombre de la plantilla de tarea
        task_category_id (Optional[str]): ID de la categoría de la tarea
        task_category_name (Optional[str]): Nombre de la categoría de la tarea
        applied_by_info (Optional[Dict[str, Any]]): Información del usuario que aplicó la tarea
        applied_at (datetime): Fecha de aplicación de la tarea
        selected_status_index (Optional[int]): Índice del estado seleccionado
        selected_status_text (Optional[str]): Texto del estado seleccionado
        created_at (datetime): Fecha de creación del registro
        updated_at (datetime): Fecha de última actualización
        deleted_at (Optional[datetime]): Fecha de eliminación (soft delete)
    """
    model_config = ConfigDict(from_attributes=True, extra='allow')

    id: str
    residence_id: str
    resident_id: str
    resident_full_name: Optional[str] = None
    task_template_id: str
    task_template_name: Optional[str] = None
    task_category_id: Optional[str] = None
    task_category_name: Optional[str] = None
    applied_by_info: Optional[Dict[str, Any]] = None
    applied_at: datetime
    selected_status_index: Optional[int] = None
    selected_status_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None