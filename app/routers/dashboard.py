# app/routers/dashboard.py
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Header, HTTPException
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, date
from typing import Dict, List, Any

from app.deps import get_db, get_current_user
from app.models import (
    Residence, Resident, Device, Measurement, TaskApplication,
    User, UserResidence, TaskTemplate, Floor, Room, Bed, TaskCategory
)
from app.schemas import (
    DashboardData, DashboardMetric, ResidentStats,
    MeasurementStats, TaskStats, DeviceStats,
    MonthlyData, YearComparison, TaskCategoryWithCount, NewResidentStats,
    MonthlyResidentData
)

# Nuevo esquema para conteos de navegación
from pydantic import BaseModel
from typing import Dict, Any

class NavigationCounts(BaseModel):
    """Conteos para navegación del menú"""
    residences: int
    residents: int
    floors: int
    rooms: int
    beds: int
    managers: int
    professionals: int
    categories: int
    tasks: int
    devices: int
    measurements: int

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# -------------------- Helper Functions --------------------

async def apply_residence_context(db: AsyncSession, current: dict, residence_id: str | None):
    """Apply residence context for RLS"""
    if residence_id:
        # User is filtering by specific residence - check access
        if current["role"] != "superadmin":
            result = await db.execute(
                select(UserResidence).where(
                    UserResidence.user_id == current["id"],
                    UserResidence.residence_id == residence_id,
                    UserResidence.deleted_at.is_(None)
                )
            )
            if result.scalar_one_or_none() is None:
                raise HTTPException(status_code=403, detail="Access denied to this residence")
        await db.execute(text("SELECT set_config('app.residence_id', :rid, true)"), {"rid": residence_id})
    else:
        # No specific residence_id - user can see their assigned residences or all if superadmin
        if current["role"] != "superadmin":
            # Get user's assigned residences
            result = await db.execute(
                select(UserResidence.residence_id).where(
                    UserResidence.user_id == current["id"],
                    UserResidence.deleted_at.is_(None)
                )
            )
            user_residences = [row[0] for row in result.all()]
            if user_residences:
                # Set context to first assigned residence
                await db.execute(text("SELECT set_config('app.residence_id', :rid, true)"), {"rid": user_residences[0]})
            else:
                raise HTTPException(status_code=403, detail="No residences assigned to user")
        # Superadmin can see all - no residence context needed

async def get_resident_stats(db: AsyncSession, residence_id: str, days: int = 30) -> ResidentStats:
    """Get resident statistics"""
    # Calculate date range for filtering
    days_ago = datetime.utcnow() - timedelta(days=days)

    # Total residents (all time)
    total_result = await db.scalar(
        select(func.count(Resident.id)).where(
            Resident.residence_id == residence_id,
            Resident.deleted_at.is_(None)
        )
    )

    # Active residents
    active_result = await db.scalar(
        select(func.count(Resident.id)).where(
            Resident.residence_id == residence_id,
            Resident.status == 'active',
            Resident.deleted_at.is_(None)
        )
    )

    # Discharged residents
    discharged_result = await db.scalar(
        select(func.count(Resident.id)).where(
            Resident.residence_id == residence_id,
            Resident.status == 'discharged',
            Resident.deleted_at.is_(None)
        )
    )

    # Deceased residents
    deceased_result = await db.scalar(
        select(func.count(Resident.id)).where(
            Resident.residence_id == residence_id,
            Resident.status == 'deceased',
            Resident.deleted_at.is_(None)
        )
    )

    # Residents with bed
    with_bed_result = await db.scalar(
        select(func.count(Resident.id)).where(
            Resident.residence_id == residence_id,
            Resident.bed_id.isnot(None),
            Resident.status == 'active',
            Resident.deleted_at.is_(None)
        )
    )

    # Residents without bed
    without_bed_result = active_result - with_bed_result if active_result else 0

    # New residents in the selected time period
    new_residents_result = await db.scalar(
        select(func.count(Resident.id)).where(
            Resident.residence_id == residence_id,
            Resident.created_at >= days_ago,
            Resident.deleted_at.is_(None)
        )
    )

    # Calculate change percentage - compare with previous period
    previous_days_ago = datetime.utcnow() - timedelta(days=days * 2)
    previous_period_result = await db.scalar(
        select(func.count(Resident.id)).where(
            Resident.residence_id == residence_id,
            Resident.created_at >= previous_days_ago,
            Resident.created_at < days_ago,
            Resident.deleted_at.is_(None)
        )
    )

    # Calculate percentage change
    change_percentage = 0.0
    if previous_period_result and previous_period_result > 0:
        change_percentage = ((new_residents_result or 0) - previous_period_result) / previous_period_result * 100
    elif new_residents_result and new_residents_result > 0:
        change_percentage = 100.0  # No data in previous period, but we have data now

    return ResidentStats(
        total=total_result or 0,
        active=active_result or 0,
        discharged=discharged_result or 0,
        deceased=deceased_result or 0,
        with_bed=with_bed_result or 0,
        without_bed=without_bed_result or 0,
        new_residents=new_residents_result or 0,
        change_percentage=round(change_percentage, 1)
    )

