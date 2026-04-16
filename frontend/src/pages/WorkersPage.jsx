import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWorkers } from '@/hooks/useWorkers'
import { useAuth } from '@/context/AuthContext'
import WorkerForm from '@/components/workers/WorkerForm'
import RoleEditor from '@/components/workers/RoleEditor'
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
import { Plus, Pencil, UserX, UserPlus, Shield } from 'lucide-react'

export default function WorkersPage() {
    const navigate = useNavigate()
    const { isAdmin } = useAuth()
    const { workers, loading, error, addWorker, editWorker, removeWorker, refetch } = useWorkers()

    const [dialogOpen, setDialogOpen] = useState(false)
    const [editingWorker, setEditingWorker] = useState(null)
    const [roleDialogOpen, setRoleDialogOpen] = useState(false)
    const [editingRoles, setEditingRoles] = useState(null)

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
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold">Workers</h2>
                    <p className="text-muted-foreground text-sm mt-1">
                        {workers.length} total workers
                    </p>
                </div>
                <div className="flex gap-2">
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

            {/* Workers table */}
            {workers.length > 0 && (
                <div className="border rounded-lg overflow-hidden">
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
                                            {worker.roles && worker.roles.length > 0 ? (
                                                <div className="flex gap-1 flex-wrap">
                                                    {worker.roles.map(role => (
                                                        <Badge
                                                            key={role}
                                                            variant={
                                                                role === 'admin'
                                                                    ? 'destructive'
                                                                    : role === 'hod'
                                                                      ? 'default'
                                                                      : 'secondary'
                                                            }
                                                            className="text-xs"
                                                        >
                                                            {role === 'hod'
                                                                ? 'HOD'
                                                                : role.charAt(0).toUpperCase() +
                                                                  role.slice(1)}
                                                        </Badge>
                                                    ))}
                                                </div>
                                            ) : (
                                                <span className="text-xs text-muted-foreground">
                                                    —
                                                </span>
                                            )}
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
                                            {isAdmin && worker.roles && worker.roles.length > 0 && (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => handleOpenRoleEdit(worker)}
                                                >
                                                    <Shield size={14} className="mr-1" />
                                                    Roles
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
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
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
                                onClose={handleCloseRoleDialog}
                                onSuccess={handleRoleUpdateSuccess}
                            />
                        )}
                    </DialogContent>
                </Dialog>
            )}
        </div>
    )
}
