import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWorkers } from '@/hooks/useWorkers'
import { useAuth } from '@/context/AuthContext'
import WorkerForm from '@/components/workers/WorkerForm'
import RoleEditor from '@/components/workers/RoleEditor'
import CreateAccountDialog from '@/components/workers/CreateAccountDialog'
import DeleteWorkerDialog from '@/components/workers/DeleteWorkerDialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert } from '@/components/ui/alert'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table'
import { Plus, Pencil, UserX, UserPlus, Shield, KeyRound, Trash2, MoreVertical } from 'lucide-react'
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
    const { workers, loading, error, addWorker, editWorker, removeWorker, destroyWorker, refetch } =
        useWorkers()

    const [dialogOpen, setDialogOpen] = useState(false)
    const [editingWorker, setEditingWorker] = useState(null)
    const [roleDialogOpen, setRoleDialogOpen] = useState(false)
    const [editingRoles, setEditingRoles] = useState(null)
    const [accountDialogOpen, setAccountDialogOpen] = useState(false)
    const [accountWorker, setAccountWorker] = useState(null)
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
    const [deletingWorker, setDeletingWorker] = useState(null)

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

    const handleSubmit = async formData => {
        if (editingWorker) {
            await editWorker(editingWorker.id, formData)
        } else {
            await addWorker(formData)
        }
        handleClose()
    }

    const handleDeactivate = async worker => {
        if (!confirm(`Deactivate ${worker.first_name} ${worker.last_name}?`)) return
        await removeWorker(worker.id)
    }

    const handleOpenDelete = worker => {
        setDeletingWorker(worker)
        setDeleteDialogOpen(true)
    }

    if (loading) {
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
                        {workers.length} total workers
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

            {/* Empty state */}
            {!error && workers.length === 0 && (
                <div className="flex flex-col items-center justify-center h-64 border rounded-lg">
                    <p className="text-muted-foreground">No workers yet</p>
                    <Button variant="outline" className="mt-4" onClick={handleOpenCreate}>
                        Add your first worker
                    </Button>
                </div>
            )}

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
                                <TableHead className="text-right">Actions</TableHead>
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
                                        <Badge variant={worker.is_active ? 'default' : 'secondary'}>
                                            {worker.is_active ? 'Active' : 'Inactive'}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <div className="flex justify-end gap-2">
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => handleOpenEdit(worker)}
                                            >
                                                <Pencil size={14} className="mr-1" />
                                                Edit
                                            </Button>
                                            {isDepartmentHead && (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => handleOpenRoleEdit(worker)}
                                                >
                                                    <Shield size={14} className="mr-1" />
                                                    Roles
                                                </Button>
                                            )}
                                            {isAdmin && !worker.has_account && (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => handleOpenCreateAccount(worker)}
                                                >
                                                    <KeyRound size={14} className="mr-1" />
                                                    Create Account
                                                </Button>
                                            )}
                                            {worker.is_active && (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => handleDeactivate(worker)}
                                                    className="text-destructive hover:text-destructive"
                                                >
                                                    <UserX size={14} className="mr-1" />
                                                    Deactivate
                                                </Button>
                                            )}
                                            {/* Only offered once a worker is deactivated, so
                                                removal is always a deliberate second step. */}
                                            {isDepartmentHead && !worker.is_active && (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => handleOpenDelete(worker)}
                                                    className="text-destructive hover:text-destructive"
                                                >
                                                    <Trash2 size={14} className="mr-1" />
                                                    Delete
                                                </Button>
                                            )}
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
                                <DropdownMenu>
                                    <DropdownMenuTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="-mr-2 shrink-0"
                                            aria-label={`Actions for ${worker.first_name} ${worker.last_name}`}
                                        >
                                            <MoreVertical size={18} />
                                        </Button>
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="end">
                                        <DropdownMenuItem onClick={() => handleOpenEdit(worker)}>
                                            <Pencil size={14} className="mr-2" />
                                            Edit
                                        </DropdownMenuItem>
                                        {isDepartmentHead && (
                                            <DropdownMenuItem
                                                onClick={() => handleOpenRoleEdit(worker)}
                                            >
                                                <Shield size={14} className="mr-2" />
                                                Roles
                                            </DropdownMenuItem>
                                        )}
                                        {isAdmin && !worker.has_account && (
                                            <DropdownMenuItem
                                                onClick={() => handleOpenCreateAccount(worker)}
                                            >
                                                <KeyRound size={14} className="mr-2" />
                                                Create account
                                            </DropdownMenuItem>
                                        )}
                                        {worker.is_active && (
                                            <DropdownMenuItem
                                                onClick={() => handleDeactivate(worker)}
                                                className="text-destructive focus:text-destructive"
                                            >
                                                <UserX size={14} className="mr-2" />
                                                Deactivate
                                            </DropdownMenuItem>
                                        )}
                                        {isDepartmentHead && !worker.is_active && (
                                            <DropdownMenuItem
                                                onClick={() => handleOpenDelete(worker)}
                                                className="text-destructive focus:text-destructive"
                                            >
                                                <Trash2 size={14} className="mr-2" />
                                                Delete
                                            </DropdownMenuItem>
                                        )}
                                    </DropdownMenuContent>
                                </DropdownMenu>
                            </div>
                            <div className="mt-3 flex flex-wrap items-center gap-2">
                                <Badge variant={worker.is_active ? 'default' : 'secondary'}>
                                    {worker.is_active ? 'Active' : 'Inactive'}
                                </Badge>
                                {isAdmin && <RoleBadges roles={worker.roles} />}
                            </div>
                        </li>
                    ))}
                </ul>
            )}

            {/* Create / Edit dialog */}
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>{editingWorker ? 'Edit Worker' : 'Add Worker'}</DialogTitle>
                    </DialogHeader>
                    <WorkerForm
                        initial={editingWorker ?? undefined}
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
                    onDeleted={destroyWorker}
                />
            )}
        </div>
    )
}