async def get_measurement_stats(db: AsyncSession, residence_id: str, days: int = 30) -> MeasurementStats:
    """Get measurement statistics"""
    # Total measurements
    total_result = await db.scalar(
        select(func.count(Measurement.id)).where(
            Measurement.residence_id == residence_id,
            Measurement.deleted_at.is_(None)
        )
    )

    # By type
    bp_result = await db.scalar(
        select(func.count(Measurement.id)).where(
            Measurement.residence_id == residence_id,
            Measurement.type == 'bp',
            Measurement.deleted_at.is_(None)
        )
    )

    spo2_result = await db.scalar(
        select(func.count(Measurement.id)).where(
            Measurement.residence_id == residence_id,
            Measurement.type == 'spo2',
            Measurement.deleted_at.is_(None)
        )
    )

    weight_result = await db.scalar(
        select(func.count(Measurement.id)).where(
            Measurement.residence_id == residence_id,
            Measurement.type == 'weight',
            Measurement.deleted_at.is_(None)
        )
    )

    temp_result = await db.scalar(
        select(func.count(Measurement.id)).where(
            Measurement.residence_id == residence_id,
            Measurement.type == 'temperature',
            Measurement.deleted_at.is_(None)
        )
    )

    by_type = {
        'bp': bp_result or 0,
        'spo2': spo2_result or 0,
        'weight': weight_result or 0,
        'temperature': temp_result or 0
    }

    # By source
    device_result = await db.scalar(
        select(func.count(Measurement.id)).where(
            Measurement.residence_id == residence_id,
            Measurement.source == 'device',
            Measurement.deleted_at.is_(None)
        )
    )

    voice_result = await db.scalar(
        select(func.count(Measurement.id)).where(
            Measurement.residence_id == residence_id,
            Measurement.source == 'voice',
            Measurement.deleted_at.is_(None)
        )
    )

    manual_result = await db.scalar(
        select(func.count(Measurement.id)).where(
            Measurement.residence_id == residence_id,
            Measurement.source == 'manual',
            Measurement.deleted_at.is_(None)
        )
    )

    by_source = {
        'device': device_result or 0,
        'voice': voice_result or 0,
        'manual': manual_result or 0
    }

    # Last N days
    days_ago = datetime.utcnow() - timedelta(days=days)
    last_period_result = await db.scalar(
        select(func.count(Measurement.id)).where(
            Measurement.residence_id == residence_id,
            Measurement.taken_at >= days_ago,
            Measurement.deleted_at.is_(None)
        )
    )

    # Trend (compare with previous period)
    previous_days_ago = datetime.utcnow() - timedelta(days=days * 2)
    previous_period_result = await db.scalar(
        select(func.count(Measurement.id)).where(
            Measurement.residence_id == residence_id,
            Measurement.taken_at >= previous_days_ago,
            Measurement.taken_at < days_ago,
            Measurement.deleted_at.is_(None)
        )
    )

    trend = 'stable'
    if last_period_result and previous_period_result:
        if last_period_result > previous_period_result * 1.1:
            trend = 'increasing'
        elif last_period_result < previous_period_result * 0.9:
            trend = 'decreasing'

    # Calculate percentage change
    change_percentage = 0.0
    if previous_period_result and previous_period_result > 0:
        change_percentage = ((last_period_result or 0) - previous_period_result) / previous_period_result * 100
    elif last_period_result and last_period_result > 0:
        change_percentage = 100.0  # No data in previous period, but we have data now

    return MeasurementStats(
        total_measurements=total_result or 0,
        by_type=by_type,
        by_source=by_source,
        last_30_days=last_period_result or 0,
        trend=trend,
        change_percentage=round(change_percentage, 1)
    )

