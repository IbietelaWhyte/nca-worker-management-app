import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useDepartmentDetail } from '@/hooks/useDepartmentDetail'
import { useWorkers } from '@/hooks/useWorkers'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert } from '@/components/ui/alert'
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ArrowLeft, UserPlus, UserMinus, Crown } from 'lucide-react'

export default function DepartmentDetailPage() {
    const { id } = useParams()
    const navigate = useNavigate()
    const { department, loading, error, addMember, removeMember, assignHod } =
        useDepartmentDetail(id)
    const { workers } = useWorkers()

    const [addMemberOpen, setAddMemberOpen] = useState(false)
    const [actionLoading, setActionLoading] = useState(null)

    // Workers not already in this department
    const memberIds = new Set(department?.workers?.map(w => w.id) ?? [])
    const availableWorkers = workers.filter(w => !memberIds.has(w.id) && w.is_active)

    const handleAddMember = async workerId => {
        setActionLoading(workerId)
        try {
            await addMember(workerId)
            setAddMemberOpen(false)
        } finally {
            setActionLoading(null)
        }
    }

    const handleRemoveMember = async worker => {
        if (!confirm(`Remove ${worker.first_name} ${worker.last_name} from this department?`))
            return
        setActionLoading(worker.id)
        try {
            await removeMember(worker.id)
        } finally {
            setActionLoading(null)
        }
    }

    const handleAssignHod = async worker => {
        if (!confirm(`Set ${worker.first_name} ${worker.last_name} as Head of Department?`)) return
        setActionLoading(worker.id)
        try {
            await assignHod(worker.id)
        } finally {
            setActionLoading(null)
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <p className="text-muted-foreground">Loading department...</p>
            </div>
        )
    }

    if (error) {
        return (
            <div className="space-y-4">
                <Button variant="outline" onClick={() => navigate('/departments')}>
                    <ArrowLeft size={16} className="mr-2" />
                    Back
                </Button>
                <Alert variant="destructive">
                    <p className="text-sm">{error}</p>
                </Alert>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Button variant="outline" size="sm" onClick={() => navigate('/departments')}>
                    <ArrowLeft size={16} className="mr-2" />
                    Back
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

            {/* Members section */}
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold">
                        Members
                        <span className="text-muted-foreground text-sm font-normal ml-2">
                            {department.workers?.length ?? 0} workers
                        </span>
                    </h3>
                    <Button size="sm" onClick={() => setAddMemberOpen(true)}>
                        <UserPlus size={16} className="mr-2" />
                        Add Member
                    </Button>
                </div>

                {!department.workers || department.workers.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-40 border rounded-lg">
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
                                                            <Crown size={10} className="mr-1" />
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
                                                    {!isHod && (
                                                        <Button
                                                            variant="outline"
                                                            size="sm"
                                                            disabled={actionLoading === worker.id}
                                                            onClick={() => handleAssignHod(worker)}
                                                        >
                                                            <Crown size={14} className="mr-1" />
                                                            Set HOD
                                                        </Button>
                                                    )}
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        disabled={actionLoading === worker.id}
                                                        onClick={() => handleRemoveMember(worker)}
                                                        className="text-destructive hover:text-destructive"
                                                    >
                                                        <UserMinus size={14} className="mr-1" />
                                                        Remove
                                                    </Button>
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
                                        disabled={actionLoading === worker.id}
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
        </div>
    )
}
