import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWorkers } from '@/hooks/useWorkers'
import { useDepartments } from '@/hooks/useDepartments'
import { useListParams } from '@/hooks/useListParams'
import { useAuth } from '@/context/AuthContext'
import WorkerForm from '@/components/workers/WorkerForm'
import RoleEditor from '@/components/workers/RoleEditor'
import CreateAccountDialog from '@/components/workers/CreateAccountDialog'
import DeleteWorkerDialog from '@/components/workers/DeleteWorkerDialog'
import WorkerLeaveDialog from '@/components/workers/WorkerLeaveDialog'
import { getCurrentLeave } from '@/api/leave'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert } from '@/components/ui/alert'
import { Input } from '@/components/ui/input'
import { Pagination } from '@/components/ui/pagination'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table'
import {
    Plus,
    Pencil,
    UserX,
    UserPlus,
    Shield,
    KeyRound,
    Trash2,
    MoreVertical,
    CalendarOff,
    Search,
    X,
} from 'lucide-react'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

const ROLE_LABELS = { hod: 'HOD', assistant_hod: 'Assistant HOD' }

const roleVariant = role =>
    role === 'admin'
        ? 'destructive'
        : role === 'hod' || role === 'assistant_hod'
          ? 'default'
          : 'secondary'

const roleLabel = role => ROLE_LABELS[role] ?? role.charAt(0).toUpperCase() + role.slice(1)

const PAGE_SIZE = 25
// Radix Select cannot hold an empty value, so "no filter" needs a sentinel of its own.
const ALL = 'all'
const ROLE_OPTIONS = ['admin', 'hod', 'assistant_hod', 'worker']
// "Active" is is_active, so it includes people on leave — the same as the Active badge, which
// shows beside the On leave one.
const STATUS_OPTIONS = [
    { value: 'active', label: 'Active' },
    { value: 'inactive', label: 'Inactive' },
    { value: 'on_leave', label: 'On leave today' },
]

/** One toolbar select whose "All" item clears its filter. */
function FilterSelect({ label, value, onChange, options }) {
    return (
        <Select value={value || ALL} onValueChange={v => onChange(v === ALL ? '' : v)}>
            <SelectTrigger aria-label={label} className="h-11 w-full sm:h-9 sm:w-44">
                <SelectValue />
            </SelectTrigger>
            <SelectContent>
                <SelectItem value={ALL}>{label}: All</SelectItem>
                {options.map(o => (
                    <SelectItem key={o.value} value={o.value}>
                        {o.label}
                    </SelectItem>
                ))}
            </SelectContent>
        </Select>
    )
}

// Parsed from local date parts: new Date('2026-10-20') is read as UTC and renders as the 19th
// west of Greenwich.
const shortDate = dateStr =>
    new Date(dateStr + 'T00:00:00').toLocaleDateString('en-CA', { month: 'short', day: 'numeric' })

/** Shown wherever a worker's status is, so "on leave" is never mistaken for "inactive". */
function StatusBadges({ worker, leave }) {
    return (
        <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant={worker.is_active ? 'default' : 'secondary'}>
                {worker.is_active ? 'Active' : 'Inactive'}
            </Badge>
            {leave && (
                <Badge variant="warning">
                    {leave.end_date ? `On leave to ${shortDate(leave.end_date)}` : 'On leave'}
                </Badge>
            )}
        </div>
    )
}

/**
 * Every row action, behind one button.
 *
 * Shared by the desktop table cell and the mobile card. Inline, the five buttons ran to roughly
 * 700px and pushed the table into a horizontal scroll on anything short of a wide monitor; they
 * also read as five equally-weighted choices when four of them are occasional and one is
 * destructive.
 *
 * Which items appear is the single source of truth for both layouts — the two lists were
 * duplicated before, and had already drifted ("Create Account" against "Create account").
 */
