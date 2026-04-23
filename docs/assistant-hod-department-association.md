# Assistant HOD Department Association

## Problem

The assistant_hod role needed department-specific tracking, but modifying the existing `worker_app_roles` table would have required:
- Adding a nullable `department_id` column
- Backfilling existing data
- Complex constraints to handle nullable/non-nullable department_id based on role

## Solution: Separate Table Design

### Two-Table Approach (Option 1)

We use **two separate tables** to track assistant HOD permissions:

1. **`worker_app_roles`** - Global permission level (role='assistant_hod')
2. **`department_assistant_hods`** - Department-specific assignments

This mirrors how HOD works:
- **HOD**: `worker_app_roles` (role='hod') + `departments.hod_id`
- **Assistant HOD**: `worker_app_roles` (role='assistant_hod') + `department_assistant_hods`

### Benefits

1. **No backfilling** - existing `worker_app_roles` data unchanged
2. **Clean separation** - permission vs. assignment
3. **No nullable columns** - every row in `department_assistant_hods` has a department_id
4. **Extensible** - easy to add assistant_hod-specific metadata later
5. **Simpler constraints** - `worker_app_roles` keeps original `unique(worker_id, role)` constraint

## Database Changes

**Migration: `20260420000002_department_assistant_hods.sql`**

Created new table:
```sql
create table public.department_assistant_hods (
    id uuid primary key default gen_random_uuid(),
    worker_id uuid not null references public.workers(id) on delete cascade,
    department_id uuid not null references public.departments(id) on delete cascade,
    assigned_at timestamptz not null default now(),
    unique (worker_id, department_id)
);
```

Key features:
- Worker can be assistant_hod for multiple departments
- No nullable columns required
- RLS policies allow admins and HODs to manage assignments
- Indexed on both worker_id and department_id for performance

## Backend Schema Changes

**File: `backend/app/schemas/workers/models.py`**

Updated `WorkerUpdate` schema:
```python
class WorkerUpdate(BaseModel):
    # ... other fields
    roles: list[UserRole] | None = Field(default=None, min_length=1)
    assistant_hod_departments: list[UUID] | None = Field(
        default=None, 
        description="Departments for assistant_hod role"
    )
```

Roles and department assignments are now separate fields.

## Backend Repository Changes

**File: `backend/app/repository/departments/repository.py`**

Added new methods:
1. `assign_assistant_hod(worker_id, department_id)` - Assign assistant_hod to department
2. `remove_assistant_hod(worker_id, department_id)` - Remove assistant_hod from department
3. `get_assistant_hod_departments(worker_id)` - Get all departments where worker is assistant_hod
4. `get_department_assistant_hods(department_id)` - Get all assistant_hods for a department

**File: `backend/app/repository/workers/repository.py`**

No changes needed - continues to work with `worker_app_roles` table for role permissions.

## Backend Service Changes

**File: `backend/app/service/workers/service.py`**

1. `can_manage_worker()`:
   - Now checks both HOD departments AND assistant_hod departments
   - Uses `department_repo.get_assistant_hod_departments()` instead of worker_repo

2. `update_worker()`:
   - Handles `roles` and `assistant_hod_departments` separately
   - Manages department assignments via department repository
   - Adds/removes department assignments as needed

## Backend Router Changes

**File: `backend/app/router/workers/router.py`**

1. `update_worker()`:
   - Validates that HODs/Assistant HODs can only assign assistant_hod for departments they manage
   - Updated to work with separate `roles` and `assistant_hod_departments` fields
   - Fetches both HOD departments and assistant_hod departments for permission checks

## Usage Examples

### Assigning Assistant HOD Role

To make a worker an assistant_hod for specific departments:

```json
PATCH /workers/{worker_id}
{
  "roles": ["worker", "assistant_hod"],
  "assistant_hod_departments": ["dept-uuid-1", "dept-uuid-2"]
}
```

### Removing Assistant HOD from a Department

```json
PATCH /workers/{worker_id}
{
  "assistant_hod_departments": ["dept-uuid-1"]  // Only keep dept 1
}
```

### Adding Assistant HOD to Additional Department

```json
PATCH /workers/{worker_id}
{
  "assistant_hod_departments": ["dept-uuid-1", "dept-uuid-2", "dept-uuid-3"]
}
```

## Permission Rules

1. **Admin**: Can assign any role to any department
2. **HOD/Assistant HOD**:
   - Can only assign `worker` or `assistant_hod` roles
   - Can only assign `assistant_hod` for departments they manage
   - Cannot assign `admin` or `hod` roles

## How It Works

### Checking Permissions

When a worker has assistant_hod role:
1. Backend checks `worker_app_roles` for role='assistant_hod' (global permission)
2. Backend queries `department_assistant_hods` for specific department assignments
3. Both must be present for a worker to act as assistant_hod of a department

### Role Assignment Flow

1. Assign role in `worker_app_roles`: `INSERT INTO worker_app_roles (worker_id, role) VALUES (..., 'assistant_hod')`
2. Assign departments in `department_assistant_hods`: `INSERT INTO department_assistant_hods (worker_id, department_id) VALUES (...)`

### Department Access Check

```python
# Get all departments a manager (HOD or Assistant HOD) oversees:
hod_depts = get_departments_by_hod(manager_id)  # From departments.hod_id
asst_depts = get_assistant_hod_departments(manager_id)  # From department_assistant_hods
all_managed = hod_depts + asst_depts
```

## Frontend Changes Required

The frontend `RoleEditor` component will need updates to:

1. When `assistant_hod` role is selected, show department multi-select
2. Display which department(s) an assistant_hod is associated with
3. Allow adding/removing assistant_hod for specific departments
4. Send both `roles` and `assistant_hod_departments` arrays in API calls

## Migration Steps

1. Run the database migration: `20260420000002_department_assistant_hods.sql`
2. Deploy backend changes
3. Update frontend to use new `assistant_hod_departments` field
4. Test permission enforcement for assistant_hod role assignments
