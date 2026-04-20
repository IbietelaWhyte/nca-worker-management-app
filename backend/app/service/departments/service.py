from uuid import UUID

from app.core.logging import get_logger
from app.repository.departments.repository import DepartmentRepository
from app.schemas.departments.models import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
    DepartmentWithWorkersResponse,
)

logger = get_logger(__name__)


class DepartmentService:
    def __init__(self, department_repo: DepartmentRepository) -> None:
        """Initialize the DepartmentService with required repository.

        Args:
            department_repo: Repository for department database operations.
        """
        self.department_repo = department_repo
        self.logger = logger.bind(service="DepartmentService")

    def get_department(self, department_id: UUID) -> DepartmentResponse:
        """Retrieve a department by ID.

        Args:
            department_id: Unique identifier of the department.

        Returns:
            DepartmentResponse: The department data.

        Raises:
            ValueError: If department not found.
        """
        log = self.logger.bind(method="get_department", department_id=str(department_id))
        dept = self.department_repo.get_by_id(department_id)
        if not dept:
            log.warning("department_not_found")
            raise ValueError(f"Department {department_id} not found")
        return dept

    def get_all_departments(self) -> list[DepartmentResponse]:
        """Retrieve all departments.

        Returns:
            list[DepartmentResponse]: List of all departments in the system.
        """
        log = self.logger.bind(method="get_all_departments")
        depts = self.department_repo.get_all()
        log.info("fetched_all_departments", count=len(depts))
        return depts

    def get_departments_by_hod(self, hod_id: UUID) -> list[DepartmentResponse]:
        """Retrieve all departments where a worker is the Head of Department (HOD).

        Args:
            hod_id: Unique identifier of the worker who is an HOD.

        Returns:
            list[DepartmentResponse]: List of departments where the worker is HOD.
        """
        log = self.logger.bind(method="get_departments_by_hod", hod_id=str(hod_id))
        depts = self.department_repo.get_departments_by_hod(hod_id)
        log.info("fetched_departments_by_hod", count=len(depts))
        return depts

    def get_department_with_workers(self, department_id: UUID) -> DepartmentWithWorkersResponse:
        """Retrieve a department with all assigned workers embedded.

        Args:
            department_id: Unique identifier of the department.

        Returns:
            DepartmentWithWorkersResponse: Department with worker details.

        Raises:
            ValueError: If department not found.
        """
        log = self.logger.bind(method="get_department_with_workers", department_id=str(department_id))
        dept = self.department_repo.get_with_workers(department_id)
        if not dept:
            log.warning("department_not_found")
            raise ValueError(f"Department {department_id} not found")
        return dept

    def create_department(self, data: DepartmentCreate) -> DepartmentResponse:
        """Create a new department.

        Validates that no department with the same name exists.

        Args:
            data: Department creation data including name and description.

        Returns:
            DepartmentResponse: The newly created department.

        Raises:
            ValueError: If department with the same name already exists.
        """
        log = self.logger.bind(method="create_department", data=data.model_dump())
        existing = self.department_repo.get_by_name(data.name)
        if existing:
            log.warning("department_already_exists")
            raise ValueError(f"Department '{data.name}' already exists")
        dept = self.department_repo.create(data.model_dump())
        log.info("department_created")
        return dept

    def update_department(self, department_id: UUID, data: DepartmentUpdate) -> DepartmentResponse:
        """Update a department's information.

        Args:
            department_id: Unique identifier of the department to update.
            data: Partial department data with fields to update.

        Returns:
            DepartmentResponse: The updated department data.

        Raises:
            ValueError: If department not found or update fails.
        """
        log = self.logger.bind(
            method="update_department", department_id=str(department_id), data=data.model_dump(exclude_none=True)
        )
        self.get_department(department_id)
        updated = self.department_repo.update(department_id, data.model_dump(exclude_none=True))
        if not updated:
            log.error("department_update_failed")
            raise ValueError(f"Failed to update department {department_id}")
        log.info("department_updated")
        return updated

    def delete_department(self, department_id: UUID) -> None:
        """Delete a department.

        Args:
            department_id: Unique identifier of the department to delete.

        Raises:
            ValueError: If department not found.
        """
        log = self.logger.bind(method="delete_department", department_id=str(department_id))
        self.get_department(department_id)
        self.department_repo.delete(department_id)
        log.info("department_deleted")

    def assign_worker(self, department_id: UUID, worker_id: UUID) -> None:
        """Assign a worker to a department.

        Args:
            department_id: Unique identifier of the department.
            worker_id: Unique identifier of the worker to assign.

        Raises:
            ValueError: If department not found.
        """
        log = self.logger.bind(method="assign_worker", department_id=str(department_id), worker_id=str(worker_id))
        self.get_department(department_id)
        self.department_repo.assign_worker(department_id, worker_id)
        log.info("worker_assigned_to_department")

    def unassign_worker(self, department_id: UUID, worker_id: UUID) -> None:
        """Remove a worker's assignment from a department.

        Args:
            department_id: Unique identifier of the department.
            worker_id: Unique identifier of the worker to unassign.

        Raises:
            ValueError: If department not found.
        """
        log = self.logger.bind(method="unassign_worker", department_id=str(department_id), worker_id=str(worker_id))
        self.get_department(department_id)
        self.department_repo.unassign_worker(department_id, worker_id)
        log.info(
            "worker_unassigned_from_department",
        )

    def set_hod(self, department_id: UUID, worker_id: UUID) -> DepartmentResponse:
        """Set the Head of Department (HOD) for a department.

        Args:
            department_id: Unique identifier of the department.
            worker_id: Unique identifier of the worker to set as HOD.

        Returns:
            DepartmentResponse: The updated department with new HOD.

        Raises:
            ValueError: If department not found or HOD assignment fails.
        """
        log = self.logger.bind(method="set_hod", department_id=str(department_id), worker_id=str(worker_id))
        self.get_department(department_id)
        updated = self.department_repo.update(department_id, {"hod_id": str(worker_id)})
        if not updated:
            log.error("set_hod_failed")
            raise ValueError(f"Failed to set HOD for department {department_id}")
        log.info("hod_assigned")
        return updated
