from datetime import date
from uuid import UUID

from app.core.logging import get_logger
from app.repository.availabilities.repository import AvailabilityRepository
from app.repository.departments.repository import DepartmentRepository
from app.repository.schedules.repository import ScheduleRepository
from app.repository.subteams.repository import SubteamRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.models import AssignmentStatus, AvailabilityType
from app.schemas.schedules.models import (
    AssignmentResponse,
    ScheduleCreate,
    ScheduleResponse,
)
from app.schemas.workers.models import Worker

logger = get_logger(__name__)


class ScheduleService:
    def __init__(
        self,
        schedule_repo: ScheduleRepository,
        worker_repo: WorkerRepository,
        department_repo: DepartmentRepository,
        subteam_repo: SubteamRepository,
        availability_repo: AvailabilityRepository,
    ) -> None:
        self.schedule_repo = schedule_repo
        self.worker_repo = worker_repo
        self.department_repo = department_repo
        self.subteam_repo = subteam_repo
        self.availability_repo = availability_repo

        # bind the logger to the service name for structured logging
        self.logger = logger.bind(service="ScheduleService")

    def get_schedule(self, schedule_id: UUID) -> ScheduleResponse:
        # bind the method and schedule_id for better traceability in logs
        log = self.logger.bind(method="get_schedule", schedule_id=str(schedule_id))
        schedule = self.schedule_repo.get_with_assignments(schedule_id)
        if not schedule:
            log.warning("schedule_not_found")
            raise ValueError(f"Schedule {schedule_id} not found")
        return schedule

    def get_schedules_by_department(self, department_id: UUID) -> list[ScheduleResponse]:
        # bind the method and department_id for better traceability in logs
        log = self.logger.bind(method="get_schedules_by_department", department_id=str(department_id))
        schedules = self.schedule_repo.get_by_department(department_id)
        log.debug(
            "fetched_schedules_by_department",
            count=len(schedules),
        )
        return schedules

    def get_worker_assignments(self, worker_id: UUID) -> list[AssignmentResponse]:
        log = self.logger.bind(method="get_worker_assignments", worker_id=str(worker_id))
        log.info("fetching_worker_assignments")
        return self.schedule_repo.get_assignments_for_worker(worker_id)

    def generate_schedule(self, data: ScheduleCreate, created_by: str) -> ScheduleResponse | None:
        # bind the method and key parameters for better traceability in logs
        log = self.logger.bind(
            method="generate_schedule",
            department_id=str(data.department_id),
            subteam_id=str(data.subteam_id) if data.subteam_id else None,
            scheduled_date=data.scheduled_date.isoformat(),
        )
        log.info("schedule_generation_started")

        # 1. Resolve workers needed
        department = self.department_repo.get_by_id(data.department_id)
        if not department:
            raise ValueError(f"Department {data.department_id} not found")

        if data.subteam_id:
            # Get the subteam
            subteam = self.subteam_repo.get_by_id(data.subteam_id)
            if not subteam:
                log.warning("subteam not found", subteam_id=str(data.subteam_id))
            else:
                workers_needed = subteam.workers_per_slot
                log.debug("workers_needed", count=workers_needed)
        else:
            workers_needed = department.workers_per_slot
            log.debug("workers_needed_from_department", count=workers_needed)

        # 2. Get eligible workers
        if data.subteam_id:
            subteam_with_workers = self.subteam_repo.get_with_workers(data.subteam_id)
            if subteam_with_workers:
                eligible_workers = [w.worker for w in subteam_with_workers if w.worker and w.worker.is_active]
            else:
                eligible_workers = []
        else:
            eligible_workers_response = self.worker_repo.get_workers_by_department(data.department_id)
            eligible_workers = [Worker(**w.model_dump()) for w in eligible_workers_response]
        eligible_workers = [w for w in eligible_workers if w.is_active]

        log.debug("eligible_workers", count=len(eligible_workers))

        if not eligible_workers:
            raise ValueError("No workers found for this department/subteam")

        # 3. Filter by availability — day_of_week in DB is 0=Sunday, Python is 0=Monday
        day_of_week = data.scheduled_date.weekday()
        db_day_of_week = (day_of_week + 1) % 7

        available_workers = [
            w for w in eligible_workers if self._is_worker_available(w.id, data.scheduled_date, db_day_of_week)
        ]

        log.debug("available_workers_after_filter", count=len(available_workers), available_workers=available_workers)

        if not available_workers:
            raise ValueError(f"No available workers found for {data.scheduled_date}")

        # 4. Sort by round-robin fairness
        available_workers = self._sort_by_round_robin(available_workers)

        log.debug(
            "available_workers_after_round_robin", count=len(available_workers), available_workers=available_workers
        )

        # 5. Pick top N and create schedule + assignments
        selected = available_workers[:workers_needed]
        log.info(
            "workers_selected",
            count=len(selected),
            worker_ids=[str(w.id) for w in selected],
        )

        # get the created_by user
        created_by_user = self.worker_repo.get_by_email(created_by)
        if not created_by_user:
            raise ValueError(f"User with email {created_by} not found")

        schedule_data = {
            "department_id": str(data.department_id),
            "subteam_id": str(data.subteam_id) if data.subteam_id else None,
            "title": data.title,
            "scheduled_date": data.scheduled_date.isoformat(),
            "start_time": data.start_time.isoformat(),
            "end_time": data.end_time.isoformat(),
            "notes": data.notes,
            "reminder_days_before": data.reminder_days_before,
            "created_by": str(created_by_user.id),
        }
        schedule = self.schedule_repo.create(schedule_data)

        assignments = [
            {
                "schedule_id": str(schedule.id),
                "worker_id": str(worker.id),
                "subteam_id": str(data.subteam_id) if data.subteam_id else None,
                "status": AssignmentStatus.PENDING,
            }
            for worker in selected
        ]
        self.schedule_repo.bulk_create_assignments(assignments)

        log.info(
            "schedule_generation_completed",
            schedule_id=str(schedule.id),
            assignments_created=len(assignments),
        )

        return self.schedule_repo.get_with_assignments(schedule.id)

    def update_assignment_status(self, assignment_id: UUID, status: AssignmentStatus) -> AssignmentResponse:
        log = self.logger.bind(method="update_assignment_status", assignment_id=str(assignment_id), status=status.value)
        updated = self.schedule_repo.update_assignment_status(assignment_id, status)
        if not updated:
            log.warning("assignment_not_found", assignment_id=str(assignment_id))
            raise ValueError(f"Assignment {assignment_id} not found")
        log.info(
            "assignment_status_updated",
            assignment_id=str(assignment_id),
            status=status,
        )
        return updated

    def delete_schedule(self, schedule_id: UUID) -> None:
        log = self.logger.bind(method="delete_schedule", schedule_id=str(schedule_id))
        self.schedule_repo.delete_assignments_for_schedule(schedule_id)
        self.schedule_repo.delete(schedule_id)
        log.info("schedule_deleted")

    # ----------------------------------------------------------------
    # Private helpers
    # ----------------------------------------------------------------

    def _is_worker_available(self, worker_id: UUID, scheduled_date: date, day_of_week: int) -> bool:
        # Specific date override takes precedence over recurring
        specific = self.availability_repo.get_by_worker_and_type(
            worker_id,
            availability_type=AvailabilityType.SPECIFIC_DATE,
            specific_date=scheduled_date,
        )
        if specific is not None:
            return specific.is_available

        recurring = self.availability_repo.get_by_worker_and_day(worker_id, day_of_week)
        if recurring is not None:
            return recurring.is_available

        return True  # default to available if no record exists

    def _sort_by_round_robin(self, workers: list[Worker]) -> list[Worker]:
        def last_assigned(worker: Worker) -> date:
            log = self.logger.bind(method="_sort_by_round_robin.last_assigned", worker_id=str(worker.id))
            assignments = self.schedule_repo.get_assignments_for_worker(worker.id)
            log.debug(
                "worker_assignments_for_round_robin",
                count=len(assignments),
                assignments=assignments,
            )
            if not assignments:
                log.debug("worker_never_assigned, returning date.min")
                return date.min
            dates = [
                a.schedules.scheduled_date
                for a in assignments
                if hasattr(a, "schedules") and hasattr(a.schedules, "scheduled_date") and a.schedules
            ]
            log.debug(
                "assignment_dates_for_worker",
                count=len(dates),
                dates=dates,
            )
            return max(dates) if dates else date.min

        return sorted(
            workers,
            key=last_assigned,
        )
