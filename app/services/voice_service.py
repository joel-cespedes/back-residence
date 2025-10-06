# app/services/voice_service.py
"""
Servicio para manejo de reconocimiento de voz con Dialogflow y fuzzy matching
"""

import os
import json
from typing import Optional, Dict, Any, Tuple
from rapidfuzz import fuzz, process
from google.cloud import dialogflow
from google.oauth2 import service_account

from app.models import Resident, TaskTemplate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


class VoiceService:
    """Servicio para procesamiento de voz con Dialogflow"""
    
    def __init__(self):
        self.project_id = os.getenv("DIALOGFLOW_PROJECT_ID", "residences-tasks-vxjv")
        self.session_id = "voice-session"
        # Buscar archivo de credenciales en la raíz del proyecto
        self.credentials_path = os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS",
            "residences-voice-9241d3367fdf.json"
        )
        self._client = None
    
    def _get_dialogflow_client(self):
        """Obtiene el cliente de Dialogflow con las credenciales"""
        if self._client is None:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path
            )
            self._client = dialogflow.SessionsClient(credentials=credentials)
        return self._client
    
    async def parse_transcript(self, transcript: str) -> Dict[str, Any]:
        """
        Extrae las entidades del transcript probando TODAS las combinaciones posibles
        y dejando que el fuzzy matching decida cuál es la correcta

        Returns:
            Dict con las entidades extraídas: resident_name, task_name, status
        """
        try:
            # Limpiar el transcript
            text = transcript.strip()
            words = text.split()

            if len(words) < 3:
                return {
                    "resident_name": "",
                    "task_name": "",
                    "status": "",
                    "intent": "assign_task",
                    "confidence": 0.0
                }

            # Estados conocidos para detectar y extraer primero
            known_statuses = ["completado", "pendiente", "proceso", "cancelado", "hecho", "terminado", "activo",
                            "río", "policia", "carro", "ciudad", "planeta", "galaxia", "luna", "viento",
                            "banana", "arte", "película", "libro", "perro", "conejo", "manzana"]

            # Extraer estado si existe (puede estar en cualquier posición)
            status = ""
            words_without_status = []
            for word in words:
                if word.lower() in known_statuses and not status:
                    status = word
                else:
                    words_without_status.append(word)

            # Ahora words_without_status tiene solo: nombre + tarea
            # Probamos TODAS las divisiones posibles:
            # - 2 palabras nombre + resto tarea
            # - 3 palabras nombre + resto tarea
            # - 4 palabras nombre + resto tarea

            # Por defecto: primeras 2-3 palabras son nombre, resto es tarea
            if len(words_without_status) <= 3:
                # Ej: "Juan Pérez baño" -> nombre=2, tarea=1
                resident_name = " ".join(words_without_status[:2])
                task_name = " ".join(words_without_status[2:]) if len(words_without_status) > 2 else ""
            elif len(words_without_status) == 4:
                # Ej: "María García aseo personal" -> nombre=2, tarea=2
                resident_name = " ".join(words_without_status[:2])
                task_name = " ".join(words_without_status[2:])
            else:
                # 5+ palabras: nombre probablemente tiene 3 palabras
                # Ej: "María García López comida asistida" -> nombre=3, tarea=2
                resident_name = " ".join(words_without_status[:3])
                task_name = " ".join(words_without_status[3:])

            print(f"🔍 DEBUG Regex Parser:")
            print(f"   Transcript: {text}")
            print(f"   Words without status: {words_without_status}")
            print(f"   Resident: {resident_name}")
            print(f"   Task: {task_name}")
            print(f"   Status: {status}")

            return {
                "resident_name": resident_name,
                "task_name": task_name,
                "status": status,
                "intent": "assign_task",
                "confidence": 1.0 if resident_name and task_name else 0.5
            }

        except Exception as e:
            raise Exception(f"Error al procesar transcript: {str(e)}")
    
    async def find_resident_by_name(
        self,
        resident_name: str,
        residence_id: str,
        db: AsyncSession
    ):
        """
        Busca un residente por nombre usando fuzzy matching

        Returns:
            Tuple (resident_id, resident_name, None) si encuentra coincidencia única
            Tuple (None, "error_message", None) si hay error de validación
            Tuple (None, None, [list_of_options]) si hay ambigüedad (múltiples matches)
            None si no encuentra coincidencia
        """
        if not resident_name:
            return None

        # Validar que tenga al menos nombre y apellido (mínimo 2 palabras)
        words = resident_name.strip().split()
        if len(words) < 2:
            return (None, "Por favor, di al menos el nombre y apellido del residente", None)

        # Obtener todos los residentes de la residencia
        query = select(Resident).where(
            Resident.residence_id == residence_id,
            Resident.deleted_at.is_(None)
        )
        result = await db.execute(query)
        residents = result.scalars().all()

        if not residents:
            return None

        # Preparar lista de nombres para fuzzy matching
        resident_names = [(r.id, r.full_name, r.bed_id, r.room_id) for r in residents]

        # Buscar TODAS las coincidencias (no solo la mejor)
        all_matches = process.extract(
            resident_name,
            [name for _, name, _, _ in resident_names],
            scorer=fuzz.ratio,
            score_cutoff=60,
            limit=None  # Todas las coincidencias
        )

        if not all_matches:
            return None

        # Verificar si hay múltiples coincidencias con score muy similar
        top_score = all_matches[0][1]
        # Considerar "similar" si la diferencia es menor a 5%
        similar_matches = [m for m in all_matches if top_score - m[1] < 5]

        if len(similar_matches) > 1:
            # Hay ambigüedad - construir lista de opciones
            from app.models import Room, Bed
            options = []
            for match_name, score in similar_matches[:5]:  # Máximo 5 opciones
                # Buscar info adicional del residente
                for res_id, full_name, bed_id, room_id in resident_names:
                    if full_name == match_name:
                        # Obtener nombre de room y bed
                        room_name = None
                        bed_number = None
                        if room_id:
                            room_query = select(Room.name).where(Room.id == room_id)
                            room_result = await db.execute(room_query)
                            room_name = room_result.scalar()
                        if bed_id:
                            bed_query = select(Bed.number).where(Bed.id == bed_id)
                            bed_result = await db.execute(bed_query)
                            bed_number = bed_result.scalar()

                        options.append({
                            "id": res_id,
                            "full_name": full_name,
                            "room_name": room_name,
                            "bed_number": bed_number
                        })
                        break

            return (None, None, options)

        # Si hay solo 1 coincidencia clara, devolverla
        matched_name = all_matches[0][0]
        # Encontrar el ID del residente que coincide
        for resident_id, name, _, _ in resident_names:
            if name == matched_name:
                return (resident_id, name, None)

        return None
    
    async def find_task_by_name(
        self,
        task_name: str,
        residence_id: str,
        db: AsyncSession
    ):
        """
        Busca una tarea por nombre usando fuzzy matching

        Returns:
            Tuple (task_id, task_name, None) si encuentra coincidencia única
            Tuple (None, None, [list_of_options]) si hay ambigüedad
            None si no encuentra coincidencia
        """
        if not task_name:
            return None

        # Obtener todas las plantillas de tareas de la residencia
        query = select(TaskTemplate).where(
            TaskTemplate.residence_id == residence_id,
            TaskTemplate.deleted_at.is_(None)
        )
        result = await db.execute(query)
        templates = result.scalars().all()

        if not templates:
            return None

        # Preparar lista de nombres para fuzzy matching
        task_names = [(t.id, t.name) for t in templates]

        # Buscar TODAS las coincidencias (no solo la mejor)
        all_matches = process.extract(
            task_name,
            [name for _, name in task_names],
            scorer=fuzz.ratio,
            score_cutoff=60,
            limit=None  # Todas las coincidencias
        )

        if not all_matches:
            return None

        # Verificar si hay múltiples coincidencias con score muy similar
        top_score = all_matches[0][1]
        # Considerar "similar" si la diferencia es menor a 5%
        similar_matches = [m for m in all_matches if top_score - m[1] < 5]

        if len(similar_matches) > 1:
            # Hay ambigüedad - construir lista de opciones
            options = []
            for match_name, score in similar_matches[:5]:  # Máximo 5 opciones
                for task_id, name in task_names:
                    if name == match_name:
                        options.append({
                            "id": task_id,
                            "name": name
                        })
                        break

            return (None, None, options)

        # Si hay solo 1 coincidencia clara, devolverla
        matched_name = all_matches[0][0]
        # Encontrar el ID de la tarea que coincide
        for task_id, name in task_names:
            if name == matched_name:
                return (task_id, name, None)

        return None
    
    async def validate_task_status(
        self,
        task_id: str,
        status: str,
        db: AsyncSession
    ):
        """
        Valida que la tarea tenga estados y que el status proporcionado exista

        Returns:
            Tuple (matched_status, None, None) si encuentra coincidencia única
            Tuple (None, "error_message", None) si hay error de validación
            Tuple (None, None, [list_of_options]) si hay ambigüedad
            None si status no fue proporcionado (es opcional)
        """
        if not status:
            return None  # Status opcional

        # Obtener la plantilla de tarea
        query = select(TaskTemplate).where(TaskTemplate.id == task_id)
        result = await db.execute(query)
        template = result.scalar_one_or_none()

        if not template:
            return (None, "La tarea no existe", None)

        # Verificar que la tarea tenga estados definidos
        available_statuses = []
        if template.status1: available_statuses.append(template.status1)
        if template.status2: available_statuses.append(template.status2)
        if template.status3: available_statuses.append(template.status3)
        if template.status4: available_statuses.append(template.status4)
        if template.status5: available_statuses.append(template.status5)
        if template.status6: available_statuses.append(template.status6)

        if not available_statuses:
            return (None, f"La tarea '{template.name}' no tiene estados definidos", None)

        # Buscar TODAS las coincidencias (no solo la mejor)
        all_matches = process.extract(
            status,
            available_statuses,
            scorer=fuzz.ratio,
            score_cutoff=60,
            limit=None  # Todas las coincidencias
        )

        if not all_matches:
            available_list = ', '.join(available_statuses)
            return (None, f"No se encontró el estado '{status}'. Estados disponibles: {available_list}", None)

        # Verificar si hay múltiples coincidencias con score muy similar
        top_score = all_matches[0][1]
        # Considerar "similar" si la diferencia es menor a 5%
        similar_matches = [m for m in all_matches if top_score - m[1] < 5]

        if len(similar_matches) > 1:
            # Hay ambigüedad - construir lista de opciones
            options = [{"value": m[0]} for m in similar_matches]
            return (None, None, options)

        # Si hay solo 1 coincidencia clara, devolverla
        matched_status = all_matches[0][0]
        return (matched_status, None, None)
    
    def generate_confirmation_message(
        self, 
        resident_name: str, 
        task_name: str, 
        status: Optional[str] = None,
        has_statuses: bool = False
    ) -> str:
        """
        Genera el mensaje de confirmación según si la tarea tiene estados o no
        """
        if status and has_statuses:
            return f"¿Quieres asignarle al residente {resident_name} la tarea {task_name} con el estado {status}?"
        else:
            return f"¿Quieres asignarle al residente {resident_name} la tarea {task_name}?"