function WorkerActionsMenu({
    worker,
    isAdmin,
    isDepartmentHead,
    onEdit,
    onRoles,
    onCreateAccount,
    onLeave,
    onDeactivate,
    onDelete,
    triggerClassName,
}) {
    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button
                    variant="ghost"
                    size="icon"
                    className={cn('shrink-0', triggerClassName)}
                    aria-label={`Actions for ${worker.first_name} ${worker.last_name}`}
                >
                    <MoreVertical size={18} />
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => onEdit(worker)}>
                    <Pencil size={14} className="mr-2" />
                    Edit
                </DropdownMenuItem>
                {isDepartmentHead && (
                    <DropdownMenuItem onClick={() => onRoles(worker)}>
                        <Shield size={14} className="mr-2" />
                        Roles
                    </DropdownMenuItem>
                )}
                {isAdmin && !worker.has_account && (
                    <DropdownMenuItem onClick={() => onCreateAccount(worker)}>
                        <KeyRound size={14} className="mr-2" />
                        Create account
                    </DropdownMenuItem>
                )}
                {isDepartmentHead && worker.is_active && (
                    <DropdownMenuItem onClick={() => onLeave(worker)}>
                        <CalendarOff size={14} className="mr-2" />
                        Leave
                    </DropdownMenuItem>
                )}
                {worker.is_active && (
                    <DropdownMenuItem
                        onClick={() => onDeactivate(worker)}
                        className="text-destructive focus:text-destructive"
                    >
                        <UserX size={14} className="mr-2" />
                        Deactivate
                    </DropdownMenuItem>
                )}
                {/* Only offered once a worker is deactivated, so removal is always a deliberate
                    second step. */}
                {isDepartmentHead && !worker.is_active && (
                    <DropdownMenuItem
                        onClick={() => onDelete(worker)}
                        className="text-destructive focus:text-destructive"
                    >
                        <Trash2 size={14} className="mr-2" />
                        Delete
                    </DropdownMenuItem>
                )}
            </DropdownMenuContent>
        </DropdownMenu>
    )
}

/** Shared by the desktop table cell and the mobile card, so the two cannot drift. */
function RoleBadges({ roles }) {
    if (!roles || roles.length === 0) {
        return <span className="text-xs text-muted-foreground">—</span>
    }
    return (
        <div className="flex gap-1 flex-wrap">
            {roles.map(role => (
                <Badge key={role} variant={roleVariant(role)} className="text-xs">
                    {roleLabel(role)}
                </Badge>
            ))}
        </div>
    )
}

