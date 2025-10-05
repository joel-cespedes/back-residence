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
        self.project_id = "residences-voice"
        self.session_id = "voice-session"
        self.credentials_path = "residences-voice-d0a9b1f0c8ae.json"
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
        Envía el transcript a Dialogflow y extrae las entidades
        
        Returns:
            Dict con las entidades extraídas: resident_name, task_name, status
        """
        try:
            client = self._get_dialogflow_client()
            session_path = client.session_path(self.project_id, self.session_id)
            
            # Crear el request para Dialogflow
            text_input = dialogflow.TextInput(text=transcript, language_code="es")
            query_input = dialogflow.QueryInput(text=text_input)
            
            # Enviar request a Dialogflow
            response = client.detect_intent(
                request={"session": session_path, "query_input": query_input}
            )
            
            # Extraer entidades de los parámetros
            parameters = response.query_result.parameters
            
            return {
                "resident_name": parameters.get("resident_name", ""),
                "task_name": parameters.get("task_name", ""),
                "status": parameters.get("status", ""),
                "intent": response.query_result.intent.display_name,
                "confidence": response.query_result.intent_detection_confidence
            }
            
        except Exception as e:
            raise Exception(f"Error al procesar con Dialogflow: {str(e)}")
    
    async def find_resident_by_name(
        self, 
        resident_name: str, 
        residence_id: str, 
        db: AsyncSession
    ) -> Optional[Tuple[str, str]]:
        """
        Busca un residente por nombre usando fuzzy matching
        
        Returns:
            Tuple (resident_id, resident_name) si encuentra coincidencia, None si no
        """
        if not resident_name:
            return None
            
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
        resident_names = [(r.id, r.full_name) for r in residents]
        
        # Buscar la mejor coincidencia con fuzzy matching
        # Usar un threshold de 60 para evitar coincidencias muy pobres
        best_match = process.extractOne(
            resident_name,
            [name for _, name in resident_names],
            scorer=fuzz.ratio,
            score_cutoff=60
        )
        
        if best_match:
            matched_name = best_match[0]
            # Encontrar el ID del residente que coincide
            for resident_id, name in resident_names:
                if name == matched_name:
                    return (resident_id, name)
        
        return None
    
    async def find_task_by_name(
        self, 
        task_name: str, 
        residence_id: str, 
        db: AsyncSession
    ) -> Optional[Tuple[str, str]]:
        """
        Busca una tarea por nombre usando fuzzy matching
        
        Returns:
            Tuple (task_id, task_name) si encuentra coincidencia, None si no
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
        
        # Buscar la mejor coincidencia con fuzzy matching
        best_match = process.extractOne(
            task_name,
            [name for _, name in task_names],
            scorer=fuzz.ratio,
            score_cutoff=60
        )
        
        if best_match:
            matched_name = best_match[0]
            # Encontrar el ID de la tarea que coincide
            for task_id, name in task_names:
                if name == matched_name:
                    return (task_id, name)
        
        return None
    
    async def validate_task_status(
        self, 
        task_id: str, 
        status: str, 
        db: AsyncSession
    ) -> bool:
        """
        Valida que la tarea tenga estados y que el status proporcionado exista
        
        Returns:
            True si el status es válido, False si no
        """
        if not status:
            return True  # Status opcional
            
        # Obtener la plantilla de tarea
        query = select(TaskTemplate).where(TaskTemplate.id == task_id)
        result = await db.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            return False
        
        # Verificar que la tarea tenga estados definidos
        available_statuses = []
        if template.status1: available_statuses.append(template.status1)
        if template.status2: available_statuses.append(template.status2)
        if template.status3: available_statuses.append(template.status3)
        if template.status4: available_statuses.append(template.status4)
        if template.status5: available_statuses.append(template.status5)
        if template.status6: available_statuses.append(template.status6)
        
        if not available_statuses:
            return False  # La tarea no tiene estados
        
        # Buscar el status usando fuzzy matching
        best_match = process.extractOne(
            status,
            available_statuses,
            scorer=fuzz.ratio,
            score_cutoff=70  # Threshold más alto para status
        )
        
        return best_match is not None
    
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
