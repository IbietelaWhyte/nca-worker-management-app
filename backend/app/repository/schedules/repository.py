from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from supabase import Client

from app.core.logging import get_logger
from app.repository.repository import BaseRepository
from app.repository.schedules import queries as q
from app.schemas.schedules.models import AssignmentResponse, DueReminder, ScheduleResponse

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

    def get_by_department(
        self,
        department_id: UUID,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[ScheduleResponse]:
        """
        Retrieve schedules for a specific department, newest scheduled_date first.

        Assignments are embedded so callers can show who is on each schedule without a
        second round-trip — the month grid needs names and confirmed counts per day.

        Args:
            department_id (UUID): The unique identifier of the department.
            from_date (date | None): Optional inclusive lower bound on scheduled_date.
            to_date (date | None): Optional inclusive upper bound on scheduled_date.

        Returns:
            list[ScheduleResponse]: Schedules for the department with their assignments,
                                   ordered by scheduled_date (newest first). Empty if none match.
        """
        log = self.logger.bind(
            method="get_by_department",
            department_id=str(department_id),
            from_date=from_date.isoformat() if from_date else None,
            to_date=to_date.isoformat() if to_date else None,
        )
        query = (
            self.client.table(q.TABLE).select(q.SELECT_WITH_ASSIGNMENTS).eq(q.Columns.DEPARTMENT_ID, str(department_id))
        )
        if from_date is not None:
            query = query.gte(q.Columns.SCHEDULED_DATE, from_date.isoformat())
        if to_date is not None:
            query = query.lte(q.Columns.SCHEDULED_DATE, to_date.isoformat())

        response = query.order(q.Columns.SCHEDULED_DATE, desc=True).execute()
        schedules = self._to_model_list(response.data or [])
        log.debug("fetched_schedules_by_department", count=len(schedules))
        return schedules

    def get_existing_schedule(
        self, department_id: UUID, scheduled_date: date, subteam_id: UUID | None = None
    ) -> ScheduleResponse | None:
        """
        Check if a schedule already exists for a department/subteam on a specific date.

        This prevents duplicate schedules from being created for the same date.

        Args:
            department_id (UUID): The unique identifier of the department.
            scheduled_date (date): The date to check for existing schedules.
            subteam_id (UUID | None): Optional subteam ID. If provided, checks for that subteam;
                                     if None, checks for department-level schedules (subteam_id IS NULL).

        Returns:
            ScheduleResponse | None: The existing schedule if found, None otherwise.
        """
        log = self.logger.bind(
            method="get_existing_schedule",
            department_id=str(department_id),
            scheduled_date=scheduled_date.isoformat(),
            subteam_id=str(subteam_id) if subteam_id else None,
        )
        query = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .eq(q.Columns.DEPARTMENT_ID, str(department_id))
            .eq(q.Columns.SCHEDULED_DATE, scheduled_date.isoformat())
        )

        # Filter by subteam: specific subteam or department-level (null)
        if subteam_id is not None:
            query = query.eq(q.Columns.SUBTEAM_ID, str(subteam_id))
        else:
            query = query.is_(q.Columns.SUBTEAM_ID, "null")

        response = query.execute()
        schedules = self._to_model_list(response.data or [])

        if schedules:
            log.info("existing_schedule_found", schedule_id=str(schedules[0].id))
            return schedules[0]

        log.debug("no_existing_schedule_found")
        return None

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

    def get_upcoming_assignments_for_worker(self, worker_id: UUID, from_date: date) -> list[AssignmentResponse]:
        """
        Retrieve a worker's assignments scheduled on or after a given date.

        Used to check whether a worker still has commitments before their profile is deleted, and to
        list those commitments on the public confirmation page — which is why the department comes
        back embedded: that page has no session to resolve a department id with.
        Filtering happens on the joined schedules table, so the select must use the inner-join
        variant for the filter to drop rows rather than null the embedded schedule.

        Args:
            worker_id (UUID): The unique identifier of the worker.
            from_date (date): Inclusive lower bound; assignments on this date or later are returned.

        Returns:
            list[AssignmentResponse]: The worker's assignments on or after from_date, ordered by
                                     date (soonest first). Empty if the worker has none.
        """
        log = self.logger.bind(
            method="get_upcoming_assignments_for_worker",
            worker_id=str(worker_id),
            from_date=from_date.isoformat(),
        )
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .select(q.SELECT_ASSIGNMENTS_WITH_SCHEDULE_AND_DEPARTMENT_INNER)
            .eq(q.AssignmentColumns.WORKER_ID, str(worker_id))
            .gte(f"{q.TABLE}.{q.Columns.SCHEDULED_DATE}", from_date.isoformat())
            .order(f"{q.TABLE}({q.Columns.SCHEDULED_DATE})")
            .execute()
        )
        assignments = [AssignmentResponse.model_validate(row) for row in response.data or []]
        log.debug("fetched_upcoming_assignments_for_worker", count=len(assignments))
        return assignments

    def get_workers_scheduled_on_date(self, scheduled_date: date) -> list[UUID]:
        """
        Retrieve worker IDs who have schedule assignments on a specific date.

        This method checks for any existing assignments (regardless of status) on the
        given date to prevent double-scheduling workers. It queries the schedule_assignments
        table and filters using the related schedules table's scheduled_date field.

        Args:
            scheduled_date (date): The date to check for existing assignments.

        Returns:
            list[UUID]: A list of worker IDs who have assignments on the given date.
                       Returns an empty list if no workers are scheduled on that date.
        """
        log = self.logger.bind(method="get_workers_scheduled_on_date", scheduled_date=scheduled_date.isoformat())
        # Query schedule_assignments with schedules join, filter by schedules.scheduled_date
        # Must include schedules!inner(*) in SELECT to create the inner join and enable filtering on schedules table
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .select(f"{q.AssignmentColumns.WORKER_ID}, {q.TABLE}!inner(*)")
            .eq(f"{q.TABLE}.{q.Columns.SCHEDULED_DATE}", scheduled_date.isoformat())
            .execute()
        )
        worker_ids = [
            UUID(str(row[q.AssignmentColumns.WORKER_ID]))
            for row in (response.data or [])
            if isinstance(row, dict) and q.AssignmentColumns.WORKER_ID in row
        ]
        log.debug("found_workers_scheduled_on_date", count=len(worker_ids), worker_ids=[str(wid) for wid in worker_ids])
        return worker_ids

    def get_workers_scheduled_in_range(self, start_date: date, end_date: date) -> dict[date, set[UUID]]:
        """
        Retrieve, per date, the workers already assigned anywhere in the org.

        The range equivalent of `get_workers_scheduled_on_date` — one round-trip for a
        whole month instead of one per date, which is what makes monthly generation
        viable against the capped connection pool.

        Args:
            start_date (date): The start of the range (inclusive).
            end_date (date): The end of the range (inclusive).

        Returns:
            dict[date, set[UUID]]: Scheduled date -> worker IDs booked that day. Dates
                                  with no assignments are absent from the mapping.
        """
        log = self.logger.bind(
            method="get_workers_scheduled_in_range",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )
        # Dot syntax + !inner is required to filter on the embedded schedules table;
        # the parenthesis form silently fails to filter.
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .select(f"{q.AssignmentColumns.WORKER_ID}, {q.TABLE}!inner({q.Columns.SCHEDULED_DATE})")
            .gte(f"{q.TABLE}.{q.Columns.SCHEDULED_DATE}", start_date.isoformat())
            .lte(f"{q.TABLE}.{q.Columns.SCHEDULED_DATE}", end_date.isoformat())
            .execute()
        )

        booked: dict[date, set[UUID]] = {}
        for row in response.data or []:
            if not isinstance(row, dict):
                continue
            schedule = row.get(q.TABLE)
            worker_id = row.get(q.AssignmentColumns.WORKER_ID)
            if not isinstance(schedule, dict) or worker_id is None:
                continue
            raw_date = schedule.get(q.Columns.SCHEDULED_DATE)
            if raw_date is None:
                continue
            scheduled_date = date.fromisoformat(str(raw_date))
            booked.setdefault(scheduled_date, set()).add(UUID(str(worker_id)))

        log.debug("found_workers_scheduled_in_range", dates=len(booked))
        return booked

    def get_assignment_history_for_workers(
        self, worker_ids: list[UUID], department_id: UUID
    ) -> list[AssignmentResponse]:
        """
        Retrieve the full in-department assignment history for several workers at once.

        Replaces N calls to `get_assignments_for_worker` when planning a month. The
        caller filters by subteam in memory — scoping that here would need a second
        query shape for the department-level (subteam_id IS NULL) case.

        Args:
            worker_ids (list[UUID]): The workers whose history is needed.
            department_id (UUID): Restricts history to this department.

        Returns:
            list[AssignmentResponse]: Assignments with their schedule embedded. Empty if
                                     `worker_ids` is empty or nothing matches.
        """
        log = self.logger.bind(
            method="get_assignment_history_for_workers",
            worker_count=len(worker_ids),
            department_id=str(department_id),
        )
        if not worker_ids:
            return []

        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .select(q.SELECT_ASSIGNMENTS_WITH_SCHEDULE_INNER)
            .in_(q.AssignmentColumns.WORKER_ID, [str(wid) for wid in worker_ids])
            .eq(f"{q.TABLE}.{q.Columns.DEPARTMENT_ID}", str(department_id))
            .execute()
        )
        assignments = [AssignmentResponse.model_validate(row) for row in response.data or []]
        log.debug("fetched_assignment_history", count=len(assignments))
        return assignments

    def bulk_create_schedules(self, schedules: list[dict[str, Any]]) -> list[ScheduleResponse]:
        """
        Create multiple schedules in a single database operation.

        One statement rather than one per date, so a monthly commit is atomic across all
        its schedule rows.

        Args:
            schedules (list[dict[str, Any]]): Schedule rows to insert.

        Returns:
            list[ScheduleResponse]: The created schedules.
        """
        log = self.logger.bind(method="bulk_create_schedules", count=len(schedules))
        if not schedules:
            return []
        response = self.client.table(q.TABLE).insert(schedules).execute()
        created = self._to_model_list(response.data or [])
        log.info("bulk_schedules_created", created_count=len(created))
        return created

    def delete_schedules(self, schedule_ids: list[UUID]) -> None:
        """
        Delete several schedules by id.

        Used as a compensating action when a monthly commit writes its schedules but
        then fails to write their assignments — there is no transaction to roll back.

        Args:
            schedule_ids (list[UUID]): The schedules to delete.
        """
        log = self.logger.bind(method="delete_schedules", count=len(schedule_ids))
        if not schedule_ids:
            return
        self.client.table(q.TABLE).delete().in_(q.Columns.ID, [str(sid) for sid in schedule_ids]).execute()
        log.info("schedules_deleted", count=len(schedule_ids))

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
        # PostgREST rejects an empty insert body, and a date whose every worker was filtered out
        # is an ordinary outcome of planning, not an error worth failing a whole month over.
        if not assignments:
            return []
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
            AssignmentResponse | None: The assignment if found, None otherwise, with the worker,
                                       subteam and role embedded.
        """
        log = self.logger.bind(method="get_assignment_by_id", assignment_id=str(assignment_id))
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .select(q.SELECT_ASSIGNMENT_WITH_RELATIONS)
            .eq(q.AssignmentColumns.ID, str(assignment_id))
            .maybe_single()
            .execute()
        )
        assignment = AssignmentResponse.model_validate(response.data) if response else None
        if not assignment:
            log.warning("assignment_not_found")
        return assignment

    def update_assignment_role(self, assignment_id: UUID, department_role_id: UUID | None) -> AssignmentResponse | None:
        """
        Update the department role of a schedule assignment.

        Args:
            assignment_id (UUID): The unique identifier of the assignment to update.
            department_role_id (UUID | None): The role to set, or None to clear it.

        Returns:
            AssignmentResponse | None: The updated assignment if successful, None if the
                                      assignment was not found.
        """
        log = self.logger.bind(
            method="update_assignment_role",
            assignment_id=str(assignment_id),
            department_role_id=str(department_role_id) if department_role_id else None,
        )
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .update({q.AssignmentColumns.DEPARTMENT_ROLE_ID: str(department_role_id) if department_role_id else None})
            .eq(q.AssignmentColumns.ID, str(assignment_id))
            .execute()
        )
        if not response.data:
            log.warning("assignment_not_found")
            return None
        # Same re-read as update_assignment_status, for the same reason.
        assignment = self.get_assignment_by_id(assignment_id)
        log.info("assignment_role_updated")
        return assignment

    def get_assignment_with_schedule(self, assignment_id: UUID) -> AssignmentResponse | None:
        """
        Retrieve one assignment together with its schedule and its worker.

        The edit paths need all three before they touch anything: the schedule carries the
        department the caller is authorized against and the date the SMS quotes, and the worker
        is who gets texted. Reading them separately would mean three round trips, and on the
        remove path the second and third would come back empty.

        Args:
            assignment_id (UUID): The unique identifier of the assignment.

        Returns:
            AssignmentResponse | None: The assignment with `schedules` and `workers` embedded,
                                       or None if no assignment has that id.
        """
        log = self.logger.bind(method="get_assignment_with_schedule", assignment_id=str(assignment_id))
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .select(q.SELECT_ASSIGNMENT_WITH_SCHEDULE_AND_WORKER)
            .eq(q.AssignmentColumns.ID, str(assignment_id))
            .maybe_single()
            .execute()
        )
        assignment = AssignmentResponse.model_validate(response.data) if response else None
        if not assignment:
            log.warning("assignment_not_found")
        return assignment

    def reassign_assignment(
        self,
        assignment_id: UUID,
        worker_id: UUID,
        subteam_id: UUID | None,
        department_role_id: UUID | None,
    ) -> AssignmentResponse | None:
        """
        Put a different worker into an existing assignment.

        **Clears `notice_sent_at`, the attendance record, and the row's reminder-send markers**,
        in this one method, because the row now names somebody who has been told nothing and was
        never there. A stale `notice_sent_at` keeps the notice sweep from ever reaching them and a
        stale send marker cancels the reminder that would have; neither errors, and the first
        anybody hears about it is the empty chair.

        The attendance columns are the sharper of the two. Carried over, they would assert that
        the **new** worker was present at - or absent from - a service they were never on, and
        that assertion is what the absence report shows their head. Done here rather than in a
        trigger: the backend is the only writer (service-role client, RLS bypassed) and this
        schema has no triggers.

        Args:
            assignment_id (UUID): The assignment to hand over.
            worker_id (UUID): The worker taking it on.
            subteam_id (UUID | None): The subteam they fill, or None.
            department_role_id (UUID | None): Their standing role in the department, or None.

        Returns:
            AssignmentResponse | None: The updated assignment with its embeds re-read, or None
                                       if no assignment has that id.
        """
        log = self.logger.bind(method="reassign_assignment", assignment_id=str(assignment_id), worker_id=str(worker_id))
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .update(
                {
                    q.AssignmentColumns.WORKER_ID: str(worker_id),
                    q.AssignmentColumns.SUBTEAM_ID: str(subteam_id) if subteam_id else None,
                    q.AssignmentColumns.DEPARTMENT_ROLE_ID: str(department_role_id) if department_role_id else None,
                    q.AssignmentColumns.NOTICE_SENT_AT: None,
                    # The whole attendance record, not just the check-in: an absence stamped
                    # against the previous holder must not follow the seat to its new one.
                    q.AssignmentColumns.CHECKED_IN_AT: None,
                    q.AssignmentColumns.CHECKED_IN_BY: None,
                    q.AssignmentColumns.MARKED_ABSENT_AT: None,
                    q.AssignmentColumns.MINUTES_LATE: None,
                    q.AssignmentColumns.IS_LATE: False,
                    q.AssignmentColumns.EXCUSED: False,
                }
            )
            .eq(q.AssignmentColumns.ID, str(assignment_id))
            .execute()
        )
        if not response.data:
            log.warning("assignment_not_found")
            return None

        self.delete_reminder_sends(assignment_id)

        # A write does not return its embeds, and the caller renders the new worker's name.
        assignment = self.get_assignment_by_id(assignment_id)
        log.info("assignment_reassigned")
        return assignment

    # ------------------------------------------------------------------
    # Attendance
    #
    # Three states from two timestamps: neither set is "not recorded", checked_in_at is present,
    # marked_absent_at is absent. Only close_roll_call writes the second, which is what makes
    # "a roll call nobody closed records nothing" true by construction. Every write re-reads,
    # because a PostgREST UPDATE returns base columns only and the caller renders the embeds.
    # ------------------------------------------------------------------

    def set_check_in(
        self,
        assignment_id: UUID,
        checked_in_at: datetime,
        minutes_late: int | None,
        is_late: bool,
        checked_in_by: UUID | None,
    ) -> AssignmentResponse | None:
        """Mark one worker present, clearing any absence already stamped against them.

        Clearing `marked_absent_at` in the same statement is what lets somebody who turns up
        after the roll call was closed simply be tapped in - the commonest correction there is -
        without the head having to reopen the whole register first. The two columns are mutually
        exclusive by check constraint, so they have to move together anyway.

        Args:
            assignment_id (UUID): The duty being marked.
            checked_in_at (datetime): When they were seen. Timezone-aware.
            minutes_late (int | None): Minutes after the start, or None if judged on another day.
            is_late (bool): Whether that beat the grace period in force at the tap.
            checked_in_by (UUID | None): The operator's worker id, if they have one.

        Returns:
            AssignmentResponse | None: The updated assignment with its embeds re-read, or None
                                       if no assignment has that id.
        """
        log = self.logger.bind(method="set_check_in", assignment_id=str(assignment_id), is_late=is_late)
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .update(
                {
                    q.AssignmentColumns.CHECKED_IN_AT: checked_in_at.isoformat(),
                    q.AssignmentColumns.CHECKED_IN_BY: str(checked_in_by) if checked_in_by else None,
                    q.AssignmentColumns.MINUTES_LATE: minutes_late,
                    q.AssignmentColumns.IS_LATE: is_late,
                    q.AssignmentColumns.MARKED_ABSENT_AT: None,
                    q.AssignmentColumns.EXCUSED: False,
                }
            )
            .eq(q.AssignmentColumns.ID, str(assignment_id))
            .execute()
        )
        if not response.data:
            log.warning("assignment_not_found")
            return None
        log.info("attendance_checked_in", minutes_late=minutes_late)
        return self.get_assignment_by_id(assignment_id)

    def clear_check_in(self, assignment_id: UUID, absent_at: datetime | None) -> AssignmentResponse | None:
        """Undo a check-in, back to absent if the roll call is closed and to nothing if it is not.

        `absent_at` carries that decision rather than the method re-reading the schedule to make
        it: a closed register must not develop a hole where a row says neither present nor absent,
        and an open one must not gain an absence nobody closed.

        Args:
            assignment_id (UUID): The duty being un-marked.
            absent_at (datetime | None): Stamp absence at this moment, or None to leave no record.

        Returns:
            AssignmentResponse | None: The updated assignment, or None if no assignment has that id.
        """
        log = self.logger.bind(method="clear_check_in", assignment_id=str(assignment_id))
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .update(
                {
                    q.AssignmentColumns.CHECKED_IN_AT: None,
                    q.AssignmentColumns.CHECKED_IN_BY: None,
                    q.AssignmentColumns.MINUTES_LATE: None,
                    q.AssignmentColumns.IS_LATE: False,
                    q.AssignmentColumns.MARKED_ABSENT_AT: absent_at.isoformat() if absent_at else None,
                }
            )
            .eq(q.AssignmentColumns.ID, str(assignment_id))
            .execute()
        )
        if not response.data:
            log.warning("assignment_not_found")
            return None
        log.info("attendance_check_in_cleared", left_absent=absent_at is not None)
        return self.get_assignment_by_id(assignment_id)

    def mark_absent(self, assignment_ids: list[UUID], absent_at: datetime, excused: bool) -> int:
        """Stamp a batch of duties absent in one statement.

        One statement per batch rather than a loop, for the same reason `mark_notice_sent` marks a
        whole batch at once: a crash mid-loop would leave a register half closed, with some rows
        absent and some recording nothing, and no way to tell which half.

        Args:
            assignment_ids (list[UUID]): The duties nobody turned up for.
            absent_at (datetime): When the roll call was closed.
            excused (bool): Whether these absences are excused (a batch of workers on leave).

        Returns:
            int: How many rows were stamped. Zero for an empty list, without a round-trip.
        """
        log = self.logger.bind(method="mark_absent", count=len(assignment_ids), excused=excused)
        if not assignment_ids:
            return 0
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .update(
                {
                    q.AssignmentColumns.MARKED_ABSENT_AT: absent_at.isoformat(),
                    q.AssignmentColumns.EXCUSED: excused,
                }
            )
            .in_(q.AssignmentColumns.ID, [str(i) for i in assignment_ids])
            .execute()
        )
        marked = len(response.data or [])
        log.info("attendance_marked_absent", marked=marked)
        return marked

    def clear_absences(self, assignment_ids: list[UUID]) -> int:
        """Erase the absences on a batch of duties, leaving check-ins alone.

        Reopening a register undoes what closing it invented; it does not undo what somebody
        observed. Takes ids rather than a schedule id because PostgREST cannot filter a DELETE or
        UPDATE through a join, and the caller is already holding the schedule's assignments.

        Args:
            assignment_ids (list[UUID]): The duties to clear.

        Returns:
            int: How many rows were cleared.
        """
        log = self.logger.bind(method="clear_absences", count=len(assignment_ids))
        if not assignment_ids:
            return 0
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .update(
                {
                    q.AssignmentColumns.MARKED_ABSENT_AT: None,
                    q.AssignmentColumns.EXCUSED: False,
                }
            )
            .in_(q.AssignmentColumns.ID, [str(i) for i in assignment_ids])
            .execute()
        )
        cleared = len(response.data or [])
        log.info("attendance_absences_cleared", cleared=cleared)
        return cleared

    def set_excused(self, assignment_id: UUID, excused: bool) -> AssignmentResponse | None:
        """Mark an absence as not counting, or put it back.

        Args:
            assignment_id (UUID): The absence to excuse.
            excused (bool): Whether it should count against the worker.

        Returns:
            AssignmentResponse | None: The updated assignment, or None if no assignment has that id.
        """
        log = self.logger.bind(method="set_excused", assignment_id=str(assignment_id), excused=excused)
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .update({q.AssignmentColumns.EXCUSED: excused})
            .eq(q.AssignmentColumns.ID, str(assignment_id))
            .execute()
        )
        if not response.data:
            log.warning("assignment_not_found")
            return None
        log.info("attendance_excused_set")
        return self.get_assignment_by_id(assignment_id)

    def set_roll_call_closed(
        self, schedule_id: UUID, closed_at: datetime | None, closed_by: UUID | None
    ) -> ScheduleResponse | None:
        """Close the register, or reopen it by passing None.

        Args:
            schedule_id (UUID): The rota whose roll call it is.
            closed_at (datetime | None): When it was closed, or None to reopen.
            closed_by (UUID | None): The operator's worker id, if they have one.

        Returns:
            ScheduleResponse | None: The re-read schedule with its assignments, or None if no
                                     schedule has that id.
        """
        log = self.logger.bind(method="set_roll_call_closed", schedule_id=str(schedule_id))
        response = (
            self.client.table(q.TABLE)
            .update(
                {
                    q.Columns.ROLL_CALL_CLOSED_AT: closed_at.isoformat() if closed_at else None,
                    q.Columns.ROLL_CALL_CLOSED_BY: str(closed_by) if (closed_at and closed_by) else None,
                }
            )
            .eq(q.Columns.ID, str(schedule_id))
            .execute()
        )
        if not response.data:
            log.warning("schedule_not_found")
            return None
        log.info("roll_call_closed" if closed_at else "roll_call_reopened")
        return self.get_with_assignments(schedule_id)

    def get_for_attendance_report(self, department_id: UUID, from_date: date, to_date: date) -> list[ScheduleResponse]:
        """Every rota a department ran in a window, with who was on it and what was recorded.

        Rooted at schedules rather than assignments because the report counts **services** as well
        as people: a month whose roll call was taken twice out of twelve has to be able to say so,
        and an assignment-rooted read cannot see the rotas that carry no attendance at all.

        Args:
            department_id (UUID): The department to report on.
            from_date (date): First day of the window, inclusive.
            to_date (date): Last day, inclusive.

        Returns:
            list[ScheduleResponse]: The rotas, ascending by date.
        """
        log = self.logger.bind(method="get_for_attendance_report", department_id=str(department_id))
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_FOR_ATTENDANCE_REPORT)
            .eq(q.Columns.DEPARTMENT_ID, str(department_id))
            .gte(q.Columns.SCHEDULED_DATE, from_date.isoformat())
            .lte(q.Columns.SCHEDULED_DATE, to_date.isoformat())
            .order(q.Columns.SCHEDULED_DATE)
            .execute()
        )
        schedules = self._to_model_list(response.data or [])
        log.debug("fetched_attendance_report_rows", count=len(schedules))
        return schedules

    def delete_reminder_sends(self, assignment_id: UUID) -> int:
        """
        Forget which of an assignment's reminders have already gone out.

        Only called when the assignment changes hands. The markers record that *a person* was
        told, not that a row was processed, so they cannot follow the row to somebody else.

        Args:
            assignment_id (UUID): The assignment whose markers to clear.

        Returns:
            int: How many markers were deleted.
        """
        response = (
            self.client.table(q.REMINDER_SENDS_TABLE)
            .delete()
            .eq(q.ReminderSendColumns.ASSIGNMENT_ID, str(assignment_id))
            .execute()
        )
        deleted = len(response.data or [])
        if deleted:
            self.logger.bind(method="delete_reminder_sends", assignment_id=str(assignment_id)).info(
                "reminder_sends_deleted", deleted=deleted
            )
        return deleted

    def delete_assignment(self, assignment_id: UUID) -> bool:
        """
        Take one worker off a schedule.

        The row's reminder markers go with it on the foreign key's ON DELETE CASCADE — unlike
        reassignment, where the row survives and has to be cleared by hand.

        Args:
            assignment_id (UUID): The assignment to delete.

        Returns:
            bool: True if a row was deleted, False if no assignment had that id.
        """
        log = self.logger.bind(method="delete_assignment", assignment_id=str(assignment_id))
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE).delete().eq(q.AssignmentColumns.ID, str(assignment_id)).execute()
        )
        deleted = len(response.data or []) > 0
        if deleted:
            log.info("assignment_deleted")
        else:
            log.warning("assignment_not_found")
        return deleted

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

    def get_assignments_due_for_reminder(self, reminder_date: date) -> list[DueReminder]:
        """
        Retrieve every reminder falling due on a specific date.

        A schedule carries a ladder of lead times, so a row here is one (assignment, lead time)
        pair rather than an assignment: the same duty appears once for each entry in the ladder
        whose date lands on `reminder_date`, and each is recorded separately once sent. Pairs
        already recorded in `assignment_reminder_sends` are excluded by the function itself.

        Args:
            reminder_date (date): The date for which to retrieve reminders now due.
        Returns:
            list[DueReminder]: Due (assignment, lead time) pairs, ordered by worker so the caller
                can group a person's duties into a single message.
        """
        log = self.logger.bind(method="get_assignments_due_for_reminder", reminder_date=reminder_date.isoformat())
        # We will be calling the database function directly here since the logic is complex and involves a join
        response = self.client.rpc(
            q.FUNCTION_GET_ASSIGNMENTS_DUE_FOR_REMINDER, {"check_date": reminder_date.isoformat()}
        ).execute()
        data = response.data if isinstance(response.data, list) else []
        reminders = [DueReminder.model_validate(row) for row in data]
        log.debug("fetched_assignments_due_for_reminder", count=len(reminders))
        return reminders

    def get_assignments_due_for_notice(self) -> list[AssignmentResponse]:
        """
        Retrieve assignments that have been created but not yet announced to the worker.

        Backs the "you have been scheduled" message. Rows come back ordered by worker so the
        caller can group a whole month of dates into one SMS per person.

        Returns:
            list[AssignmentResponse]: Un-notified future assignments for contactable workers.
        """
        log = self.logger.bind(method="get_assignments_due_for_notice")
        response = self.client.rpc(q.FUNCTION_GET_ASSIGNMENTS_DUE_FOR_NOTICE, {}).execute()
        data = response.data if isinstance(response.data, list) else []
        assignments = [AssignmentResponse.model_validate(row) for row in data]
        log.debug("fetched_assignments_due_for_notice", count=len(assignments))
        return assignments

    def mark_notice_sent(self, assignment_ids: list[UUID]) -> int:
        """
        Mark assignments as having had their initial notice sent.

        Takes a list because one SMS covers every date in a worker's batch — they are marked
        together, in one statement, so a partial failure cannot leave some dates looking
        un-notified and re-announce them on the next run.

        Args:
            assignment_ids (list[UUID]): The assignments covered by a single notice.
        Returns:
            int: How many rows were updated.
        """
        if not assignment_ids:
            return 0
        log = self.logger.bind(method="mark_notice_sent", count=len(assignment_ids))
        response = (
            self.client.table(q.ASSIGNMENTS_TABLE)
            .update({q.AssignmentColumns.NOTICE_SENT_AT: datetime.now(timezone.utc).isoformat()})
            .in_(q.AssignmentColumns.ID, [str(assignment_id) for assignment_id in assignment_ids])
            .execute()
        )
        updated = len(response.data or [])
        log.info("notice_marked_sent", updated=updated)
        return updated

    def mark_reminders_sent(self, sends: list[tuple[UUID, int]]) -> int:
        """
        Record the (assignment, lead time) pairs one reminder message covered.

        Takes a list because a worker's duties are reminded about in a single text, exactly as
        mark_notice_sent does — and a pair rather than an id because a schedule reminds several
        times: marking the whole assignment would cancel the lead times still to come.

        An upsert rather than an insert, so a second scheduler run racing the first lands on the
        composite primary key and does nothing instead of raising. `sent_at` is left out of the
        payload deliberately: PostgREST only updates the columns it is sent, so a re-run keeps
        the original send time rather than rewriting it.

        Args:
            sends (list[tuple[UUID, int]]): (assignment id, lead time in days) pairs to record.
        Returns:
            int: How many rows were written.
        """
        if not sends:
            return 0
        log = self.logger.bind(method="mark_reminders_sent", count=len(sends))
        response = (
            self.client.table(q.REMINDER_SENDS_TABLE)
            .upsert(
                [
                    {
                        q.ReminderSendColumns.ASSIGNMENT_ID: str(assignment_id),
                        q.ReminderSendColumns.DAYS_BEFORE: days_before,
                    }
                    for assignment_id, days_before in sends
                ],
                on_conflict=q.REMINDER_SEND_CONFLICT_TARGET,
            )
            .execute()
        )
        written = len(response.data or [])
        log.info("reminders_marked_sent", written=written)
        return written
