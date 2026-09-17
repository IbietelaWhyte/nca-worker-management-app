from datetime import date
from uuid import UUID

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.repository.schedules.repository import ScheduleRepository
from app.repository.worker_leave.repository import WorkerLeaveRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.worker_leave.models import (
    CurrentLeave,
    LeaveClash,
    LeaveClashReport,
    WorkerLeaveCreate,
    WorkerLeaveResponse,
)

logger = get_logger(__name__)


class WorkerLeaveService:
    """Records the stretches a worker is away.

    Leave does two things and deliberately only two: it takes a worker out of schedule
    generation for the dates it covers, and it stops the availability prompt texting them while
    they are away. It never edits the rota — see `get_clashes`.

    It is not the same as deactivating a worker. Deactivation removes somebody from their
    departments and from every roster; leave is temporary and leaves their membership, roles and
    history intact, so they come back without being re-added.
    """

    def __init__(
        self,
        leave_repo: WorkerLeaveRepository,
        worker_repo: WorkerRepository,
        schedule_repo: ScheduleRepository,
    ) -> None:
        """Initialize the WorkerLeaveService with required repositories.

        Args:
            leave_repo: Repository for leave rows.
            worker_repo: Repository for workers, to validate the target.
            schedule_repo: Repository for schedules, to report duties already on the rota.
        """
        self.leave_repo = leave_repo
        self.worker_repo = worker_repo
        self.schedule_repo = schedule_repo
        self.logger = logger.bind(service="WorkerLeaveService")

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def get_leave_for_worker(self, worker_id: UUID) -> list[WorkerLeaveResponse]:
        """List every leave recorded for a worker, soonest first.

        Args:
            worker_id: The worker whose leave to list.

        Returns:
            list[WorkerLeaveResponse]: Their leave, past and future.
        """
        return self.leave_repo.get_by_worker(worker_id)

    def get_current_leave(self, today: date | None = None) -> list[CurrentLeave]:
        """List who is away right now, across every worker.

        Returned as a flat list rather than folded into the worker payload so the roster can be
        badged without the worker repository learning about leave.

        Args:
            today: Override for the current date; defaults to the current date.

        Returns:
            list[CurrentLeave]: One entry per worker currently away.
        """
        records = self.leave_repo.get_active_on(today or date.today())
        return [CurrentLeave(worker_id=r.worker_id, start_date=r.start_date, end_date=r.end_date) for r in records]

    def get_worker_ids_on_leave(self, day: date) -> set[UUID]:
        """Return the workers who are away on one date.

        Args:
            day: The date to test.

        Returns:
            set[UUID]: Workers covered by a leave on that date.
        """
        return {r.worker_id for r in self.leave_repo.get_active_on(day)}

    def get_clashes(self, worker_id: UUID, start_date: date, end_date: date) -> LeaveClashReport:
        """List duties already on the rota inside a proposed leave period.

        Advisory only. Setting leave records an absence; it does not reassign work, and silently
        dropping somebody off a rota they were counted on for would be a worse surprise than the
        clash itself. The head is told so they can reassign, and the worker keeps their reminder
        in the meantime — which is what prompts a decline if nobody gets to it.

        Args:
            worker_id: The worker going away.
            start_date: First day away, inclusive.
            end_date: Last day away, inclusive.

        Returns:
            LeaveClashReport: The duties that fall inside the window, soonest first.
        """
        assignments = self.schedule_repo.get_upcoming_assignments_for_worker(worker_id, start_date)
        clashes = []
        for assignment in assignments:
            schedule = assignment.schedules
            if schedule is None or schedule.scheduled_date is None:
                continue
            if schedule.scheduled_date > end_date:
                continue
            clashes.append(
                LeaveClash(
                    schedule_id=schedule.id,
                    scheduled_date=schedule.scheduled_date,
                    department_name=schedule.departments.name if schedule.departments else None,
                )
            )
        return LeaveClashReport(clashes=clashes)

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def create_leave(self, worker_id: UUID, data: WorkerLeaveCreate, created_by: UUID | None) -> WorkerLeaveResponse:
        """Record that a worker is away for a stretch.

        Args:
            worker_id: The worker going away.
            data: The range and an optional note.
            created_by: The head who set it, if their profile could be resolved.

        Returns:
            WorkerLeaveResponse: The stored leave.

        Raises:
            NotFoundError: If the worker does not exist.
            ConflictError: If it would overlap leave already recorded for them.
        """
        log = self.logger.bind(method="create_leave", worker_id=str(worker_id))
        if not self.worker_repo.get_by_id(worker_id):
            log.warning("leave_worker_not_found")
            raise NotFoundError(f"Worker {worker_id} not found")

        # Rejected here rather than by a database constraint: excluding overlapping ranges in
        # Postgres needs btree_gist, and overlap is untidy rather than harmful — every read
        # unions the rows, so two overlapping leaves still mean "on leave". The check is for the
        # head's benefit, so the message names what it collided with.
        overlapping = self.leave_repo.get_overlapping(worker_id, data.start_date, data.end_date)
        if overlapping:
            existing = overlapping[0]
            log.info("leave_overlaps_existing", existing_id=str(existing.id))
            raise ConflictError(
                f"This overlaps leave already recorded for {existing.start_date:%d %b %Y} "
                f"to {existing.end_date:%d %b %Y}. Remove that one first, or change these dates."
            )

        payload = data.model_dump(mode="json")
        payload["worker_id"] = str(worker_id)
        payload["created_by"] = str(created_by) if created_by else None
        leave = self.leave_repo.create(payload)
        log.info(
            "leave_created",
            leave_id=str(leave.id),
            start_date=leave.start_date.isoformat(),
            end_date=leave.end_date.isoformat(),
        )
        return leave

    def delete_leave(self, leave_id: UUID) -> None:
        """Remove a recorded leave, putting the worker back in the rota for those dates.

        Args:
            leave_id: The leave to remove.

        Raises:
            NotFoundError: If it does not exist.
        """
        log = self.logger.bind(method="delete_leave", leave_id=str(leave_id))
        if not self.leave_repo.get_by_id(leave_id):
            log.warning("leave_not_found")
            raise NotFoundError(f"Leave {leave_id} not found")
        self.leave_repo.delete(leave_id)
        log.info("leave_deleted")

    def get_owner_id(self, leave_id: UUID) -> UUID:
        """Return the worker a leave belongs to, for authorization.

        An endpoint addressing a leave by its own id cannot tell whose it is from the URL, so the
        owner has to be resolved before the caller can be checked against it.

        Args:
            leave_id: The leave being acted on.

        Returns:
            UUID: The owning worker.

        Raises:
            NotFoundError: If the leave does not exist.
        """
        existing = self.leave_repo.get_by_id(leave_id)
        if not existing:
            self.logger.warning("leave_not_found", leave_id=str(leave_id))
            raise NotFoundError(f"Leave {leave_id} not found")
        return existing.worker_id
