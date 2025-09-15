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
    User, UserResidence, TaskTemplate, Floor, Room, Bed
)
from app.schemas import (
    DashboardData, DashboardMetric, ResidentStats,
    MeasurementStats, TaskStats, DeviceStats,
    MonthlyData, YearComparison
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# -------------------- Helper Functions --------------------

async def apply_residence_context(db: AsyncSession, current: dict, residence_id: str | None):
    """Apply residence context for RLS"""
    if residence_id:
        if current["role"] != "superadmin":
            result = await db.execute(
                select(UserResidence).where(
                    UserResidence.user_id == current["id"],
                    UserResidence.residence_id == residence_id,
                )
            )
            if result.scalar_one_or_none() is None:
                raise HTTPException(status_code=403, detail="Access denied to this residence")

        await db.execute(text("SELECT set_config('app.residence_id', :rid, true)"), {"rid": residence_id})
    elif current["role"] != "superadmin":
        raise HTTPException(status_code=400, detail="Residence ID required for non-superadmin users")

async def get_resident_stats(db: AsyncSession, residence_id: str) -> ResidentStats:
    """Get resident statistics"""
    # Total residents
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

    return ResidentStats(
        total=total_result or 0,
        active=active_result or 0,
        discharged=discharged_result or 0,
        deceased=deceased_result or 0,
        with_bed=with_bed_result or 0,
        without_bed=without_bed_result or 0
    )

async def get_measurement_stats(db: AsyncSession, residence_id: str) -> MeasurementStats:
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

    # Last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    last_30_result = await db.scalar(
        select(func.count(Measurement.id)).where(
            Measurement.residence_id == residence_id,
            Measurement.taken_at >= thirty_days_ago,
            Measurement.deleted_at.is_(None)
        )
    )

    # Trend (compare with previous 30 days)
    sixty_days_ago = datetime.utcnow() - timedelta(days=60)
    previous_30_result = await db.scalar(
        select(func.count(Measurement.id)).where(
            Measurement.residence_id == residence_id,
            Measurement.taken_at >= sixty_days_ago,
            Measurement.taken_at < thirty_days_ago,
            Measurement.deleted_at.is_(None)
        )
    )

    trend = 'stable'
    if last_30_result and previous_30_result:
        if last_30_result > previous_30_result * 1.1:
            trend = 'increasing'
        elif last_30_result < previous_30_result * 0.9:
            trend = 'decreasing'

    return MeasurementStats(
        total_measurements=total_result or 0,
        by_type=by_type,
        by_source=by_source,
        last_30_days=last_30_result or 0,
        trend=trend
    )

async def get_task_stats(db: AsyncSession, residence_id: str) -> TaskStats:
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

    # Last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    last_30_result = await db.scalar(
        select(func.count(TaskApplication.id)).where(
            TaskApplication.residence_id == residence_id,
            TaskApplication.applied_at >= thirty_days_ago,
            TaskApplication.deleted_at.is_(None)
        )
    )

    return TaskStats(
        total_applications=total_result or 0,
        completion_rate=completion_rate,
        by_category=by_category,
        last_30_days=last_30_result or 0
    )

async def get_device_stats(db: AsyncSession, residence_id: str) -> DeviceStats:
    """Get device statistics"""
    # Total devices
    total_result = await db.scalar(
        select(func.count(Device.id)).where(
            Device.residence_id == residence_id,
            Device.deleted_at.is_(None)
        )
    )

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
        average_battery=float(avg_battery_result or 0)
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

async def get_recent_activity(db: AsyncSession, residence_id: str) -> List[Dict[str, Any]]:
    """Get recent activity across all entities"""
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    # Recent residents
    recent_residents = await db.execute(
        select(
            Resident.id,
            Resident.full_name,
            Resident.created_at,
            Resident.status
        ).where(
            Resident.residence_id == residence_id,
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

# -------------------- Main Dashboard Endpoint --------------------

@router.get("/", response_model=DashboardData)
async def get_dashboard_data(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Header(None, alias="X-Residence-Id"),
):
    """Get complete dashboard data"""
    await apply_residence_context(db, current, residence_id)

    if not residence_id:
        raise HTTPException(status_code=400, detail="Residence ID is required")

    # Get all statistics
    resident_stats = await get_resident_stats(db, residence_id)
    measurement_stats = await get_measurement_stats(db, residence_id)
    task_stats = await get_task_stats(db, residence_id)
    device_stats = await get_device_stats(db, residence_id)
    yearly_comparison = await get_yearly_comparison(db, residence_id)
    recent_activity = await get_recent_activity(db, residence_id)

    # Create metrics cards
    metrics = [
        DashboardMetric(
            title="Total Residents",
            value=str(resident_stats.total),
            change="+5%",
            changeType="positive",
            icon="people",
            color="primary",
            colorIcon="bg-blue-500"
        ),
        DashboardMetric(
            title="Active Devices",
            value=str(device_stats.total_devices),
            change="+2%",
            changeType="positive",
            icon="devices",
            color="success",
            colorIcon="bg-green-500"
        ),
        DashboardMetric(
            title="Measurements",
            value=str(measurement_stats.total_measurements),
            change="+12%",
            changeType="positive",
            icon="monitoring",
            color="warning",
            colorIcon="bg-yellow-500"
        ),
        DashboardMetric(
            title="Task Completion",
            value=f"{task_stats.completion_rate:.1f}%",
            change="-3%",
            changeType="negative",
            icon="task_alt",
            color="info",
            colorIcon="bg-purple-500"
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

# -------------------- Individual Stats Endpoints --------------------

@router.get("/residents/stats", response_model=ResidentStats)
async def get_residents_stats(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Header(None, alias="X-Residence-Id"),
):
    """Get resident statistics only"""
    await apply_residence_context(db, current, residence_id)
    if not residence_id:
        raise HTTPException(status_code=400, detail="Residence ID is required")
    return await get_resident_stats(db, residence_id)

@router.get("/measurements/stats", response_model=MeasurementStats)
async def get_measurements_stats(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Header(None, alias="X-Residence-Id"),
):
    """Get measurement statistics only"""
    await apply_residence_context(db, current, residence_id)
    if not residence_id:
        raise HTTPException(status_code=400, detail="Residence ID is required")
    return await get_measurement_stats(db, residence_id)

@router.get("/tasks/stats", response_model=TaskStats)
async def get_tasks_stats(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Header(None, alias="X-Residence-Id"),
):
    """Get task statistics only"""
    await apply_residence_context(db, current, residence_id)
    if not residence_id:
        raise HTTPException(status_code=400, detail="Residence ID is required")
    return await get_task_stats(db, residence_id)

@router.get("/devices/stats", response_model=DeviceStats)
async def get_devices_stats(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Header(None, alias="X-Residence-Id"),
):
    """Get device statistics only"""
    await apply_residence_context(db, current, residence_id)
    if not residence_id:
        raise HTTPException(status_code=400, detail="Residence ID is required")
    return await get_device_stats(db, residence_id)

@router.get("/activity", response_model=list[dict])
async def get_dashboard_activity(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Header(None, alias="X-Residence-Id"),
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