async def get_task_stats(db: AsyncSession, residence_id: str, days: int = 30) -> TaskStats:
    """Get task statistics"""
    # Total applications
    total_result = await db.scalar(
        select(func.count(TaskApplication.id)).where(
            TaskApplication.residence_id == residence_id,
            TaskApplication.deleted_at.is_(None)
        )
    )

    # Completion rate (applications with selected_status_index)
    completed_result = await db.scalar(
        select(func.count(TaskApplication.id)).where(
            TaskApplication.residence_id == residence_id,
            TaskApplication.selected_status_index.isnot(None),
            TaskApplication.deleted_at.is_(None)
        )
    )

    completion_rate = (completed_result / total_result * 100) if total_result else 0.0

    # By category
    category_result = await db.execute(
        text("""
            SELECT tc.name,
                   COUNT(ta.id) as total,
                   COUNT(CASE WHEN ta.selected_status_index IS NOT NULL THEN 1 END) as completed
            FROM task_category tc
            LEFT JOIN task_template tt ON tc.id = tt.task_category_id AND tt.deleted_at IS NULL
            LEFT JOIN task_application ta ON tt.id = ta.task_template_id AND ta.deleted_at IS NULL
            WHERE tc.residence_id = :residence_id AND tc.deleted_at IS NULL
            GROUP BY tc.name
        """),
        {"residence_id": residence_id}
    )

    by_category = {}
    for row in category_result.fetchall():
        by_category[row.name] = {
            'total': row.total,
            'completed': row.completed
        }

    # Last N days
    days_ago = datetime.utcnow() - timedelta(days=days)
    last_period_result = await db.scalar(
        select(func.count(TaskApplication.id)).where(
            TaskApplication.residence_id == residence_id,
            TaskApplication.applied_at >= days_ago,
            TaskApplication.deleted_at.is_(None)
        )
    )

    # Calculate change percentage - compare with previous period
    previous_days_ago = datetime.utcnow() - timedelta(days=days * 2)
    previous_period_result = await db.scalar(
        select(func.count(TaskApplication.id)).where(
            TaskApplication.residence_id == residence_id,
            TaskApplication.applied_at >= previous_days_ago,
            TaskApplication.applied_at < days_ago,
            TaskApplication.deleted_at.is_(None)
        )
    )

    # Calculate percentage change
    change_percentage = 0.0
    if previous_period_result and previous_period_result > 0:
        change_percentage = ((last_period_result or 0) - previous_period_result) / previous_period_result * 100
    elif last_period_result and last_period_result > 0:
        change_percentage = 100.0  # No data in previous period, but we have data now

    return TaskStats(
        total_applications=total_result or 0,
        completion_rate=completion_rate,
        by_category=by_category,
        last_30_days=last_period_result or 0,
        change_percentage=round(change_percentage, 1)
    )

async def get_device_stats(db: AsyncSession, residence_id: str, days: int = 30) -> DeviceStats:
    """Get device statistics"""
    # Calculate date range for filtering
    days_ago = datetime.utcnow() - timedelta(days=days)
    """Get device statistics"""
    # Total devices (all time)
    total_result = await db.scalar(
        select(func.count(Device.id)).where(
            Device.residence_id == residence_id,
            Device.deleted_at.is_(None)
        )
    )

    # New devices in the selected time period
    new_devices_result = await db.scalar(
        select(func.count(Device.id)).where(
            Device.residence_id == residence_id,
            Device.created_at >= days_ago,
            Device.deleted_at.is_(None)
        )
    )

    # Calculate change percentage - compare with previous period
    previous_days_ago = datetime.utcnow() - timedelta(days=days * 2)
    previous_period_result = await db.scalar(
        select(func.count(Device.id)).where(
            Device.residence_id == residence_id,
            Device.created_at >= previous_days_ago,
            Device.created_at < days_ago,
            Device.deleted_at.is_(None)
        )
    )

    # Calculate percentage change
    change_percentage = 0.0
    if previous_period_result and previous_period_result > 0:
        change_percentage = ((new_devices_result or 0) - previous_period_result) / previous_period_result * 100
    elif new_devices_result and new_devices_result > 0:
        change_percentage = 100.0  # No data in previous period, but we have data now

    # By type
    bp_device_result = await db.scalar(
        select(func.count(Device.id)).where(
            Device.residence_id == residence_id,
            Device.type == 'blood_pressure',
            Device.deleted_at.is_(None)
        )
    )

    spo2_device_result = await db.scalar(
        select(func.count(Device.id)).where(
            Device.residence_id == residence_id,
            Device.type == 'pulse_oximeter',
            Device.deleted_at.is_(None)
        )
    )

    scale_result = await db.scalar(
        select(func.count(Device.id)).where(
            Device.residence_id == residence_id,
            Device.type == 'scale',
            Device.deleted_at.is_(None)
        )
    )

    therm_result = await db.scalar(
        select(func.count(Device.id)).where(
            Device.residence_id == residence_id,
            Device.type == 'thermometer',
            Device.deleted_at.is_(None)
        )
    )

    by_type = {
        'blood_pressure': bp_device_result or 0,
        'pulse_oximeter': spo2_device_result or 0,
        'scale': scale_result or 0,
        'thermometer': therm_result or 0
    }

    # Low battery (< 20%)
    low_battery_result = await db.scalar(
        select(func.count(Device.id)).where(
            Device.residence_id == residence_id,
            Device.battery_percent < 20,
            Device.deleted_at.is_(None)
        )
    )

    # Average battery
    avg_battery_result = await db.scalar(
        select(func.avg(Device.battery_percent)).where(
            Device.residence_id == residence_id,
            Device.battery_percent.isnot(None),
            Device.deleted_at.is_(None)
        )
    )

    return DeviceStats(
        total_devices=total_result or 0,
        by_type=by_type,
        low_battery=low_battery_result or 0,
        average_battery=float(avg_battery_result or 0),
        new_devices=new_devices_result or 0,
        change_percentage=round(change_percentage, 1)
    )

