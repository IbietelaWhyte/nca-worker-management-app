from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from supabase import Client

from app.core.logging import get_logger
from app.repository.repository import BaseRepository
from app.repository.schedules import queries as q
from app.schemas.models import AssignmentStatus
from app.schemas.schedules.models import AssignmentResponse, ScheduleResponse

logger = get_logger(__name__)


class ScheduleRepository(BaseRepository[ScheduleResponse]):
    def __init__(self, client: Client) -> None:
        """
        Initialize the ScheduleRepository with a Supabase client.

        Args:
            client (Client): The Supabase client instance used for database operations.
        """
        super().__init__(client, q.TABLE, ScheduleResponse)
        self.logger = logger.bind(repository="ScheduleRepository")

    def get_by_department(self, department_id: UUID) -> list[ScheduleResponse]:
        """
        Retrieve all schedules for a specific department.

        This method fetches all schedule records associated with the given department,
        ordered by start date in descending order (most recent first).

        Args:
            department_id (UUID): The unique identifier of the department.

        Returns:
            list[ScheduleResponse]: A list of schedules for the department, ordered by
                                   start date (newest first). Returns an empty list if
                                   no schedules exist for the department.
        """
        log = self.logger.bind(method="get_by_department", department_id=str(department_id))
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .eq(q.Columns.DEPARTMENT_ID, str(department_id))
            .order(q.Columns.START_TIME, desc=True)
            .execute()
        )
        schedules = self._to_model_list(response.data or [])
        log.debug("fetched_schedules_by_department", count=len(schedules))
        return schedules

    def get_with_assignments(self, schedule_id: UUID) -> ScheduleResponse | None:
        """
        Retrieve a schedule with all its worker assignments embedded.

        This method fetches a schedule along with complete information about all
        worker assignments associated with it through a join operation.

        Args:
            schedule_id (UUID): The unique identifier of the schedule.

        Returns:
            ScheduleResponse | None: The schedule with embedded assignment data if found,
                                    None if the schedule doesn't exist.
        """
        log = self.logger.bind(method="get_with_assignments", schedule_id=str(schedule_id))
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_WITH_ASSIGNMENTS)
            .eq(q.Columns.ID, str(schedule_id))
            .maybe_single()
            .execute()
        )
        schedule = self._to_model(response.data) if response else None
        if schedule:
            log.debug("fetched_schedule_with_assignments")
        else:
            log.warning("schedule_not_found")
        return schedule

    def get_assignments_for_worker(self, worker_id: UUID) -> list[AssignmentResponse]:
        """
        Retrieve all schedule assignments for a specific worker.

        This method fetches all assignments for a worker with embedded schedule details,
        ordered by schedule date in descending order (most recent first).

        Args:
            worker_id (UUID): The unique identifier of the worker.

        Returns:
            list[AssignmentResponse]: A list of all assignments for the worker with embedded
                                     schedule information, ordered by date (newest first).
                                     Returns an empty list if the worker has no assignments.
        """
        log = self.logger.bind(method="get_assignments_for_worker", worker_id=str(worker_id))
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .select(q.SELECT_ASSIGNMENTS_WITH_SCHEDULE)
            .eq(q.AssignmentColumns.WORKER_ID, str(worker_id))
            .order(f"{q.TABLE}({q.Columns.SCHEDULED_DATE})", desc=True)
            .execute()
        )
        assignments = [AssignmentResponse.model_validate(row) for row in response.data or []]
        log.debug("fetched_assignments_for_worker", count=len(assignments))
        return assignments

    def get_assignments_in_range(self, start_date: date, end_date: date) -> list[AssignmentResponse]:
        """
        Retrieve all pending assignments within a specific date range.

        This method fetches assignments with embedded worker information for a given
        date range, filtered to only include assignments with PENDING status.

        Args:
            start_date (date): The start date of the range (inclusive).
            end_date (date): The end date of the range (inclusive).

        Returns:
            list[AssignmentResponse]: A list of pending assignments within the date range
                                     with embedded worker data. Returns an empty list if
                                     no pending assignments exist in the range.
        """
        log = self.logger.bind(
            method="get_assignments_in_range", start_date=start_date.isoformat(), end_date=end_date.isoformat()
        )
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .select(q.SELECT_ASSIGNMENTS_WITH_WORKERS)
            .gte(f"{q.TABLE}({q.Columns.SCHEDULED_DATE})", start_date.isoformat())
            .lte(f"{q.TABLE}({q.Columns.SCHEDULED_DATE})", end_date.isoformat())
            .eq(q.AssignmentColumns.STATUS, AssignmentStatus.PENDING)
            .order(f"{q.TABLE}({q.Columns.SCHEDULED_DATE})", desc=True)
            .execute()
        )
        assignments = [AssignmentResponse.model_validate(row) for row in response.data or []]
        log.debug("fetched_assignments_in_range", count=len(assignments))
        return assignments

    def create_assignment(self, data: dict[str, Any]) -> AssignmentResponse:
        """
        Create a new schedule assignment for a worker.

        Args:
            data (dict[str, Any]): A dictionary containing the assignment data including worker_id,
                        schedule_id, schedule_date, and status.

        Returns:
            AssignmentResponse: The newly created assignment record.
        """
        log = self.logger.bind(method="create_assignment")
        response = self.client.table(q.ASSIGNMENTS_TABLE).insert(data).execute()
        assignment = AssignmentResponse.model_validate(response.data[0])
        log.info("assignment_created", assignment_id=str(assignment.id))
        return assignment

    def bulk_create_assignments(self, assignments: list[dict[str, Any]]) -> list[AssignmentResponse]:
        """
        Create multiple schedule assignments in a single database operation.

        This method is more efficient than creating assignments one at a time,
        especially useful when generating schedules for multiple workers.

        Args:
            assignments (list[dict[str, Any]]): A list of dictionaries, each containing assignment data
                                     (worker_id, schedule_id, schedule_date, status).

        Returns:
            list[AssignmentResponse]: A list of all created assignment records.
        """
        log = self.logger.bind(method="bulk_create_assignments", count=len(assignments))
        response = self.client.table(q.ASSIGNMENTS_TABLE).insert(assignments).execute()
        created = [AssignmentResponse.model_validate(row) for row in response.data or []]
        log.info("bulk_assignments_created", created_count=len(created))
        return created

    def get_assignment_by_id(self, assignment_id: UUID) -> AssignmentResponse | None:
        """
        Retrieve a single schedule assignment by its unique identifier.

        Args:
            assignment_id (UUID): The unique identifier of the assignment.

        Returns:
            AssignmentResponse | None: The assignment if found, None otherwise.
        """
        log = self.logger.bind(method="get_assignment_by_id", assignment_id=str(assignment_id))
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .select("*")
            .eq(q.AssignmentColumns.ID, str(assignment_id))
            .maybe_single()
            .execute()
        )
        assignment = AssignmentResponse.model_validate(response.data) if response else None
        if not assignment:
            log.warning("assignment_not_found")
        return assignment

    def update_assignment_status(self, assignment_id: UUID, status: AssignmentStatus) -> AssignmentResponse | None:
        """
        Update the status of a schedule assignment.

        This method allows changing an assignment's status (e.g., from PENDING to
        CONFIRMED, CANCELLED, or COMPLETED).

        Args:
            assignment_id (UUID): The unique identifier of the assignment to update.
            status (AssignmentStatus): The new status to set (PENDING, CONFIRMED,
                                       CANCELLED, or COMPLETED).

        Returns:
            AssignmentResponse | None: The updated assignment if successful, None if the
                                      assignment was not found.
        """
        log = self.logger.bind(method="update_assignment_status", assignment_id=str(assignment_id), status=status)
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .update({q.AssignmentColumns.STATUS: status})
            .eq(q.AssignmentColumns.ID, str(assignment_id))
            .execute()
        )
        assignment = AssignmentResponse.model_validate(response.data[0]) if response.data else None
        if assignment:
            log.info("assignment_status_updated")
        else:
            log.warning("assignment_not_found")
        return assignment

    def delete_assignments_for_schedule(self, schedule_id: UUID) -> bool:
        """
        Delete all worker assignments associated with a specific schedule.

        This method removes all assignment records linked to a schedule, typically used
        when deleting a schedule or when regenerating assignments for a schedule.

        Args:
            schedule_id (UUID): The unique identifier of the schedule whose assignments
                               should be deleted.

        Returns:
            bool: True if one or more assignments were deleted, False if no assignments
                 existed for the schedule.
        """
        log = self.logger.bind(method="delete_assignments_for_schedule", schedule_id=str(schedule_id))
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .delete()
            .eq(q.AssignmentColumns.SCHEDULE_ID, str(schedule_id))
            .execute()
        )
        deleted = len(response.data) > 0
        if deleted:
            log.info("assignments_deleted", count=len(response.data))
        else:
            log.debug("no_assignments_to_delete")
        return deleted

    def get_assignments_due_for_reminder(self, reminder_date: date) -> list[AssignmentResponse]:
        """
        Retrieve all assignments that are due for reminders on a specific date.

        This method fetches assignments where the schedule date minus the reminder
        lead time matches the given reminder date, allowing the system to send
        timely notifications to workers about upcoming shifts.

        Args:
            reminder_date (date): The date for which to retrieve assignments due for reminders.
        Returns:
            list[AssignmentResponse]: A list of assignments that are due for reminders on the specified date
        """
        log = self.logger.bind(method="get_assignments_due_for_reminder", reminder_date=reminder_date.isoformat())
        # We will be calling the database function directly here since the logic is complex and involves a join
        response = self.client.rpc(
            q.FUNCTION_GET_ASSIGNMENTS_DUE_FOR_REMINDER, {"check_date": reminder_date.isoformat()}
        ).execute()
        data = response.data if isinstance(response.data, list) else []
        assignments = [AssignmentResponse.model_validate(row) for row in data]
        log.debug("fetched_assignments_due_for_reminder", count=len(assignments))
        return assignments

    def mark_reminder_sent(self, assignment_id: UUID) -> bool:
        """
        Mark an assignment as having had its reminder sent.

        This method updates the assignment record to indicate that a reminder has been
        sent for it, preventing duplicate reminders from being sent in the future.

        Args:
            assignment_id (UUID): The unique identifier of the assignment to update.
        Returns:
            bool: True if the assignment was successfully updated, False if the assignment was not found.
        """
        log = self.logger.bind(method="mark_reminder_sent", assignment_id=str(assignment_id))
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .update({q.AssignmentColumns.REMINDER_SENT_AT: datetime.now(timezone.utc).isoformat()})
            .eq(q.AssignmentColumns.ID, str(assignment_id))
            .execute()
        )
        success = len(response.data) > 0
        if success:
            log.info("reminder_marked_sent")
        else:
            log.warning("assignment_not_found")
        return success
