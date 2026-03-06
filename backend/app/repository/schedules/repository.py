from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from supabase import Client

from app.repository.repository import BaseRepository
from app.repository.schedules import queries as q
from app.schemas.models import AssignmentStatus
from app.schemas.schedules.models import AssignmentResponse, ScheduleResponse


class ScheduleRepository(BaseRepository[ScheduleResponse]):
    def __init__(self, client: Client) -> None:
        """
        Initialize the ScheduleRepository with a Supabase client.

        Args:
            client (Client): The Supabase client instance used for database operations.
        """
        super().__init__(client, q.TABLE, ScheduleResponse)

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
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .eq(q.Columns.DEPARTMENT_ID, str(department_id))
            .order(q.Columns.START_DATE, desc=True)
            .execute()
        )
        return self._to_model_list(response.data or [])

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
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_WITH_ASSIGNMENTS)
            .eq(q.Columns.ID, str(schedule_id))
            .single()
            .execute()
        )
        return self._to_model(response.data) if response.data else None

    def get_assignments_for_worker(
        self, worker_id: UUID
    ) -> list[AssignmentResponse]:
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
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .select(q.SELECT_ASSIGNMENTS_WITH_SCHEDULE)
            .eq(q.AssignmentColumns.WORKER_ID, str(worker_id))
            .order(q.AssignmentColumns.SCHEDULE_DATE, desc=True)
            .execute()
        )
        return [AssignmentResponse.model_validate(row) for row in response.data or []]

    def get_assignments_in_range(
        self, start_date: date, end_date: date
    ) -> list[AssignmentResponse]:
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
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .select(q.SELECT_ASSIGNMENTS_WITH_WORKERS)
            .gte(q.AssignmentColumns.SCHEDULE_DATE, start_date.isoformat())
            .lte(q.AssignmentColumns.SCHEDULE_DATE, end_date.isoformat())
            .eq(q.AssignmentColumns.STATUS, AssignmentStatus.PENDING)
            .execute()
        )
        return [AssignmentResponse.model_validate(row) for row in response.data or []]

    def create_assignment(self, data: dict[str, Any]) -> AssignmentResponse:
        """
        Create a new schedule assignment for a worker.

        Args:
            data (dict[str, Any]): A dictionary containing the assignment data including worker_id,
                        schedule_id, schedule_date, and status.

        Returns:
            AssignmentResponse: The newly created assignment record.
        """
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .insert(data)
            .execute()
        )
        return AssignmentResponse.model_validate(response.data[0])

    def bulk_create_assignments(
        self, assignments: list[dict[str, Any]]
    ) -> list[AssignmentResponse]:
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
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .insert(assignments)
            .execute()
        )
        return [AssignmentResponse.model_validate(row) for row in response.data or []]

    def update_assignment_status(
        self, assignment_id: UUID, status: AssignmentStatus
    ) -> AssignmentResponse | None:
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
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .update({q.AssignmentColumns.STATUS: status})
            .eq(q.AssignmentColumns.ID, str(assignment_id))
            .execute()
        )
        return AssignmentResponse.model_validate(response.data[0]) if response.data else None

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
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .delete()
            .eq(q.AssignmentColumns.SCHEDULE_ID, str(schedule_id))
            .execute()
        )
        return len(response.data) > 0
    
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
        # We will be calling the database function directly here since the logic is complex and involves a join
        response = (
            self.client.rpc(q.FUNCTION_GET_ASSIGNMENTS_DUE_FOR_REMINDERS, {"check_date": reminder_date.isoformat()})
            .execute()
        )
        data = response.data if isinstance(response.data, list) else []
        return [AssignmentResponse.model_validate(row) for row in data]
    
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
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .update({q.AssignmentColumns.REMINDER_SENT_AT: datetime.now(timezone.utc).isoformat()})
            .eq(q.AssignmentColumns.ID, str(assignment_id))
            .execute()
        )
        return len(response.data) > 0