# app/services/voice_measurement_service.py
"""
Servicio para procesamiento de transcripciones de voz de mediciones usando regex y fuzzy matching
"""

import re
from typing import Optional, Dict, Any, Tuple
from rapidfuzz import fuzz, process
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Resident, Room, Bed


class VoiceMeasurementService:
    """Servicio para procesamiento de voz de mediciones usando regex y fuzzy matching"""

    def __init__(self):
        pass

    async def parse_measurement_transcript(self, transcript: str) -> Dict[str, Any]:
        """
        Extrae el nombre del residente, tipo de medición y valores del transcript.

        Ejemplos de transcripts:
        - "Tensión de Juan Pérez 120 80"
        - "Oxígeno de María García 98"
        - "Peso de Pedro López 75 kilos"
        - "Temperatura de Ana Martínez 36.5"

        Returns:
            Dict con: resident_name, measurement_type, values
        """
        try:
            text = transcript.strip().lower()

            # Palabras clave para cada tipo de medición
            measurement_keywords = {
                "bp": ["tensión", "presión", "presión arterial", "sistólica", "diastólica"],
                "spo2": ["oxígeno", "saturación", "oximetría", "oxímetro"],
                "weight": ["peso", "kilos", "kilogramos", "báscula"],
                "temperature": ["temperatura", "fiebre", "grados"]
            }

            # Detectar tipo de medición
            measurement_type = None
            for mtype, keywords in measurement_keywords.items():
                if any(keyword in text for keyword in keywords):
                    measurement_type = mtype
                    break

            if not measurement_type:
                return {
                    "resident_name": "",
                    "measurement_type": None,
                    "values": {},
                    "confidence": 0.0,
                    "error": "No se pudo identificar el tipo de medición"
                }

            # Patrón para extraer nombre: buscar después del ÚLTIMO "de" hasta encontrar números
            # Ejemplo: "saturación de oxígeno de Juan Pérez 98" -> "Juan Pérez"
            # Primero, encontrar todas las ocurrencias de "de"
            de_positions = [m.start() for m in re.finditer(r'\bde\b', text)]

            if not de_positions:
                return {
                    "resident_name": "",
                    "measurement_type": measurement_type,
                    "values": {},
                    "confidence": 0.0,
                    "error": "No se encontró la palabra 'de' para identificar el nombre"
                }

            # Usar el último "de" encontrado
            last_de_pos = de_positions[-1]
            text_after_last_de = text[last_de_pos:]

            # Extraer nombre después del último "de"
            name_pattern = r"de\s+([a-záéíóúñ\s]+?)(?=\s+\d)"
            name_match = re.search(name_pattern, text_after_last_de)

            if not name_match:
                return {
                    "resident_name": "",
                    "measurement_type": measurement_type,
                    "values": {},
                    "confidence": 0.0,
                    "error": "No se pudo identificar el nombre del residente"
                }

            resident_name = name_match.group(1).strip().title()

            # Extraer valores según el tipo de medición
            values = {}

            if measurement_type == "bp":
                # Buscar dos números: sistólica y diastólica
                numbers = re.findall(r"\b(\d{2,3})\b", text)
                if len(numbers) >= 2:
                    values["systolic"] = int(numbers[0])
                    values["diastolic"] = int(numbers[1])
                    # Buscar pulso opcional (tercer número)
                    if len(numbers) >= 3:
                        values["pulse_bpm"] = int(numbers[2])
                else:
                    return {
                        "resident_name": resident_name,
                        "measurement_type": measurement_type,
                        "values": {},
                        "confidence": 0.5,
                        "error": "No se encontraron valores de presión arterial (se esperan 2 números)"
                    }

            elif measurement_type == "spo2":
                # Buscar un número (saturación)
                numbers = re.findall(r"\b(\d{2,3})\b", text)
                if len(numbers) >= 1:
                    values["spo2"] = int(numbers[0])
                    # Buscar pulso opcional (segundo número)
                    if len(numbers) >= 2:
                        values["pulse_bpm"] = int(numbers[1])
                else:
                    return {
                        "resident_name": resident_name,
                        "measurement_type": measurement_type,
                        "values": {},
                        "confidence": 0.5,
                        "error": "No se encontró valor de saturación de oxígeno"
                    }

            elif measurement_type == "weight":
                # Buscar número con posible decimal
                weight_match = re.search(r"\b(\d{2,3}(?:\.\d{1,2})?)\b", text)
                if weight_match:
                    values["weight_kg"] = float(weight_match.group(1))
                else:
                    return {
                        "resident_name": resident_name,
                        "measurement_type": measurement_type,
                        "values": {},
                        "confidence": 0.5,
                        "error": "No se encontró valor de peso"
                    }

            elif measurement_type == "temperature":
                # Buscar número con posible decimal
                temp_match = re.search(r"\b(\d{2}(?:\.\d{1})?)\b", text)
                if temp_match:
                    values["temperature_c"] = float(temp_match.group(1))
                else:
                    return {
                        "resident_name": resident_name,
                        "measurement_type": measurement_type,
                        "values": {},
                        "confidence": 0.5,
                        "error": "No se encontró valor de temperatura"
                    }

            print(f"🔍 DEBUG Measurement Parser:")
            print(f"   Transcript: {transcript}")
            print(f"   Resident: {resident_name}")
            print(f"   Type: {measurement_type}")
            print(f"   Values: {values}")

            return {
                "resident_name": resident_name,
                "measurement_type": measurement_type,
                "values": values,
                "confidence": 1.0,
                "error": None
            }

        except Exception as e:
            return {
                "resident_name": "",
                "measurement_type": None,
                "values": {},
                "confidence": 0.0,
                "error": f"Error al procesar transcript: {str(e)}"
            }

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
            options = []
            for match_name, score in similar_matches[:5]:  # Máximo 5 opciones
                # Buscar info adicional del residente
                for res_id, full_name, bed_id, room_id in resident_names:
                    if full_name == match_name:
                        # Obtener nombre de room y bed
                        room_name = None
                        bed_number = None
                        floor_name = None

                        if room_id:
                            room_query = select(Room.name, Room.floor_name).where(Room.id == room_id)
                            room_result = await db.execute(room_query)
                            room_row = room_result.one_or_none()
                            if room_row:
                                room_name, floor_name = room_row

                        if bed_id:
                            bed_query = select(Bed.number).where(Bed.id == bed_id)
                            bed_result = await db.execute(bed_query)
                            bed_number = bed_result.scalar()

                        options.append({
                            "id": res_id,
                            "full_name": full_name,
                            "room_name": room_name,
                            "bed_number": bed_number,
                            "floor_name": floor_name
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

    def validate_measurement_values(
        self,
        measurement_type: str,
        values: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Valida que los valores de la medición estén dentro de rangos válidos

        Returns:
            Tuple (is_valid, error_message)
        """
        if measurement_type == "bp":
            systolic = values.get("systolic")
            diastolic = values.get("diastolic")

            if not systolic or not diastolic:
                return (False, "Se requieren valores de presión sistólica y diastólica")

            if not (70 <= systolic <= 200):
                return (False, "La presión sistólica debe estar entre 70 y 200 mmHg")

            if not (40 <= diastolic <= 130):
                return (False, "La presión diastólica debe estar entre 40 y 130 mmHg")

            pulse = values.get("pulse_bpm")
            if pulse and not (40 <= pulse <= 200):
                return (False, "El pulso debe estar entre 40 y 200 bpm")

        elif measurement_type == "spo2":
            spo2 = values.get("spo2")

            if not spo2:
                return (False, "Se requiere valor de saturación de oxígeno")

            if not (0 <= spo2 <= 100):
                return (False, "La saturación de oxígeno debe estar entre 0 y 100%")

            pulse = values.get("pulse_bpm")
            if pulse and not (40 <= pulse <= 200):
                return (False, "El pulso debe estar entre 40 y 200 bpm")

        elif measurement_type == "weight":
            weight = values.get("weight_kg")

            if not weight:
                return (False, "Se requiere valor de peso")

            if not (20 <= weight <= 300):
                return (False, "El peso debe estar entre 20 y 300 kg")

        elif measurement_type == "temperature":
            temperature = values.get("temperature_c")

            if not temperature:
                return (False, "Se requiere valor de temperatura")

            if not (30 <= temperature <= 45):
                return (False, "La temperatura debe estar entre 30 y 45°C")

        else:
            return (False, f"Tipo de medición desconocido: {measurement_type}")

        return (True, None)

    def generate_confirmation_message(
        self,
        resident_name: str,
        measurement_type: str,
        values: Dict[str, Any]
    ) -> str:
        """
        Genera el mensaje de confirmación para la medición
        """
        type_labels = {
            "bp": "Presión arterial",
            "spo2": "Saturación de oxígeno",
            "weight": "Peso",
            "temperature": "Temperatura"
        }

        type_label = type_labels.get(measurement_type, measurement_type)

        if measurement_type == "bp":
            systolic = values.get("systolic")
            diastolic = values.get("diastolic")
            pulse = values.get("pulse_bpm")
            if pulse:
                return f"Medición registrada: {type_label} {systolic}/{diastolic} mmHg, pulso {pulse} bpm para {resident_name}"
            else:
                return f"Medición registrada: {type_label} {systolic}/{diastolic} mmHg para {resident_name}"

        elif measurement_type == "spo2":
            spo2 = values.get("spo2")
            pulse = values.get("pulse_bpm")
            if pulse:
                return f"Medición registrada: {type_label} {spo2}%, pulso {pulse} bpm para {resident_name}"
            else:
                return f"Medición registrada: {type_label} {spo2}% para {resident_name}"

        elif measurement_type == "weight":
            weight = values.get("weight_kg")
            return f"Medición registrada: {type_label} {weight} kg para {resident_name}"

        elif measurement_type == "temperature":
            temperature = values.get("temperature_c")
            return f"Medición registrada: {type_label} {temperature}°C para {resident_name}"

        return f"Medición registrada para {resident_name}"
