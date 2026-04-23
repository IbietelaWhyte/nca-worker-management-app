from uuid import UUID

from app.core.logging import get_logger
from app.repository.departments.repository import DepartmentRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.departments.models import DepartmentResponse
from app.schemas.workers.models import WorkerCreate, WorkerResponse, WorkerUpdate

logger = get_logger(__name__)


class WorkerService:
    def __init__(
        self,
        worker_repo: WorkerRepository,
        department_repo: DepartmentRepository,
    ) -> None:
        """Initialize the WorkerService with required repositories.

        Args:
            worker_repo: Repository for worker database operations.
            department_repo: Repository for department database operations.
        """
        self.worker_repo = worker_repo
        self.department_repo = department_repo

        # bind the logger to the service name for structured logging
        self.logger = logger.bind(service="WorkerService")

    def get_worker(self, worker_id: UUID) -> WorkerResponse:
        """Retrieve a worker by ID.

        Args:
            worker_id: Unique identifier of the worker.

        Returns:
            WorkerResponse: The worker data with roles.

        Raises:
            ValueError: If worker not found.
        """
        # bind the method and worker_id for better traceability in logs
        log = self.logger.bind(method="get_worker", worker_id=str(worker_id))
        worker = self.worker_repo.get_by_id(worker_id)
        if not worker:
            log.warning("worker_not_found")
            raise ValueError(f"Worker {worker_id} not found")

        # Load roles for the worker
        worker.roles = self.worker_repo.get_worker_roles(worker_id)
        return worker

    def get_all_workers(self) -> list[WorkerResponse]:
        """Retrieve all workers.

        Returns:
            list[WorkerResponse]: List of all workers in the system with their roles.
        """
        # bind the method for better traceability in logs
        log = self.logger.bind(method="get_all_workers")
        workers = self.worker_repo.get_all()

        # Load roles for each worker
        for worker in workers:
            worker.roles = self.worker_repo.get_worker_roles(worker.id)

        log.info("fetched_all_workers", count=len(workers))
        return workers

    def get_active_workers(self) -> list[WorkerResponse]:
        """Retrieve all active workers.

        Returns:
            list[WorkerResponse]: List of workers with active status and their roles.
        """
        # bind the method for better traceability in logs
        log = self.logger.bind(method="get_active_workers")
        workers = self.worker_repo.get_active_workers()

        # Load roles for each worker
        for worker in workers:
            worker.roles = self.worker_repo.get_worker_roles(worker.id)

        log.info("fetched_active_workers", count=len(workers))
        return workers

    def get_workers_by_department(self, department_id: UUID) -> list[WorkerResponse]:
        """Retrieve all workers assigned to a specific department.

        Args:
            department_id: Unique identifier of the department.

        Returns:
            list[WorkerResponse]: List of workers in the department.
        """
        # bind the method and department_id for better traceability in logs
        log = self.logger.bind(method="get_workers_by_department", department_id=str(department_id))
        workers = self.worker_repo.get_workers_by_department(department_id)
        log.info(
            "fetched_workers_by_department",
            count=len(workers),
        )
        return workers

    def create_worker(self, data: WorkerCreate) -> WorkerResponse:
        """Create a new worker.

        Validates that either email or phone is provided and checks for existing workers
        with the same contact information.

        Args:
            data: Worker creation data including name, contact info.

        Returns:
            WorkerResponse: The newly created worker.

        Raises:
            ValueError: If contact info is missing or worker already exists.
        """
        # bind the method and email for better traceability in logs
        log = self.logger.bind(method="create_worker", email=data.email)
        if data.email:
            existing = self.worker_repo.get_by_email(data.email)
        elif data.phone:
            existing = self.worker_repo.get_by_phone(data.phone)
        else:
            log.error("missing_contact_info")
            raise ValueError("Either email or phone number must be provided")
        if existing:
            log.warning("worker_already_exists")
            raise ValueError(f"Worker with email {data.email} already exists")
        worker = self.worker_repo.create(data.model_dump())
        log.info("worker_created", worker_id=str(worker.id))
        return worker

    def update_worker(self, worker_id: UUID, data: WorkerUpdate) -> WorkerResponse:
        """Update a worker's information.

        Args:
            worker_id: Unique identifier of the worker to update.
            data: Partial worker data with fields to update (including optional roles).

        Returns:
            WorkerResponse: The updated worker data with roles.

        Raises:
            ValueError: If worker not found or update fails.
        """
        # bind the method and worker_id for better traceability in logs
        log = self.logger.bind(
            method="update_worker", worker_id=str(worker_id), data=data.model_dump(exclude_none=True)
        )

        # Get existing worker
        worker = self.worker_repo.get_by_id(worker_id)
        if not worker:
            log.warning("worker_not_found")
            raise ValueError(f"Worker {worker_id} not found")

        # Extract roles and assistant_hod_departments from update data if present
        update_dict = data.model_dump(exclude_none=True)
        new_roles = update_dict.pop("roles", None)
        new_assistant_hod_departments = update_dict.pop("assistant_hod_departments", None)

        # Update worker profile fields if any were provided
        if update_dict:
            updated = self.worker_repo.update(worker_id, update_dict)
            if not updated:
                log.error("worker_update_failed")
                raise ValueError(f"Failed to update worker {worker_id}")
            worker = updated

        # Update roles if provided
        if new_roles is not None:
            # Delete all existing roles
            self.worker_repo.delete_worker_roles(worker_id)
            log.info("deleted_existing_roles")

            # Insert new roles
            for role in new_roles:
                self.worker_repo.create_worker_role(worker_id, role)

            log.info("roles_updated", new_roles=new_roles)

        # Update assistant_hod department assignments if provided
        if new_assistant_hod_departments is not None:
            # Get current assistant_hod departments
            current_dept_ids = set(self.department_repo.get_assistant_hod_departments(worker_id))
            new_dept_ids = set(new_assistant_hod_departments)

            # Remove old assignments
            for dept in current_dept_ids - new_dept_ids:
                self.department_repo.remove_assistant_hod(worker_id, dept.id)

            # Add new assignments
            for dept_id in new_dept_ids - current_dept_ids:
                self.department_repo.assign_assistant_hod(worker_id, dept_id)

            log.info("assistant_hod_departments_updated", departments=new_assistant_hod_departments)

        # Load current roles for response
        worker.roles = self.worker_repo.get_worker_roles(worker_id)

        log.info("worker_updated")
        return worker

    def deactivate_worker(self, worker_id: UUID) -> WorkerResponse:
        """Deactivate a worker (set is_active to False).

        Args:
            worker_id: Unique identifier of the worker to deactivate.

        Returns:
            WorkerResponse: The updated worker with is_active=False.

        Raises:
            ValueError: If worker not found or deactivation fails.
        """
        # bind the method and worker_id for better traceability in logs
        log = self.logger.bind(method="deactivate_worker", worker_id=str(worker_id))
        self.get_worker(worker_id)
        updated = self.worker_repo.update(worker_id, {"is_active": False})
        if not updated:
            log.error("worker_deactivation_failed")
            raise ValueError(f"Failed to deactivate worker {worker_id}")
        log.info("worker_deactivated")
        return updated

    def search_workers(self, query: str) -> list[WorkerResponse]:
        """Search for workers by name.

        Performs case-insensitive partial matching on first and last names.

        Args:
            query: Search term to match against worker names.

        Returns:
            list[WorkerResponse]: List of workers matching the search query.
        """
        # bind the method and query for better traceability in logs
        log = self.logger.bind(method="search_workers", query=query)
        workers = self.worker_repo.search(query)
        log.info("worker_search", results=len(workers), workers=workers)
        return workers

    def get_worker_departments(self, worker_id: UUID) -> list[DepartmentResponse]:
        """Retrieve all departments a worker is assigned to.

        Args:
            worker_id: Unique identifier of the worker.

        Returns:
            list[DepartmentResponse]: List of departments the worker belongs to.
        """
        log = self.logger.bind(method="get_worker_departments", worker_id=str(worker_id))
        departments = self.department_repo.get_departments_for_worker(worker_id)
        log.info("fetched_worker_departments", count=len(departments))
        return [DepartmentResponse.model_validate(dept) for dept in departments]

    def can_manage_worker(self, manager_id: UUID, worker_id: UUID) -> bool:
        """Check if a manager (HOD or Assistant HOD) can manage a specific worker.

        A manager can manage a worker if the worker belongs to at least one department
        that the manager oversees (either as HOD or assistant_hod).

        Args:
            manager_id: Unique identifier of the manager (HOD or assistant_hod).
            worker_id: Unique identifier of the worker to check.

        Returns:
            bool: True if manager oversees at least one department containing the worker.
        """
        log = self.logger.bind(method="can_manage_worker", manager_id=str(manager_id), worker_id=str(worker_id))

        # Get departments where this user is HOD
        hod_departments = self.department_repo.get_departments_by_hod(manager_id)

        # Get departments where this user is assistant_hod
        assistant_hod_dept_ids = self.department_repo.get_assistant_hod_departments(manager_id)
        assistant_hod_departments = [self.department_repo.get_by_id(dept.id) for dept in assistant_hod_dept_ids]
        assistant_hod_departments = [d for d in assistant_hod_departments if d is not None]

        # Combine all managed departments
        all_managed_departments = hod_departments + assistant_hod_departments

        if not all_managed_departments:
            log.info("manager_has_no_departments")
            return False

        # Get departments the worker belongs to
        worker_departments = self.department_repo.get_departments_for_worker(worker_id)
        if not worker_departments:
            log.info("worker_has_no_departments")
            return False

        # Check for overlap
        managed_dept_ids = {dept.id for dept in all_managed_departments}  # type: ignore
        worker_dept_ids = {dept.id for dept in worker_departments}
        can_manage = bool(managed_dept_ids & worker_dept_ids)

        log.info("can_manage_check", can_manage=can_manage)
        return can_manage