async def get_new_resident_stats(db: AsyncSession, residence_id: str) -> NewResidentStats:
    """Get new resident statistics for the current year"""
    current_year = datetime.utcnow().year
    previous_year = current_year - 1

    # Get residents for current year
    current_year_result = await db.scalar(
        select(func.count(Resident.id)).where(
            Resident.residence_id == residence_id,
            Resident.deleted_at.is_(None),
            func.extract('year', Resident.created_at) == current_year
        )
    )

    # Get residents for previous year
    previous_year_result = await db.scalar(
        select(func.count(Resident.id)).where(
            Resident.residence_id == residence_id,
            Resident.deleted_at.is_(None),
            func.extract('year', Resident.created_at) == previous_year
        )
    )

    # Get total residents
    total_residents_result = await db.scalar(
        select(func.count(Resident.id)).where(
            Resident.residence_id == residence_id,
            Resident.deleted_at.is_(None)
        )
    )

    # Calculate growth percentage
    current_year_residents = current_year_result or 0
    previous_year_residents = previous_year_result or 0
    growth_percentage = 0.0

    if previous_year_residents > 0:
        growth_percentage = ((current_year_residents - previous_year_residents) / previous_year_residents) * 100
    elif current_year_residents > 0:
        growth_percentage = 100.0

    # Get monthly data for current year
    monthly_data = []
    for month in range(1, 13):
        month_start = datetime(current_year, month, 1)
        if month == 12:
            month_end = datetime(current_year + 1, 1, 1)
        else:
            month_end = datetime(current_year, month + 1, 1)

        month_residents = await db.scalar(
            select(func.count(Resident.id)).where(
                Resident.residence_id == residence_id,
                Resident.deleted_at.is_(None),
                Resident.created_at >= month_start,
                Resident.created_at < month_end
            )
        )

        monthly_data.append(MonthlyResidentData(
            month=datetime(current_year, month, 1).strftime('%b'),
            value=month_residents or 0
        ))

    return NewResidentStats(
        current_year=current_year,
        current_year_residents=current_year_residents,
        previous_year_residents=previous_year_residents,
        growth_percentage=round(growth_percentage, 1),
        total_residents=total_residents_result or 0,
        monthly_data=monthly_data
    )

async def get_yearly_comparison(db: AsyncSession, residence_id: str) -> List[YearComparison]:
    """Get yearly comparison data"""
    current_year = datetime.utcnow().year
    previous_year = current_year - 1

    years = []

    for year in [previous_year, current_year]:
        monthly_data = []

        for month in range(1, 13):
            month_start = datetime(year, month, 1)
            if month == 12:
                month_end = datetime(year + 1, 1, 1)
            else:
                month_end = datetime(year, month + 1, 1)

            # Residents count for this month
            residents_result = await db.scalar(
                select(func.count(Resident.id)).where(
                    Resident.residence_id == residence_id,
                    Resident.created_at >= month_start,
                    Resident.created_at < month_end,
                    Resident.deleted_at.is_(None)
                )
            )

            # Measurements count for this month
            measurements_result = await db.scalar(
                select(func.count(Measurement.id)).where(
                    Measurement.residence_id == residence_id,
                    Measurement.taken_at >= month_start,
                    Measurement.taken_at < month_end,
                    Measurement.deleted_at.is_(None)
                )
            )

            monthly_data.append(MonthlyData(
                month=f"{year}-{month:02d}",
                value=residents_result + measurements_result  # Combined metric
            ))

        years.append(YearComparison(year=year, data=monthly_data))

    return years

