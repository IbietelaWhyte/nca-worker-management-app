# Add Worker Management to Subteams

## Overview
Implements inline worker assignment and management for subteams on the Department Detail page. Users can now add/remove workers to/from subteams directly through an expandable table interface.

## Features

### Backend
- **New Endpoint**: `GET /api/v1/subteams/{id}/workers` - Retrieves all workers assigned to a subteam
- **Existing Endpoints Enhanced**:
  - `POST /api/v1/subteams/{id}/workers/{worker_id}` - Assign worker to subteam (validates worker is in parent department)
  - `DELETE /api/v1/subteams/{id}/workers/{worker_id}` - Remove worker from subteam

### Frontend
- **Expandable Subteam Rows**: Click any subteam row to expand and view assigned workers
- **Worker Count Display**: Shows member count in collapsed view ("Click to view" or "X workers")
- **Add Member Button**: Quick access to assign workers to subteams (next to Edit/Delete buttons)
- **Add Worker Dialog**: 
  - Shows only department members not already in the subteam
  - Includes helpful indicator: "Only showing members of {department name}"
  - Empty state when all department members are assigned
- **Remove Worker Action**: One-click removal with confirmation dialog
- **Real-time Updates**: Worker count and list update immediately after add/remove operations

## Implementation Details

### Database Layer
- Workers are assigned to subteams via the existing `worker_departments` junction table
- The `subteam_id` column is updated when assigning a worker to a subteam
- Worker remains associated with parent department when assigned to subteam
- Setting `subteam_id` to NULL removes from subteam while keeping department membership

### Backend Changes

**Modified Files:**
- `backend/app/router/subteams/router.py` - Added GET endpoint for subteam with workers
- `backend/app/service/subteams/service.py` - Enhanced validation to distinguish between "subteam not found" and "no workers assigned"
- `backend/app/repository/subteams/repository.py` - Fixed `assign_worker` and `unassign_worker` to UPDATE existing rows instead of INSERT/DELETE
- `backend/app/repository/subteams/queries.py` - Added `DEPARTMENT_ID` to `JunctionColumns` and fixed query to join through junction table
- `backend/app/schemas/subteams/models.py` - Added `SubteamWithWorkersResponse` import to router

**Key Fixes:**
- Query properly joins through `worker_departments` junction table: `workers:worker_departments!subteam_id(workers(*))`
- Returns empty list `[]` for subteams with no workers (not 404)
- Type-safe dictionary access with proper casting

### Frontend Changes

**Modified Files:**
- `frontend/src/api/subteams.js` - Added API client functions:
  - `getSubteamWithWorkers(subteamId)`
  - `assignWorkerToSubteam(subteamId, workerId)`
  - `unassignWorkerFromSubteam(subteamId, workerId)`
- `frontend/src/pages/DepartmentDetailPage.jsx` - Major UI enhancements:
  - Added state management for expanded rows and worker data
  - Implemented expandable table rows with ChevronRight/ChevronDown icons
  - Added worker count column
  - Created inline worker list with remove buttons
  - Built "Add Worker to Subteam" dialog with department member filtering

**UI Pattern:**
- Follows existing department member management pattern for consistency
- Honors permission controls (HOD/Admin only)
- Provides loading states, empty states, and error handling

## Testing Checklist

- [x] Backend endpoint returns workers assigned to subteam
- [x] Backend returns empty list for subteam with no workers
- [x] Backend validates worker is in parent department before assignment
- [x] Frontend displays expandable subteam rows
- [x] Frontend shows accurate worker count
- [x] Frontend filters out already-assigned workers in add dialog
- [x] Frontend updates count after add/remove operations
- [x] Permission controls work correctly (HOD/Admin only)

## Screenshots
_Add screenshots of the UI showing:_
1. Collapsed subteam row with worker count
2. Expanded subteam row with worker list
3. Add Worker to Subteam dialog

## Notes
- Empty subteams now return `200 OK` with empty array instead of `404 Not Found`
- Worker assignment requires existing department membership (validated by backend)
- Removing a worker from a subteam keeps them in the parent department
- Multiple workers can be assigned to the same subteam
- UI automatically refreshes after each add/remove operation
