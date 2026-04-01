import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useDepartmentDetail } from '@/hooks/useDepartmentDetail'
import { useWorkers } from '@/hooks/useWorkers'
import { useSubteams } from '@/hooks/useSubteams'
import { useAuth } from '@/context/AuthContext'
import SubteamForm from '@/components/subteams/SubteamForm'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert } from '@/components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ArrowLeft, UserPlus, UserMinus, Crown, Plus, Pencil, Trash2, Users } from 'lucide-react'

export default function DepartmentDetailPage() {
    const { id } = useParams()
    const navigate = useNavigate()
    const { isAdmin, isDepartmentHead } = useAuth()

    // Members
    const {
        department,
        loading: deptLoading,
        error: deptError,
        addMember,
        removeMember,
        assignHod,
    } = useDepartmentDetail(id)
    const { workers } = useWorkers()

    // Subteams
    const {
        subteams,
        loading: subteamsLoading,
        addSubteam,
        editSubteam,
        removeSubteam,
    } = useSubteams(id)

    // Member dialog state
    const [addMemberOpen, setAddMemberOpen] = useState(false)
    const [memberActionLoading, setMemberActionLoading] = useState(null)

    // Subteam dialog state
    const [subteamDialogOpen, setSubteamDialogOpen] = useState(false)
    const [editingSubteam, setEditingSubteam] = useState(null)
    const [subteamActionLoading, setSubteamActionLoading] = useState(null)

    // Workers not already in this department
    const memberIds = new Set(department?.workers?.map(w => w.id) ?? [])
    const availableWorkers = workers.filter(w => !memberIds.has(w.id) && w.is_active)

    // Member handlers
    const handleAddMember = async workerId => {
        setMemberActionLoading(workerId)
        try {
            await addMember(workerId)
            setAddMemberOpen(false)
        } finally {
            setMemberActionLoading(null)
        }
    }

    const handleRemoveMember = async worker => {
        if (!confirm(`Remove ${worker.first_name} ${worker.last_name} from this department?`))
            return
        setMemberActionLoading(worker.id)
        try {
            await removeMember(worker.id)
        } finally {
            setMemberActionLoading(null)
        }
    }

    const handleAssignHod = async worker => {
        if (!confirm(`Set ${worker.first_name} ${worker.last_name} as Head of Department?`)) return
        setMemberActionLoading(worker.id)
        try {
            await assignHod(worker.id)
        } finally {
            setMemberActionLoading(null)
        }
    }

    // Subteam handlers
    const handleOpenCreateSubteam = () => {
        setEditingSubteam(null)
        setSubteamDialogOpen(true)
    }

    const handleOpenEditSubteam = subteam => {
        setEditingSubteam(subteam)
        setSubteamDialogOpen(true)
    }

    const handleSubteamSubmit = async formData => {
        if (editingSubteam) {
            await editSubteam(editingSubteam.id, formData)
        } else {
            await addSubteam(formData)
        }
        setSubteamDialogOpen(false)
        setEditingSubteam(null)
    }

    const handleDeleteSubteam = async subteam => {
        if (!confirm(`Delete subteam "${subteam.name}"? This cannot be undone.`)) return
        setSubteamActionLoading(subteam.id)
        try {
            await removeSubteam(subteam.id)
        } finally {
            setSubteamActionLoading(null)
        }
    }

    if (deptLoading) {
        return (
            <div className="flex items-center justify-center h-64">
                <p className="text-muted-foreground">Loading department...</p>
            </div>
        )
    }

    if (deptError) {
        return (
            <div className="space-y-4">
                <Button variant="outline" onClick={() => navigate('/departments')}>
                    <ArrowLeft size={16} className="mr-2" /> Back
                </Button>
                <Alert variant="destructive">
                    <p className="text-sm">{deptError}</p>
                </Alert>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Button variant="outline" size="sm" onClick={() => navigate('/departments')}>
                    <ArrowLeft size={16} className="mr-2" /> Back
                </Button>
                <div>
                    <h2 className="text-2xl font-bold">{department.name}</h2>
                    {department.description && (
                        <p className="text-muted-foreground text-sm mt-1">
                            {department.description}
                        </p>
                    )}
                </div>
            </div>

            {/* Tabs */}
            <Tabs defaultValue="members">
                <TabsList>
                    <TabsTrigger value="members">
                        Members
                        <Badge variant="secondary" className="ml-2 text-xs">
                            {department.workers?.length ?? 0}
                        </Badge>
                    </TabsTrigger>
                    <TabsTrigger value="subteams">
                        Subteams
                        {subteams.length > 0 && (
                            <Badge variant="secondary" className="ml-2 text-xs">
                                {subteams.length}
                            </Badge>
                        )}
                    </TabsTrigger>
                </TabsList>

                {/* Members tab */}
                <TabsContent value="members" className="mt-4">
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <p className="text-sm text-muted-foreground">
                                {department.workers?.length ?? 0} workers in this department
                            </p>
                            <Button size="sm" onClick={() => setAddMemberOpen(true)}>
                                <UserPlus size={16} className="mr-2" /> Add Member
                            </Button>
                        </div>

                        {!department.workers || department.workers.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-40 border rounded-lg">
                                <Users size={24} className="text-muted-foreground mb-2" />
                                <p className="text-muted-foreground text-sm">No members yet</p>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="mt-3"
                                    onClick={() => setAddMemberOpen(true)}
                                >
                                    Add first member
                                </Button>
                            </div>
                        ) : (
                            <div className="border rounded-lg overflow-hidden">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Name</TableHead>
                                            <TableHead>Email</TableHead>
                                            <TableHead>Role</TableHead>
                                            <TableHead className="text-right">Actions</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {department.workers.map(worker => {
                                            const isHod = worker.id === department.hod_id
                                            return (
                                                <TableRow key={worker.id}>
                                                    <TableCell className="font-medium">
                                                        <div className="flex items-center gap-2">
                                                            {worker.first_name} {worker.last_name}
                                                            {isHod && (
                                                                <Badge
                                                                    variant="default"
                                                                    className="text-xs"
                                                                >
                                                                    <Crown
                                                                        size={10}
                                                                        className="mr-1"
                                                                    />{' '}
                                                                    HOD
                                                                </Badge>
                                                            )}
                                                        </div>
                                                    </TableCell>
                                                    <TableCell>{worker.email}</TableCell>
                                                    <TableCell className="text-muted-foreground">
                                                        {isHod ? 'Head of Department' : 'Member'}
                                                    </TableCell>
                                                    <TableCell className="text-right">
                                                        <div className="flex justify-end gap-2">
                                                            {!isHod &&
                                                                (isAdmin || isDepartmentHead) && (
                                                                    <Button
                                                                        variant="outline"
                                                                        size="sm"
                                                                        disabled={
                                                                            memberActionLoading ===
                                                                            worker.id
                                                                        }
                                                                        onClick={() =>
                                                                            handleAssignHod(worker)
                                                                        }
                                                                    >
                                                                        <Crown
                                                                            size={14}
                                                                            className="mr-1"
                                                                        />{' '}
                                                                        Set HOD
                                                                    </Button>
                                                                )}
                                                            {(isAdmin || isDepartmentHead) && (
                                                                <Button
                                                                    variant="outline"
                                                                    size="sm"
                                                                    disabled={
                                                                        memberActionLoading ===
                                                                        worker.id
                                                                    }
                                                                    onClick={() =>
                                                                        handleRemoveMember(worker)
                                                                    }
                                                                    className="text-destructive hover:text-destructive"
                                                                >
                                                                    <UserMinus
                                                                        size={14}
                                                                        className="mr-1"
                                                                    />{' '}
                                                                    Remove
                                                                </Button>
                                                            )}
                                                        </div>
                                                    </TableCell>
                                                </TableRow>
                                            )
                                        })}
                                    </TableBody>
                                </Table>
                            </div>
                        )}
                    </div>
                </TabsContent>

                {/* Subteams tab */}
                <TabsContent value="subteams" className="mt-4">
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <p className="text-sm text-muted-foreground">
                                Subteams allow finer-grained scheduling within this department
                            </p>
                            {(isAdmin || isDepartmentHead) && (
                                <Button size="sm" onClick={handleOpenCreateSubteam}>
                                    <Plus size={16} className="mr-2" /> Add Subteam
                                </Button>
                            )}
                        </div>

                        {subteamsLoading && (
                            <div className="flex items-center justify-center h-32">
                                <p className="text-muted-foreground text-sm">Loading subteams...</p>
                            </div>
                        )}

                        {!subteamsLoading && subteams.length === 0 && (
                            <div className="flex flex-col items-center justify-center h-40 border rounded-lg">
                                <p className="text-muted-foreground text-sm">No subteams yet</p>
                                {(isAdmin || isDepartmentHead) && (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        className="mt-3"
                                        onClick={handleOpenCreateSubteam}
                                    >
                                        Add first subteam
                                    </Button>
                                )}
                            </div>
                        )}

                        {!subteamsLoading && subteams.length > 0 && (
                            <div className="border rounded-lg overflow-hidden">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Name</TableHead>
                                            <TableHead>Description</TableHead>
                                            <TableHead>Workers/Slot</TableHead>
                                            {(isAdmin || isDepartmentHead) && (
                                                <TableHead className="text-right">
                                                    Actions
                                                </TableHead>
                                            )}
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {subteams.map(subteam => (
                                            <TableRow key={subteam.id}>
                                                <TableCell className="font-medium">
                                                    {subteam.name}
                                                </TableCell>
                                                <TableCell className="text-muted-foreground">
                                                    {subteam.description ?? '—'}
                                                </TableCell>
                                                <TableCell>
                                                    {subteam.workers_per_slot ?? (
                                                        <span className="text-muted-foreground text-xs">
                                                            dept. default
                                                        </span>
                                                    )}
                                                </TableCell>
                                                {(isAdmin || isDepartmentHead) && (
                                                    <TableCell className="text-right">
                                                        <div className="flex justify-end gap-2">
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                onClick={() =>
                                                                    handleOpenEditSubteam(subteam)
                                                                }
                                                            >
                                                                <Pencil
                                                                    size={14}
                                                                    className="mr-1"
                                                                />{' '}
                                                                Edit
                                                            </Button>
                                                            {isAdmin && (
                                                                <Button
                                                                    variant="outline"
                                                                    size="sm"
                                                                    disabled={
                                                                        subteamActionLoading ===
                                                                        subteam.id
                                                                    }
                                                                    onClick={() =>
                                                                        handleDeleteSubteam(subteam)
                                                                    }
                                                                    className="text-destructive hover:text-destructive"
                                                                >
                                                                    <Trash2
                                                                        size={14}
                                                                        className="mr-1"
                                                                    />{' '}
                                                                    Delete
                                                                </Button>
                                                            )}
                                                        </div>
                                                    </TableCell>
                                                )}
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        )}
                    </div>
                </TabsContent>
            </Tabs>

            {/* Add member dialog */}
            <Dialog open={addMemberOpen} onOpenChange={setAddMemberOpen}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>Add Member</DialogTitle>
                    </DialogHeader>
                    {availableWorkers.length === 0 ? (
                        <p className="text-sm text-muted-foreground py-4 text-center">
                            All active workers are already members of this department.
                        </p>
                    ) : (
                        <div className="space-y-2 max-h-80 overflow-y-auto">
                            {availableWorkers.map(worker => (
                                <div
                                    key={worker.id}
                                    className="flex items-center justify-between p-3 border rounded-md hover:bg-accent transition-colors"
                                >
                                    <div>
                                        <p className="text-sm font-medium">
                                            {worker.first_name} {worker.last_name}
                                        </p>
                                        <p className="text-xs text-muted-foreground">
                                            {worker.email}
                                        </p>
                                    </div>
                                    <Button
                                        size="sm"
                                        disabled={memberActionLoading === worker.id}
                                        onClick={() => handleAddMember(worker.id)}
                                    >
                                        Add
                                    </Button>
                                </div>
                            ))}
                        </div>
                    )}
                </DialogContent>
            </Dialog>

            {/* Create / Edit subteam dialog */}
            <Dialog open={subteamDialogOpen} onOpenChange={setSubteamDialogOpen}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>{editingSubteam ? 'Edit Subteam' : 'Add Subteam'}</DialogTitle>
                    </DialogHeader>
                    <SubteamForm
                        initial={editingSubteam ?? undefined}
                        onSubmit={handleSubteamSubmit}
                        onCancel={() => {
                            setSubteamDialogOpen(false)
                            setEditingSubteam(null)
                        }}
                    />
                </DialogContent>
            </Dialog>
        </div>
    )
}