async def get_recent_activity(db: AsyncSession, residence_id: str, days: int = 30) -> List[Dict[str, Any]]:
    """Get recent activity across all entities"""
    days_ago = datetime.utcnow() - timedelta(days=days)

    # Recent residents
    recent_residents = await db.execute(
        select(
            Resident.id,
            Resident.full_name,
            Resident.created_at,
            Resident.status
        ).where(
            Resident.residence_id == residence_id,
            Resident.created_at >= days_ago,
            Resident.deleted_at.is_(None)
        ).order_by(Resident.created_at.desc()).limit(5)
    )

    # Recent measurements
    recent_measurements = await db.execute(
        select(
            Measurement.id,
            Measurement.type,
            Measurement.taken_at,
            Resident.full_name.label('resident_name')
        ).join(
            Resident, Measurement.resident_id == Resident.id
        ).where(
            Measurement.residence_id == residence_id,
            Measurement.taken_at >= days_ago,
            Measurement.deleted_at.is_(None)
        ).order_by(Measurement.taken_at.desc()).limit(5)
    )

    # Recent task applications
    recent_tasks = await db.execute(
        select(
            TaskApplication.id,
            TaskTemplate.name.label('task_name'),
            TaskApplication.applied_at,
            Resident.full_name.label('resident_name')
        ).join(
            Resident, TaskApplication.resident_id == Resident.id
        ).join(
            TaskTemplate, TaskApplication.task_template_id == TaskTemplate.id
        ).where(
            TaskApplication.residence_id == residence_id,
            TaskApplication.applied_at >= days_ago,
            TaskApplication.deleted_at.is_(None)
        ).order_by(TaskApplication.applied_at.desc()).limit(5)
    )

    activity = []

    # Add residents
    for resident in recent_residents.fetchall():
        activity.append({
            'type': 'resident',
            'id': resident.id,
            'description': f'New resident: {resident.full_name}',
            'timestamp': resident.created_at,
            'status': resident.status
        })

    # Add measurements
    for measurement in recent_measurements.fetchall():
        activity.append({
            'type': 'measurement',
            'id': measurement.id,
            'description': f'{measurement.type} measurement for {measurement.resident_name}',
            'timestamp': measurement.taken_at,
            'measurement_type': measurement.type
        })

    # Add task applications
    for task in recent_tasks.fetchall():
        activity.append({
            'type': 'task',
            'id': task.id,
            'description': f'Task applied: {task.task_name} for {task.resident_name}',
            'timestamp': task.applied_at,
            'task_name': task.task_name
        })

    # Sort by timestamp and return top 10
    activity.sort(key=lambda x: x['timestamp'], reverse=True)
    return activity[:10]

# -------------------- Main Dashboard Endpoint --------------------

@router.get("/", response_model=DashboardData)
async def get_dashboard_data(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
    time_filter: str = Query("year", regex="^(week|month|year)$", description="Time filter: week, month, or year"),
):
    """Get complete dashboard data"""
    await apply_residence_context(db, current, residence_id)

    # For superadmin users, if no residence_id is provided, get the first residence
    if not residence_id:
        if current["role"] == "superadmin":
            # Get first available residence
            result = await db.execute(
                select(Residence.id).where(Residence.deleted_at.is_(None)).limit(1)
            )
            first_residence = result.scalar_one_or_none()
            if not first_residence:
                raise HTTPException(status_code=404, detail="No residences found")
            residence_id = first_residence
        else:
            raise HTTPException(status_code=400, detail="Residence ID is required")

    # Convert time_filter to days
    days_map = {
        "week": 7,
        "month": 30,
        "year": 365
    }
    days = days_map[time_filter]

    # Get all statistics
    resident_stats = await get_resident_stats(db, residence_id, days)
    measurement_stats = await get_measurement_stats(db, residence_id, days)
    task_stats = await get_task_stats(db, residence_id, days)
    device_stats = await get_device_stats(db, residence_id, days)
    yearly_comparison = await get_yearly_comparison(db, residence_id)
    recent_activity = await get_recent_activity(db, residence_id, days)

    # Create metrics cards with dynamic change percentages
    def format_change_percentage(percentage: float) -> tuple[str, str]:
        """Format percentage change and determine if it's positive or negative"""
        if percentage > 0:
            return f"+{percentage:.1f}%", "positive"
        elif percentage < 0:
            return f"{percentage:.1f}%", "negative"
        else:
            return "0%", "positive"

    resident_change, resident_change_type = format_change_percentage(resident_stats.change_percentage)
    device_change, device_change_type = format_change_percentage(device_stats.change_percentage)
    measurement_change, measurement_change_type = format_change_percentage(measurement_stats.change_percentage)
    task_change, task_change_type = format_change_percentage(task_stats.change_percentage)

    metrics = [
        DashboardMetric(
            title="Residentes",
            value=str(resident_stats.new_residents),
            change=resident_change,
            changeType=resident_change_type,
            icon="people",
            color="primary",
            colorIcon="btn_lightblue"
        ),
        DashboardMetric(
            title="Dispositivos",
            value=str(device_stats.new_devices),
            change=device_change,
            changeType=device_change_type,
            icon="devices",
            color="success",
            colorIcon="btn_green"
        ),
        DashboardMetric(
            title="Mediciones",
            value=str(measurement_stats.last_30_days),
            change=measurement_change,
            changeType=measurement_change_type,
            icon="monitoring",
            color="warning",
            colorIcon="btn_orange"
        ),
        DashboardMetric(
            title="Tareas",
            value=str(task_stats.last_30_days),
            change=task_change,
            changeType=task_change_type,
            icon="task_alt",
            color="info",
            colorIcon="btn_purple"
        )
    ]

    return DashboardData(
        metrics=metrics,
        resident_stats=resident_stats,
        measurement_stats=measurement_stats,
        task_stats=task_stats,
        device_stats=device_stats,
        yearly_comparison=yearly_comparison,
        recent_activity=recent_activity
    )