export default function WorkersPage() {
    const navigate = useNavigate()
    const { isAdmin, isDepartmentHead, role } = useAuth()
    const list = useListParams(['department', 'role', 'status'])
    const { department, role: roleFilter, status } = list.filters
    const {
        workers,
        total,
        loading,
        error,
        addWorker,
        editWorker,
        removeWorker,
        destroyWorker,
        refetch,
    } = useWorkers({
        search: list.q || undefined,
        department_id: department || undefined,
        role: roleFilter || undefined,
        status: status || undefined,
        limit: PAGE_SIZE,
        offset: (list.page - 1) * PAGE_SIZE,
    })
    // Already scoped for heads: they can only filter by the departments they manage.
    const { departments } = useDepartments()

    // A deactivation under "Active", or a delete, can empty the last page; step back rather than
    // show "nothing here" beside a non-zero total.
    const { page, setPage } = list
    useEffect(() => {
        if (!loading && total > 0 && workers.length === 0 && page > 1) {
            setPage(Math.ceil(total / PAGE_SIZE))
        }
    }, [loading, total, workers.length, page, setPage])

    const [dialogOpen, setDialogOpen] = useState(false)
    const [editingWorker, setEditingWorker] = useState(null)
    const [roleDialogOpen, setRoleDialogOpen] = useState(false)
    const [editingRoles, setEditingRoles] = useState(null)
    const [accountDialogOpen, setAccountDialogOpen] = useState(false)
    const [accountWorker, setAccountWorker] = useState(null)
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
    const [deletingWorker, setDeletingWorker] = useState(null)
    const [leaveDialogOpen, setLeaveDialogOpen] = useState(false)
    const [leaveWorker, setLeaveWorker] = useState(null)
    // worker id -> the leave they are on right now. Fetched as one list rather than folded into
    // each worker, so the worker endpoint stays unaware of leave.
    const [leaveByWorker, setLeaveByWorker] = useState({})

    const refreshLeave = useCallback(() => {
        // Heads and admins only — the endpoint is gated, and a plain worker has no roster view
        // to badge. A failure is silent: a missing badge is cosmetic.
        if (!isDepartmentHead) return
        getCurrentLeave()
            .then(response =>
                setLeaveByWorker(
                    Object.fromEntries(response.data.map(entry => [entry.worker_id, entry]))
                )
            )
            .catch(() => {})
    }, [isDepartmentHead])

    useEffect(() => {
        refreshLeave()
    }, [refreshLeave])

    const handleOpenLeave = worker => {
        setLeaveWorker(worker)
        setLeaveDialogOpen(true)
    }

    const handleRegisterNewUser = () => {
        navigate('/workers/register')
    }

    const handleOpenEdit = worker => {
        setEditingWorker(worker)
        setDialogOpen(true)
    }

    const handleOpenRoleEdit = worker => {
        setEditingRoles(worker)
        setRoleDialogOpen(true)
    }

    const handleCloseRoleDialog = () => {
        setRoleDialogOpen(false)
        setEditingRoles(null)
    }

    const handleRoleUpdateSuccess = () => {
        refetch()
    }

    const handleOpenCreateAccount = worker => {
        setAccountWorker(worker)
        setAccountDialogOpen(true)
    }

    const handleCloseAccountDialog = () => {
        setAccountDialogOpen(false)
        setAccountWorker(null)
    }

    const handleOpenCreate = () => {
        setEditingWorker(null)
        setDialogOpen(true)
    }

    const handleClose = () => {
        setDialogOpen(false)
        setEditingWorker(null)
    }

    const handleSubmit = async (formData, departmentId) => {
        if (editingWorker) {
            await editWorker(editingWorker.id, formData)
        } else {
            await addWorker(formData, departmentId)
        }
        handleClose()
        // The list is one filtered, sorted page, so a patched-in row may not belong on it.
        refetch()
    }

    const handleDeactivate = async worker => {
        if (!confirm(`Deactivate ${worker.first_name} ${worker.last_name}?`)) return
        await removeWorker(worker.id)
        refetch()
    }

    const handleDestroyed = async id => {
        await destroyWorker(id)
        refetch()
    }

    const handleOpenDelete = worker => {
        setDeletingWorker(worker)
        setDeleteDialogOpen(true)
    }

    // Only the first load replaces the page; later fetches keep the toolbar mounted and focused.
    if (loading && total === null) {
        return (
            <div className="flex items-center justify-center h-64">
                <p className="text-muted-foreground">Loading workers...</p>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            {/* Page header */}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h2 className="text-2xl font-bold">Workers</h2>
                    <p className="text-muted-foreground text-sm mt-1">
                        {list.hasFilters ? `${total ?? 0} matching` : `${total ?? 0} total workers`}
                    </p>
                </div>
                <div className="flex flex-wrap gap-2">
                    {isAdmin && (
                        <Button onClick={handleRegisterNewUser} variant="default">
                            <UserPlus size={16} className="mr-2" />
                            Register New User
                        </Button>
                    )}
                    <Button onClick={handleOpenCreate} variant="outline">
                        <Plus size={16} className="mr-2" />
                        Add Worker Profile
                    </Button>
                </div>
            </div>

            {/* Error state */}
            {error && (
                <Alert variant="destructive">
                    <p className="text-sm">{error}</p>
                </Alert>
            )}

            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
                <div className="relative sm:w-64">
                    <Search
                        size={16}
                        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                    />
                    <Input
                        value={list.searchText}
                        onChange={e => list.setSearchText(e.target.value)}
                        placeholder="Search by name or email"
                        aria-label="Search workers"
                        className="h-11 pl-9 sm:h-9"
                    />
                </div>
                <FilterSelect
                    label="Department"
                    value={department}
                    onChange={v => list.setFilter('department', v)}
                    options={departments.map(d => ({ value: d.id, label: d.name }))}
                />
                <FilterSelect
                    label="Role"
                    value={roleFilter}
                    onChange={v => list.setFilter('role', v)}
                    options={ROLE_OPTIONS.map(r => ({ value: r, label: roleLabel(r) }))}
                />
                <FilterSelect
                    label="Status"
                    value={status}
                    onChange={v => list.setFilter('status', v)}
                    options={STATUS_OPTIONS}
                />
                {list.hasFilters && (
                    <Button variant="ghost" className="min-h-11 sm:min-h-0" onClick={list.clear}>
                        <X size={16} className="mr-1" />
                        Clear filters
                    </Button>
                )}
            </div>

            {!error && !loading && workers.length === 0 && list.hasFilters && (
                <div className="flex flex-col items-center justify-center h-64 border rounded-lg">
                    <p className="text-muted-foreground">No workers match these filters</p>
                    <Button variant="outline" className="mt-4" onClick={list.clear}>
                        Clear filters
                    </Button>
                </div>
            )}

            {/* Empty state */}
            {!error && !loading && workers.length === 0 && !list.hasFilters && (
                <div className="flex flex-col items-center justify-center h-64 border rounded-lg">
                    <p className="text-muted-foreground">No workers yet</p>
                    <Button variant="outline" className="mt-4" onClick={handleOpenCreate}>
                        Add your first worker
                    </Button>
                </div>
            )}

            <div
                aria-busy={loading}
                className={cn('space-y-4 transition-opacity', loading && 'opacity-60')}
            >
                {/* Workers table — desktop */}
                {workers.length > 0 && (
                    <div className="hidden border rounded-lg overflow-hidden md:block">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Name</TableHead>
                                    <TableHead>Email</TableHead>
                                    <TableHead>Phone</TableHead>
                                    {isAdmin && <TableHead>Roles</TableHead>}
                                    <TableHead>Status</TableHead>
                                    <TableHead className="w-16 text-right">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {workers.map(worker => (
                                    <TableRow key={worker.id}>
                                        <TableCell className="font-medium">
                                            {worker.first_name} {worker.last_name}
                                        </TableCell>
                                        <TableCell>{worker.email}</TableCell>
                                        <TableCell>{worker.phone}</TableCell>
                                        {isAdmin && (
                                            <TableCell>
                                                <RoleBadges roles={worker.roles} />
                                            </TableCell>
                                        )}
                                        <TableCell>
                                            <StatusBadges
                                                worker={worker}
                                                leave={leaveByWorker[worker.id]}
                                            />
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <div className="flex justify-end">
                                                <WorkerActionsMenu
                                                    worker={worker}
                                                    isAdmin={isAdmin}
                                                    isDepartmentHead={isDepartmentHead}
                                                    onEdit={handleOpenEdit}
                                                    onRoles={handleOpenRoleEdit}
                                                    onCreateAccount={handleOpenCreateAccount}
                                                    onLeave={handleOpenLeave}
                                                    onDeactivate={handleDeactivate}
                                                    onDelete={handleOpenDelete}
                                                    triggerClassName="-mr-2"
                                                />
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>
                )}

                {/* Below md the six-column table becomes a card per worker. The five row actions —
                which alone run to ~500px — collapse into a menu. */}
                {workers.length > 0 && (
                    <ul className="space-y-2 md:hidden">
                        {workers.map(worker => (
                            <li key={worker.id} className="rounded-lg border p-4">
                                <div className="flex items-start justify-between gap-3">
                                    <div className="min-w-0">
                                        <p className="truncate font-medium">
                                            {worker.first_name} {worker.last_name}
                                        </p>
                                        <p className="truncate text-sm text-muted-foreground">
                                            {worker.email}
                                        </p>
                                        {worker.phone && (
                                            <a
                                                href={`tel:${worker.phone}`}
                                                className="text-sm text-primary underline underline-offset-2"
                                            >
                                                {worker.phone}
                                            </a>
                                        )}
                                    </div>
                                    <WorkerActionsMenu
                                        worker={worker}
                                        isAdmin={isAdmin}
                                        isDepartmentHead={isDepartmentHead}
                                        onEdit={handleOpenEdit}
                                        onRoles={handleOpenRoleEdit}
                                        onCreateAccount={handleOpenCreateAccount}
                                        onLeave={handleOpenLeave}
                                        onDeactivate={handleDeactivate}
                                        onDelete={handleOpenDelete}
                                        triggerClassName="-mr-2"
                                    />
                                </div>
                                <div className="mt-3 flex flex-wrap items-center gap-2">
                                    <StatusBadges
                                        worker={worker}
                                        leave={leaveByWorker[worker.id]}
                                    />
                                    {isAdmin && <RoleBadges roles={worker.roles} />}
                                </div>
                            </li>
                        ))}
                    </ul>
                )}

                <Pagination
                    page={list.page}
                    pageSize={PAGE_SIZE}
                    total={total}
                    onPageChange={list.setPage}
                />
            </div>

            <WorkerLeaveDialog
                worker={leaveWorker}
                open={leaveDialogOpen}
                onOpenChange={setLeaveDialogOpen}
                onChanged={refreshLeave}
            />

            {/* Create / Edit dialog */}
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>{editingWorker ? 'Edit Worker' : 'Add Worker'}</DialogTitle>
                    </DialogHeader>
                    <WorkerForm
                        initial={editingWorker ?? undefined}
                        departments={editingWorker ? undefined : departments}
                        requireDepartment={!isAdmin}
                        onSubmit={handleSubmit}
                        onCancel={handleClose}
                    />
                </DialogContent>
            </Dialog>

            {/* Role Editor dialog */}
            {isAdmin && (
                <Dialog open={roleDialogOpen} onOpenChange={setRoleDialogOpen}>
                    <DialogContent className="sm:max-w-md">
                        <DialogHeader>
                            <DialogTitle>Manage User Roles</DialogTitle>
                        </DialogHeader>
                        {editingRoles && (
                            <RoleEditor
                                workerId={editingRoles.id}
                                workerName={`${editingRoles.first_name} ${editingRoles.last_name}`}
                                currentUserRole={role}
                                onClose={handleCloseRoleDialog}
                                onSuccess={handleRoleUpdateSuccess}
                            />
                        )}
                    </DialogContent>
                </Dialog>
            )}

            {/* Create Account dialog */}
            {isAdmin && (
                <Dialog open={accountDialogOpen} onOpenChange={setAccountDialogOpen}>
                    <DialogContent className="sm:max-w-md">
                        <DialogHeader>
                            <DialogTitle>Create Login Account</DialogTitle>
                        </DialogHeader>
                        {accountWorker && (
                            <CreateAccountDialog
                                workerId={accountWorker.id}
                                workerName={`${accountWorker.first_name} ${accountWorker.last_name}`}
                                onClose={handleCloseAccountDialog}
                                onSuccess={refetch}
                            />
                        )}
                    </DialogContent>
                </Dialog>
            )}

            {/* Delete dialog — gated identically to the Delete button that opens it */}
            {isDepartmentHead && (
                <DeleteWorkerDialog
                    worker={deletingWorker}
                    open={deleteDialogOpen}
                    onOpenChange={setDeleteDialogOpen}
                    onDeleted={handleDestroyed}
                />
            )}
        </div>
    )
}
