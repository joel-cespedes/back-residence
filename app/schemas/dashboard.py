# =====================================================================
# ESQUEMAS DE DASHBOARD Y ESTADÍSTICAS
# =====================================================================

from __future__ import annotations

from typing import Literal, List, Dict, Optional
from pydantic import BaseModel

# =========================================================
# ESQUEMAS DE MÉTRICAS DE DASHBOARD
# =========================================================

class DashboardMetric(BaseModel):
    """
    Esquema para métricas individuales del dashboard.

    Attributes:
        title (str): Título de la métrica
        value (str): Valor de la métrica
        change (str): Cambio representado como texto
        changeType (Literal['positive', 'negative']): Tipo de cambio
        icon (str): Icono a mostrar
        color (str): Color principal
        colorIcon (Optional[str]): Color del icono (opcional)
    """
    title: str
    value: str
    change: str
    changeType: Literal['positive', 'negative']
    icon: str
    color: str
    colorIcon: Optional[str] = None


class MonthlyData(BaseModel):
    """
    Esquema para datos mensuales de comparación.

    Attributes:
        month (str): Mes en formato texto
        value (int): Valor del mes
    """
    month: str
    value: int


class YearComparison(BaseModel):
    """
    Esquema para comparación entre años.

    Attributes:
        year (int): Año de comparación
        data (List[MonthlyData]): Datos mensuales del año
    """
    year: int
    data: List[MonthlyData]


# =========================================================
# ESQUEMAS DE ESTADÍSTICAS DE RESIDENTES
# =========================================================

class ResidentStats(BaseModel):
    """
    Esquema para estadísticas de residentes.

    Attributes:
        total (int): Total de residentes
        active (int): Residentes activos
        discharged (int): Residentes dados de alta
        deceased (int): Residentes fallecidos
        with_bed (int): Residentes con cama asignada
        without_bed (int): Residentes sin cama asignada
        new_residents (int): Nuevos residentes en el período seleccionado
        change_percentage (float): Porcentaje de cambio respecto al período anterior
    """
    total: int
    active: int
    discharged: int
    deceased: int
    with_bed: int
    without_bed: int
    new_residents: int = 0
    change_percentage: float = 0.0


class MonthlyResidentData(BaseModel):
    """
    Esquema para datos mensuales de residentes.

    Attributes:
        month (str): Mes en formato texto
        value (int): Número de residentes
    """
    month: str
    value: int


class NewResidentStats(BaseModel):
    """
    Esquema para estadísticas de nuevos residentes.

    Attributes:
        current_year (int): Año actual
        current_year_residents (int): Residentes del año actual
        previous_year_residents (int): Residentes del año anterior
        growth_percentage (float): Porcentaje de crecimiento
        total_residents (int): Total de residentes
        monthly_data (List[MonthlyResidentData]): Datos mensuales
    """
    current_year: int
    current_year_residents: int
    previous_year_residents: int
    growth_percentage: float
    total_residents: int
    monthly_data: List[MonthlyResidentData]


# =========================================================
# ESQUEMAS DE ESTADÍSTICAS DE MEDICIONES
# =========================================================

class MeasurementStats(BaseModel):
    """
    Esquema para estadísticas de mediciones.

    Attributes:
        total_measurements (int): Total de mediciones
        by_type (Dict[str, int]): Mediciones por tipo
        by_source (Dict[str, int]): Mediciones por fuente
        last_30_days (int): Mediciones en los últimos 30 días
        trend (Literal['increasing', 'decreasing', 'stable']): Tendencia
        change_percentage (float): Porcentaje de cambio respecto al período anterior
    """
    total_measurements: int
    by_type: Dict[str, int]
    by_source: Dict[str, int]
    last_30_days: int
    trend: Literal['increasing', 'decreasing', 'stable']
    change_percentage: float = 0.0


# =========================================================
# ESQUEMAS DE ESTADÍSTICAS DE TAREAS
# =========================================================

class TaskStats(BaseModel):
    """
    Esquema para estadísticas de tareas.

    Attributes:
        total_applications (int): Total de aplicaciones
        completion_rate (float): Tasa de completitud
        by_category (Dict[str, Dict[str, int]]): Datos por categoría
        last_30_days (int): Aplicaciones en los últimos 30 días
        change_percentage (float): Porcentaje de cambio respecto al período anterior
    """
    total_applications: int
    completion_rate: float
    by_category: Dict[str, Dict[str, int]]
    last_30_days: int
    change_percentage: float = 0.0


class TaskCategoryWithCount(BaseModel):
    """
    Esquema para categoría de tareas con conteo.

    Attributes:
        id (str): ID de la categoría
        name (str): Nombre de la categoría
        description (Optional[str]): Descripción de la categoría
        icon (Optional[str]): Icono de la categoría
        color (Optional[str]): Color de la categoría
        residence_id (str): ID de la residencia
        residence_name (str): Nombre de la residencia
        task_count (int): Total de tareas
        active_tasks (int): Tareas activas
        completed_tasks (int): Tareas completadas
    """
    id: str
    name: str
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    residence_id: str
    residence_name: str
    task_count: int
    active_tasks: int
    completed_tasks: int


# =========================================================
# ESQUEMAS DE ESTADÍSTICAS DE DISPOSITIVOS
# =========================================================

class DeviceStats(BaseModel):
    """
    Esquema para estadísticas de dispositivos.

    Attributes:
        total_devices (int): Total de dispositivos
        by_type (Dict[str, int]): Dispositivos por tipo
        low_battery (int): Dispositivos con batería baja
        average_battery (float): Porcentaje promedio de batería
        new_devices (int): Nuevos dispositivos en el período seleccionado
        change_percentage (float): Porcentaje de cambio respecto al período anterior
    """
    total_devices: int
    by_type: Dict[str, int]
    low_battery: int
    average_battery: float
    new_devices: int = 0
    change_percentage: float = 0.0


# =========================================================
# ESQUEMA PRINCIPAL DE DASHBOARD
# =========================================================

class DashboardData(BaseModel):
    """
    Esquema principal para datos del dashboard.

    Attributes:
        metrics (List[DashboardMetric]): Métricas principales
        resident_stats (ResidentStats): Estadísticas de residentes
        measurement_stats (MeasurementStats): Estadísticas de mediciones
        task_stats (TaskStats): Estadísticas de tareas
        device_stats (DeviceStats): Estadísticas de dispositivos
        yearly_comparison (List[YearComparison]): Comparación anual
        recent_activity (List[Dict]): Actividad reciente
    """
    metrics: List[DashboardMetric]
    resident_stats: ResidentStats
    measurement_stats: MeasurementStats
    task_stats: TaskStats
    device_stats: DeviceStats
    yearly_comparison: List[YearComparison]
    recent_activity: List[Dict]