# -------------------- Navigation Counts Endpoint --------------------

@router.get("/navigation-counts", response_model=NavigationCounts)
async def get_navigation_counts(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Get counts for navigation menu - returns all data the user can see based on their role"""

    # Base queries depending on user role - NO residence_id header needed for navigation counts
    if current["role"] == "superadmin":
        # Superadmin can see everything
        residences_query = select(func.count(Residence.id)).where(Residence.deleted_at.is_(None))

        # Get all users by role
        managers_query = select(func.count(User.id)).where(
            User.role == 'manager',
            User.deleted_at.is_(None)
        )
        professionals_query = select(func.count(User.id)).where(
            User.role == 'professional',
            User.deleted_at.is_(None)
        )

        # For all other entities, count all (superadmin sees everything)
        residents_query = select(func.count(Resident.id)).where(Resident.deleted_at.is_(None))
        floors_query = select(func.count(Floor.id)).where(Floor.deleted_at.is_(None))
        rooms_query = select(func.count(Room.id)).where(Room.deleted_at.is_(None))
        beds_query = select(func.count(Bed.id)).where(Bed.deleted_at.is_(None))
        categories_query = select(func.count(TaskCategory.id)).where(TaskCategory.deleted_at.is_(None))
        tasks_query = select(func.count(TaskApplication.id)).where(TaskApplication.deleted_at.is_(None))
        devices_query = select(func.count(Device.id)).where(Device.deleted_at.is_(None))
        measurements_query = select(func.count(Measurement.id)).where(Measurement.deleted_at.is_(None))

    else:
        # For managers and professionals, need to check which residences they have access to
        user_residences_query = select(UserResidence).where(
            UserResidence.user_id == current["id"],
            UserResidence.deleted_at.is_(None)
        )
        user_residences_result = await db.execute(user_residences_query)
        user_residences = user_residences_result.scalars().all()
        residence_ids = [ur.residence_id for ur in user_residences]

        if not residence_ids:
            # User has no access to any residences
            return NavigationCounts(
                residences=0,
                residents=0,
                floors=0,
                rooms=0,
                beds=0,
                managers=0,
                professionals=0,
                categories=0,
                tasks=0,
                devices=0,
                measurements=0
            )

        # Count based on accessible residences
        residences_query = select(func.count(Residence.id)).where(
            Residence.id.in_(residence_ids),
            Residence.deleted_at.is_(None)
        )

        # Count users by role across accessible residences
        managers_query = select(func.count(User.id)).join(
            UserResidence, User.id == UserResidence.user_id
        ).where(
            User.role == 'manager',
            UserResidence.residence_id.in_(residence_ids),
            User.deleted_at.is_(None),
            UserResidence.deleted_at.is_(None)
        )

        professionals_query = select(func.count(User.id)).join(
            UserResidence, User.id == UserResidence.user_id
        ).where(
            User.role == 'professional',
            UserResidence.residence_id.in_(residence_ids),
            User.deleted_at.is_(None),
            UserResidence.deleted_at.is_(None)
        )

        # Count entities from accessible residences
        residents_query = select(func.count(Resident.id)).where(
            Resident.residence_id.in_(residence_ids),
            Resident.deleted_at.is_(None)
        )
        floors_query = select(func.count(Floor.id)).where(
            Floor.residence_id.in_(residence_ids),
            Floor.deleted_at.is_(None)
        )
        rooms_query = select(func.count(Room.id)).where(
            Room.residence_id.in_(residence_ids),
            Room.deleted_at.is_(None)
        )
        beds_query = select(func.count(Bed.id)).where(
            Bed.residence_id.in_(residence_ids),
            Bed.deleted_at.is_(None)
        )
        categories_query = select(func.count(TaskCategory.id)).where(
            TaskCategory.residence_id.in_(residence_ids),
            TaskCategory.deleted_at.is_(None)
        )
        tasks_query = select(func.count(TaskApplication.id)).where(
            TaskApplication.residence_id.in_(residence_ids),
            TaskApplication.deleted_at.is_(None)
        )
        devices_query = select(func.count(Device.id)).where(
            Device.residence_id.in_(residence_ids),
            Device.deleted_at.is_(None)
        )
        measurements_query = select(func.count(Measurement.id)).where(
            Measurement.residence_id.in_(residence_ids),
            Measurement.deleted_at.is_(None)
        )

    # Execute all queries
    residences = await db.scalar(residences_query) or 0
    residents = await db.scalar(residents_query) or 0
    floors = await db.scalar(floors_query) or 0
    rooms = await db.scalar(rooms_query) or 0
    beds = await db.scalar(beds_query) or 0
    managers = await db.scalar(managers_query) or 0
    professionals = await db.scalar(professionals_query) or 0
    categories = await db.scalar(categories_query) or 0
    tasks = await db.scalar(tasks_query) or 0
    devices = await db.scalar(devices_query) or 0
    measurements = await db.scalar(measurements_query) or 0

    return NavigationCounts(
        residences=residences,
        residents=residents,
        floors=floors,
        rooms=rooms,
        beds=beds,
        managers=managers,
        professionals=professionals,
        categories=categories,
        tasks=tasks,
        devices=devices,
        measurements=measurements
    )

# -------------------- Individual Stats Endpoints --------------------

@router.get("/residents/stats", response_model=ResidentStats)
async def get_residents_stats(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
    time_filter: str = Query("year", regex="^(week|month|year)$", description="Time filter: week, month, or year"),
):
    """Get resident statistics only"""
    await apply_residence_context(db, current, residence_id)
    if not residence_id:
        raise HTTPException(status_code=400, detail="Residence ID is required")
    # Convert time_filter to days
    days_map = {
        "week": 7,
        "month": 30,
        "year": 365
    }
    days = days_map[time_filter]
    return await get_resident_stats(db, residence_id, days)

@router.get("/measurements/stats", response_model=MeasurementStats)
async def get_measurements_stats(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
    time_filter: str = Query("year", regex="^(week|month|year)$", description="Time filter: week, month, or year"),
):
    """Get measurement statistics only"""
    await apply_residence_context(db, current, residence_id)
    if not residence_id:
        raise HTTPException(status_code=400, detail="Residence ID is required")

    # Convert time_filter to days
    days_map = {
        "week": 7,
        "month": 30,
        "year": 365
    }
    days = days_map[time_filter]

    return await get_measurement_stats(db, residence_id, days)

@router.get("/tasks/stats", response_model=TaskStats)
async def get_tasks_stats(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
    time_filter: str = Query("year", regex="^(week|month|year)$", description="Time filter: week, month, or year"),
):
    """Get task statistics only"""
    await apply_residence_context(db, current, residence_id)
    if not residence_id:
        raise HTTPException(status_code=400, detail="Residence ID is required")

    # Convert time_filter to days
    days_map = {
        "week": 7,
        "month": 30,
        "year": 365
    }
    days = days_map[time_filter]

    return await get_task_stats(db, residence_id, days)

@router.get("/devices/stats", response_model=DeviceStats)
async def get_devices_stats(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
    time_filter: str = Query("year", regex="^(week|month|year)$", description="Time filter: week, month, or year"),
):
    """Get device statistics only"""
    await apply_residence_context(db, current, residence_id)
    if not residence_id:
        raise HTTPException(status_code=400, detail="Residence ID is required")
    # Convert time_filter to days
    days_map = {
        "week": 7,
        "month": 30,
        "year": 365
    }
    days = days_map[time_filter]
    return await get_device_stats(db, residence_id, days)

@router.get("/new-residents/stats", response_model=NewResidentStats)
async def get_new_residents_stats(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
):
    """Get new resident statistics for current year"""
    await apply_residence_context(db, current, residence_id)
    if not residence_id:
        raise HTTPException(status_code=400, detail="Residence ID is required")
    return await get_new_resident_stats(db, residence_id)

@router.get("/task-categories", response_model=list[TaskCategoryWithCount])
async def get_task_categories_with_counts(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
):
    """Get task categories with task counts for dashboard"""
    await apply_residence_context(db, current, residence_id)

    # If no specific residence_id, get all residences the user has access to
    if not residence_id:
        if current["role"] == "superadmin":
            # Get all residences for superadmin
            residences_query = select(Residence).where(Residence.deleted_at.is_(None))
            residences_result = await db.execute(residences_query)
            residences = residences_result.scalars().all()
        else:
            # Get residences assigned to user
            user_residences_query = select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.deleted_at.is_(None)
            )
            user_residences_result = await db.execute(user_residences_query)
            user_residences = user_residences_result.scalars().all()
            residence_ids = [ur.residence_id for ur in user_residences]

            residences_query = select(Residence).where(
                Residence.id.in_(residence_ids),
                Residence.deleted_at.is_(None)
            )
            residences_result = await db.execute(residences_query)
            residences = residences_result.scalars().all()
    else:
        # Get specific residence
        residences_query = select(Residence).where(
            Residence.id == residence_id,
            Residence.deleted_at.is_(None)
        )
        residences_result = await db.execute(residences_query)
        residences = residences_result.scalars().all()

    categories_with_counts = []

    for residence in residences:
        # Get categories for this residence
        categories_query = select(TaskCategory).where(
            TaskCategory.residence_id == residence.id,
            TaskCategory.deleted_at.is_(None)
        )
        categories_result = await db.execute(categories_query)
        categories = categories_result.scalars().all()

        for category in categories:
            # Count task applications for this category using TaskTemplate
            active_tasks_query = select(func.count(TaskApplication.id)).join(
                TaskTemplate, TaskApplication.task_template_id == TaskTemplate.id
            ).where(
                TaskTemplate.task_category_id == category.id,
                TaskApplication.deleted_at.is_(None),
                TaskApplication.selected_status_index.is_(None)
            )
            active_tasks_result = await db.execute(active_tasks_query)
            active_tasks_count = active_tasks_result.scalar() or 0

            completed_tasks_query = select(func.count(TaskApplication.id)).join(
                TaskTemplate, TaskApplication.task_template_id == TaskTemplate.id
            ).where(
                TaskTemplate.task_category_id == category.id,
                TaskApplication.deleted_at.is_(None),
                TaskApplication.selected_status_index.is_not(None)
            )
            completed_tasks_result = await db.execute(completed_tasks_query)
            completed_tasks_count = completed_tasks_result.scalar() or 0

            total_tasks_count = active_tasks_count + completed_tasks_count

            categories_with_counts.append(TaskCategoryWithCount(
                id=category.id,
                name=category.name,
                description=None,
                icon=None,
                color=None,
                residence_id=residence.id,
                residence_name=residence.name,
                task_count=total_tasks_count,
                active_tasks=active_tasks_count,
                completed_tasks=completed_tasks_count
            ))

    return categories_with_counts

@router.get("/activity", response_model=list[dict])
async def get_dashboard_activity(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
):
    """Get recent activity only"""
    await apply_residence_context(db, current, residence_id)
    if not residence_id:
        raise HTTPException(status_code=400, detail="Residence ID is required")

    # Override the 30 days default with user parameter
    original_func = get_recent_activity

    async def get_recent_activity_custom(db: AsyncSession, residence_id: str) -> List[Dict[str, Any]]:
        thirty_days_ago = datetime.utcnow() - timedelta(days=days)

        # Recent residents
        recent_residents = await db.execute(
            select(
                Resident.id,
                Resident.full_name,
                Resident.created_at,
                Resident.status
            ).where(
                Residence.residence_id == residence_id,
                Resident.created_at >= thirty_days_ago,
                Resident.deleted_at.is_(None)
            ).order_by(Resident.created_at.desc()).limit(5)
        )

        # Recent measurements
        recent_measurements = await db.execute(
            select(
                Measurement.id,
                Measurement.type,
                Measurement.taken_at,
                Resident.full_name.label('resident_name')
            ).join(
                Resident, Measurement.resident_id == Resident.id
            ).where(
                Measurement.residence_id == residence_id,
                Measurement.taken_at >= thirty_days_ago,
                Measurement.deleted_at.is_(None)
            ).order_by(Measurement.taken_at.desc()).limit(5)
        )

        # Recent task applications
        recent_tasks = await db.execute(
            select(
                TaskApplication.id,
                TaskTemplate.name.label('task_name'),
                TaskApplication.applied_at,
                Resident.full_name.label('resident_name')
            ).join(
                Resident, TaskApplication.resident_id == Resident.id
            ).join(
                TaskTemplate, TaskApplication.task_template_id == TaskTemplate.id
            ).where(
                TaskApplication.residence_id == residence_id,
                TaskApplication.applied_at >= thirty_days_ago,
                TaskApplication.deleted_at.is_(None)
            ).order_by(TaskApplication.applied_at.desc()).limit(5)
        )

        activity = []

        # Add residents
        for resident in recent_residents.fetchall():
            activity.append({
                'type': 'resident',
                'id': resident.id,
                'description': f'New resident: {resident.full_name}',
                'timestamp': resident.created_at,
                'status': resident.status
            })

        # Add measurements
        for measurement in recent_measurements.fetchall():
            activity.append({
                'type': 'measurement',
                'id': measurement.id,
                'description': f'{measurement.type} measurement for {measurement.resident_name}',
                'timestamp': measurement.taken_at,
                'measurement_type': measurement.type
            })

        # Add task applications
        for task in recent_tasks.fetchall():
            activity.append({
                'type': 'task',
                'id': task.id,
                'description': f'Task applied: {task.task_name} for {task.resident_name}',
                'timestamp': task.applied_at,
                'task_name': task.task_name
            })

        # Sort by timestamp and return top 10
        activity.sort(key=lambda x: x['timestamp'], reverse=True)
        return activity[:10]

    return await get_recent_activity_custom(db, residence_id)