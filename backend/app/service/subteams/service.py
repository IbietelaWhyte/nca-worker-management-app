from uuid import UUID

from app.core.logging import get_logger
from app.repository.departments.repository import DepartmentRepository
from app.repository.subteams.repository import SubteamRepository
from app.schemas.subteams.models import SubteamCreate, SubteamResponse, SubteamUpdate, SubteamWithWorkersResponse

logger = get_logger(__name__)


class SubteamService:
    def __init__(self, subteam_repo: SubteamRepository, department_repo: DepartmentRepository) -> None:
        """Initialize the SubteamService with required repositories.

        Args:
            subteam_repo: Repository for subteam database operations.
            department_repo: Repository for department database operations.
        """
        self.subteam_repo = subteam_repo
        self.department_repo = department_repo
        self.logger = logger.bind(service="SubteamService")

    def get_subteam(self, subteam_id: UUID) -> SubteamResponse:
        """Retrieve a subteam by ID.

        Args:
            subteam_id: Unique identifier of the subteam.

        Returns:
            SubteamResponse: The subteam data.

        Raises:
            ValueError: If subteam not found.
        """
        log = self.logger.bind(method="get_subteam", subteam_id=str(subteam_id))
        subteam = self.subteam_repo.get_by_id(subteam_id)
        if not subteam:
            log.warning("subteam_not_found")
            raise ValueError(f"subteam {subteam_id} not found")
        return subteam

    def get_all_subteams(self) -> list[SubteamResponse]:
        """Retrieve all subteams.

        Returns:
            list[SubteamResponse]: List of all subteams in the system.
        """
        log = self.logger.bind(method="get_all_subteams")
        subteams = self.subteam_repo.get_all()
        log.debug("fetched_all_subteams", count=len(subteams))
        return subteams

    def get_subteam_with_workers(self, subteam_id: UUID) -> list[SubteamWithWorkersResponse]:
        """Retrieve a subteam with all assigned workers embedded.

        Args:
            subteam_id: Unique identifier of the subteam.

        Returns:
            list[SubteamWithWorkersResponse]: Subteam with worker details (can be empty list).

        Raises:
            ValueError: If subteam not found.
        """
        log = self.logger.bind(method="get_subteam_with_workers", subteam_id=str(subteam_id))

        # First validate that the subteam exists
        subteam_exists = self.subteam_repo.get_by_id(subteam_id)
        if not subteam_exists:
            log.warning("subteam_not_found")
            raise ValueError(f"subteam {subteam_id} not found")

        # Then get workers (can be empty list if no workers assigned)
        workers = self.subteam_repo.get_with_workers(subteam_id)
        return workers

    def create_subteam(self, data: SubteamCreate) -> SubteamResponse:
        """Create a new subteam.

        Validates that no subteam with the same name exists.

        Args:
            data: Subteam creation data including name and department.

        Returns:
            SubteamResponse: The newly created subteam.

        Raises:
            ValueError: If subteam with the same name already exists.
        """
        log = self.logger.bind(method="create_subteam", data=data.model_dump())
        existing = self.subteam_repo.get_by_name(data.name)
        if existing:
            log.warning("subteam_already_exists")
            raise ValueError(f"subteam '{data.name}' already exists")
        subteam = self.subteam_repo.create(data.model_dump(mode="json"))
        log = self.logger.bind(method="create_subteam", subteam_id=str(subteam.id), name=data.name)
        log.info("subteam_created")
        return subteam

    def update_subteam(self, subteam_id: UUID, data: SubteamUpdate) -> SubteamResponse:
        """Update a subteam's information.

        Args:
            subteam_id: Unique identifier of the subteam to update.
            data: Partial subteam data with fields to update.

        Returns:
            SubteamResponse: The updated subteam data.

        Raises:
            ValueError: If subteam not found or update fails.
        """
        log = self.logger.bind(
            method="update_subteam", subteam_id=str(subteam_id), data=data.model_dump(exclude_none=True)
        )
        self.get_subteam(subteam_id)
        updated = self.subteam_repo.update(subteam_id, data.model_dump(exclude_none=True))
        if not updated:
            log.error("subteam_update_failed")
            raise ValueError(f"Failed to update subteam {subteam_id}")
        log.info("subteam_updated")
        return updated

    def delete_subteam(self, subteam_id: UUID) -> None:
        """Delete a subteam.

        Args:
            subteam_id: Unique identifier of the subteam to delete.

        Raises:
            ValueError: If subteam not found.
        """
        log = self.logger.bind(method="delete_subteam", subteam_id=str(subteam_id))
        self.get_subteam(subteam_id)
        self.subteam_repo.delete(subteam_id)
        log.info("subteam_deleted")

    def assign_worker(self, subteam_id: UUID, worker_id: UUID) -> None:
        """Assign a worker to a subteam.

        Validates that the worker is already assigned to the subteam's parent department
        before allowing the assignment.

        Args:
            subteam_id: Unique identifier of the subteam.
            worker_id: Unique identifier of the worker to assign.

        Raises:
            ValueError: If subteam not found or worker not assigned to parent department.
        """
        log = self.logger.bind(method="assign_worker", subteam_id=str(subteam_id), worker_id=str(worker_id))

        # Get subteam and validate it exists
        subteam = self.get_subteam(subteam_id)

        # Validate worker is assigned to the subteam's parent department
        worker_subteams = self.department_repo.get_departments_for_worker(worker_id)
        is_in_department = any(d.id == subteam.department_id for d in worker_subteams)

        if not is_in_department:
            log.warning("worker_not_in_parent_department", department_id=str(subteam.department_id))
            raise ValueError(f"Worker {worker_id} is not assigned to department {subteam.department_id}")

        self.subteam_repo.assign_worker(subteam_id, worker_id)
        log.info("worker_assigned_to_subteam")

    def unassign_worker(self, subteam_id: UUID, worker_id: UUID) -> None:
        """Remove a worker's assignment from a subteam.

        Args:
            subteam_id: Unique identifier of the subteam.
            worker_id: Unique identifier of the worker to unassign.

        Raises:
            ValueError: If subteam not found.
        """
        log = self.logger.bind(method="unassign_worker", subteam_id=str(subteam_id), worker_id=str(worker_id))
        self.get_subteam(subteam_id)
        self.subteam_repo.unassign_worker(subteam_id, worker_id)
        log.info(
            "worker_unassigned_from_subteam",
        )

    def set_hod(self, subteam_id: UUID, worker_id: UUID) -> SubteamResponse:
        """Set the Head of Department (HOD) for a subteam.

        Args:
            subteam_id: Unique identifier of the subteam.
            worker_id: Unique identifier of the worker to set as HOD.

        Returns:
            SubteamResponse: The updated subteam with new HOD.

        Raises:
            ValueError: If subteam not found or HOD assignment fails.
        """
        log = self.logger.bind(method="set_hod", subteam_id=str(subteam_id), worker_id=str(worker_id))
        self.get_subteam(subteam_id)
        updated = self.subteam_repo.update(subteam_id, {"hod_id": str(worker_id)})
        if not updated:
            log.error("set_hod_failed")
            raise ValueError(f"Failed to set HOD for subteam {subteam_id}")
        log.info("hod_assigned")
        return updated

    def get_subteams_by_department(self, department_id: UUID) -> list[SubteamResponse]:
        """Retrieve all subteams belonging to a specific department.

        Args:
            department_id: Unique identifier of the department.

        Returns:
            list[SubteamResponse]: List of subteams in the department.
        """
        log = self.logger.bind(method="get_subteams_by_department", department_id=str(department_id))
        subteams = self.subteam_repo.get_by_department(department_id)
        log.debug("fetched_subteams_by_department", count=len(subteams))
        return subteams
