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
    ScopeType,
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
        log.info(
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
            scope=data.scope.value,
            subteam_id=str(data.subteam_id) if data.subteam_id else None,
            scheduled_date=data.scheduled_date.isoformat(),
        )
        log.info("schedule_generation_started")

        # 0. Check if a schedule already exists for this date/department/subteam combination
        # For SUBTEAM scope: check if schedule exists for that specific subteam
        # For DEPARTMENT_ONLY/DEPARTMENT_ALL: check if department-level schedule exists (subteam_id=null)
        check_subteam_id = data.subteam_id if data.scope == ScopeType.SUBTEAM else None
        existing_schedule = self.schedule_repo.get_existing_schedule(
            data.department_id, data.scheduled_date, check_subteam_id
        )
        if existing_schedule:
            scope_description = "subteam" if existing_schedule.subteam_id else "department"
            raise ValueError(
                f"A schedule already exists for this {scope_description} on {data.scheduled_date.isoformat()}. "
                f"Please edit or delete the existing schedule (ID: {existing_schedule.id}) instead."
            )

        # 1. Resolve workers needed based on scope
        department = self.department_repo.get_by_id(data.department_id)
        if not department:
            raise ValueError(f"Department {data.department_id} not found")

        if data.scope == ScopeType.SUBTEAM:
            # Get the subteam and its workers_per_slot
            # Type assertion: validator ensures subteam_id is not None when scope is SUBTEAM
            assert data.subteam_id is not None
            subteam = self.subteam_repo.get_by_id(data.subteam_id)
            if not subteam:
                raise ValueError(f"Subteam {data.subteam_id} not found")
            workers_needed = subteam.workers_per_slot if subteam.workers_per_slot else department.workers_per_slot
            log.info("workers_needed_from_subteam", count=workers_needed)
        elif data.scope == ScopeType.DEPARTMENT_ONLY:
            # Use department's workers_per_slot for department-only workers
            workers_needed = department.workers_per_slot
            log.info("workers_needed_from_department", count=workers_needed)
        else:  # ScopeType.DEPARTMENT_ALL
            # For department-wide schedule, use department's workers_per_slot
            workers_needed = department.workers_per_slot
            log.info("workers_needed_for_department_all", count=workers_needed)

        # 2. Get eligible workers based on scope
        if data.scope == ScopeType.SUBTEAM:
            # Get workers specifically assigned to this subteam
            # Type assertion: validator ensures subteam_id is not None when scope is SUBTEAM
            assert data.subteam_id is not None
            subteam_with_workers = self.subteam_repo.get_with_workers(data.subteam_id)
            if subteam_with_workers:
                eligible_workers = [w.worker for w in subteam_with_workers if w.worker and w.worker.is_active]
            else:
                eligible_workers = []
        elif data.scope == ScopeType.DEPARTMENT_ONLY:
            # Get workers assigned to department but NOT in any subteam
            eligible_workers_response = self.worker_repo.get_department_only_workers(data.department_id)
            eligible_workers = [Worker(**w.model_dump()) for w in eligible_workers_response]
            eligible_workers = [w for w in eligible_workers if w.is_active]
        else:  # ScopeType.DEPARTMENT_ALL
            # Get all workers in department (both subteam and department-only workers)
            eligible_workers_response = self.worker_repo.get_workers_by_department(data.department_id)
            eligible_workers = [Worker(**w.model_dump()) for w in eligible_workers_response]
            eligible_workers = [w for w in eligible_workers if w.is_active]

        log.info("eligible_workers", count=len(eligible_workers))

        if not eligible_workers:
            scope_msg = {
                ScopeType.SUBTEAM: "subteam",
                ScopeType.DEPARTMENT_ONLY: "department (department-only workers)",
                ScopeType.DEPARTMENT_ALL: "department",
            }
            raise ValueError(f"No workers found for this {scope_msg.get(data.scope, 'scope')}")

        # 3. Filter by availability — day_of_week in DB is 0=Sunday, Python is 0=Monday
        day_of_week = data.scheduled_date.weekday()
        db_day_of_week = (day_of_week + 1) % 7

        available_workers = [
            w for w in eligible_workers if self._is_worker_available(w.id, data.scheduled_date, db_day_of_week)
        ]

        log.info("available_workers_after_availability_filter", count=len(available_workers))

        # 4. Filter out workers already scheduled on this date (prevent double-scheduling)
        already_scheduled_worker_ids = self.schedule_repo.get_workers_scheduled_on_date(data.scheduled_date)
        available_workers = [w for w in available_workers if w.id not in already_scheduled_worker_ids]

        log.info(
            "available_workers_after_conflict_filter",
            count=len(available_workers),
            filtered_out=len(already_scheduled_worker_ids),
        )

        if not available_workers:
            if already_scheduled_worker_ids:
                raise ValueError(
                    f"No available workers found for {data.scheduled_date}. "
                    f"{len(already_scheduled_worker_ids)} worker(s) already scheduled on this date."
                )
            else:
                raise ValueError(f"No available workers found for {data.scheduled_date}")

        # 5. Sort by round-robin fairness (scoped to department/subteam)
        available_workers = self._sort_by_round_robin(
            available_workers, data.department_id, data.subteam_id if data.scope == ScopeType.SUBTEAM else None
        )

        log.info(
            "available_workers_after_round_robin", count=len(available_workers), available_workers=available_workers
        )

        # 6. Pick top N and create schedule + assignments
        selected = available_workers[:workers_needed]

        if len(selected) < (workers_needed or 0):
            log.warning(
                "insufficient_workers_selected",
                needed=workers_needed,
                selected=len(selected),
            )
        log.info(
            "workers_selected",
            count=len(selected),
            worker_ids=[str(w.id) for w in selected],
        )

        # get the created_by user
        created_by_user = self.worker_repo.get_by_email(created_by)
        if not created_by_user:
            raise ValueError(f"User with email {created_by} not found")

        # Set subteam_id based on scope: only SUBTEAM scope has subteam_id, others are None
        schedule_subteam_id = str(data.subteam_id) if data.scope == ScopeType.SUBTEAM else None

        schedule_data = {
            "department_id": str(data.department_id),
            "subteam_id": schedule_subteam_id,
            "title": data.title,
            "scheduled_date": data.scheduled_date.isoformat(),
            "start_time": data.start_time.isoformat(),
            "end_time": data.end_time.isoformat(),
            "notes": data.notes,
            "reminder_days_before": data.reminder_days_before,
            "created_by": str(created_by_user.id),
        }
        schedule = self.schedule_repo.create(schedule_data)

        # Get the subteam_id for each worker if DEPARTMENT_ALL scope to correctly set it on the assignment
        worker_subteams: dict[UUID, str | None] = {}
        if data.scope == ScopeType.DEPARTMENT_ALL:
            for w in selected:
                # Get the worker's subteam
                worker_subteam = self.subteam_repo.get_subteam_for_worker_in_department(w.id, data.department_id)
                worker_subteams[w.id] = str(worker_subteam.id) if worker_subteam else None
            logger.info("worker_subteams_resolved_for_department_all", worker_subteams=worker_subteams)

        assignments = [
            {
                "schedule_id": str(schedule.id),
                "worker_id": str(worker.id),
                "subteam_id": worker_subteams.get(worker.id, schedule_subteam_id)
                if data.scope == ScopeType.DEPARTMENT_ALL
                else schedule_subteam_id,
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

    def _sort_by_round_robin(
        self, workers: list[Worker], department_id: UUID, subteam_id: UUID | None = None
    ) -> list[Worker]:
        """
        Sort workers by round-robin fairness, scoped to department or subteam.

        Workers with the oldest last assignment date (or never assigned) get priority.
        Assignment history is filtered by scope:
        - If subteam_id provided: Only count assignments for that specific subteam
        - If subteam_id is None: Only count department-level assignments (subteam_id IS NULL)

        Args:
            workers: List of workers to sort
            department_id: Department ID to scope the round-robin fairness
            subteam_id: Optional subteam ID to further scope fairness

        Returns:
            Sorted list of workers (least recently assigned first)
        """

        def last_assigned(worker: Worker) -> date:
            log = self.logger.bind(
                method="_sort_by_round_robin.last_assigned",
                worker_id=str(worker.id),
                department_id=str(department_id),
                subteam_id=str(subteam_id) if subteam_id else None,
            )
            assignments = self.schedule_repo.get_assignments_for_worker(worker.id)

            # Filter assignments to match the scope
            filtered_assignments = [
                a
                for a in assignments
                if hasattr(a, "schedules")
                and a.schedules
                and a.schedules.department_id == department_id
                and (
                    # For subteam scope: match specific subteam
                    (subteam_id is not None and a.schedules.subteam_id == subteam_id)
                    # For department scope: only department-level schedules (subteam_id IS NULL)
                    or (subteam_id is None and a.schedules.subteam_id is None)
                )
            ]

            log.info(
                "worker_assignments_for_round_robin",
                total_assignments=len(assignments),
                filtered_assignments=len(filtered_assignments),
            )

            if not filtered_assignments:
                log.info("worker_never_assigned_in_scope, returning date.min")
                return date.min

            dates = [
                a.schedules.scheduled_date
                for a in filtered_assignments
                if a.schedules is not None
                and hasattr(a.schedules, "scheduled_date")
                and a.schedules.scheduled_date is not None
            ]
            log.info(
                "assignment_dates_for_worker_in_scope",
                count=len(dates),
                dates=dates,
            )
            return max(dates) if dates else date.min

        return sorted(
            workers,
            key=last_assigned,
        )
