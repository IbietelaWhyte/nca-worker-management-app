import { Fragment, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useDepartmentDetail } from '@/hooks/useDepartmentDetail'
import { useWorkers } from '@/hooks/useWorkers'
import { useSubteams } from '@/hooks/useSubteams'
import { useRoles } from '@/hooks/useRoles'
import { useAuth } from '@/context/AuthContext'
import SubteamForm from '@/components/subteams/SubteamForm'
import RoleForm from '@/components/roles/RoleForm'
import CsvImportDialog from '@/components/departments/CsvImportDialog'
import {
    getSubteamWithWorkers,
    assignWorkerToSubteam,
    unassignWorkerFromSubteam,
} from '@/api/subteams'
import { assignWorkerRole, unassignWorkerRole } from '@/api/roles'
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
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
    ArrowLeft,
    UserPlus,
    UserMinus,
    Crown,
    Plus,
    Pencil,
    Trash2,
    Users,
    ChevronRight,
    ChevronDown,
    Upload,
} from 'lucide-react'

// Radix Select disallows an empty-string value, so use a sentinel for "no role".
const NO_ROLE = '__none__'

export default function DepartmentDetailPage() {
    const { id } = useParams()
    const navigate = useNavigate()
    const { isAdmin, isDepartmentHead, role } = useAuth()

    // Members
    const {
        department,
        loading: deptLoading,
        error: deptError,
        addMember,
        removeMember,
        assignHod,
        refetch,
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

    // Roles
    const { roles, loading: rolesLoading, addRole, editRole, removeRole } = useRoles(id)

    // Member dialog state
    const [addMemberOpen, setAddMemberOpen] = useState(false)
    const [csvImportOpen, setCsvImportOpen] = useState(false)
    const [memberActionLoading, setMemberActionLoading] = useState(null)

    // Subteam dialog state
    const [subteamDialogOpen, setSubteamDialogOpen] = useState(false)
    const [editingSubteam, setEditingSubteam] = useState(null)
    const [subteamActionLoading, setSubteamActionLoading] = useState(null)

    // Subteam worker management state
    const [expandedSubteamId, setExpandedSubteamId] = useState(null)
    const [subteamWorkers, setSubteamWorkers] = useState([])
    const [loadingSubteamWorkers, setLoadingSubteamWorkers] = useState(false)
    const [addSubteamMemberOpen, setAddSubteamMemberOpen] = useState(false)
    const [selectedSubteam, setSelectedSubteam] = useState(null)
    const [subteamMemberActionLoading, setSubteamMemberActionLoading] = useState(null)

    // Role dialog + inline assignment state
    const [roleDialogOpen, setRoleDialogOpen] = useState(false)
    const [editingRole, setEditingRole] = useState(null)
    const [roleActionLoading, setRoleActionLoading] = useState(null)
    const [memberRoleLoading, setMemberRoleLoading] = useState(null)

    const canManage = isAdmin || isDepartmentHead

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

    // Subteam worker handlers
    const handleToggleSubteamExpansion = async subteamId => {
        if (expandedSubteamId === subteamId) {
            // Collapse
            setExpandedSubteamId(null)
            setSubteamWorkers([])
        } else {
            // Expand and fetch workers
            setExpandedSubteamId(subteamId)
            setLoadingSubteamWorkers(true)
            try {
                const response = await getSubteamWithWorkers(subteamId)
                setSubteamWorkers(response.data || [])
            } catch (error) {
                console.error('Failed to load subteam workers:', error)
                setSubteamWorkers([])
            } finally {
                setLoadingSubteamWorkers(false)
            }
        }
    }

    const handleOpenAddSubteamMember = subteam => {
        setSelectedSubteam(subteam)
        setAddSubteamMemberOpen(true)
    }

    const handleAddSubteamMember = async workerId => {
        if (!selectedSubteam) return
        setSubteamMemberActionLoading(workerId)
        try {
            await assignWorkerToSubteam(selectedSubteam.id, workerId)
            // Refresh subteam workers list
            const response = await getSubteamWithWorkers(selectedSubteam.id)
            setSubteamWorkers(response.data || [])
            setAddSubteamMemberOpen(false)
        } catch (error) {
            console.error('Failed to add worker to subteam:', error)
            alert(error.response?.data?.detail || 'Failed to add worker to subteam')
        } finally {
            setSubteamMemberActionLoading(null)
        }
    }

    const handleRemoveSubteamMember = async worker => {
        if (!selectedSubteam) return
        if (
            !confirm(
                `Remove ${worker.first_name} ${worker.last_name} from subteam "${selectedSubteam.name}"?`
            )
        )
            return
        setSubteamMemberActionLoading(worker.id)
        try {
            await unassignWorkerFromSubteam(selectedSubteam.id, worker.id)
            // Refresh subteam workers list
            const response = await getSubteamWithWorkers(selectedSubteam.id)
            setSubteamWorkers(response.data || [])
        } catch (error) {
            console.error('Failed to remove worker from subteam:', error)
            alert(error.response?.data?.detail || 'Failed to remove worker from subteam')
        } finally {
            setSubteamMemberActionLoading(null)
        }
    }

    // Role handlers
    const handleOpenCreateRole = () => {
        setEditingRole(null)
        setRoleDialogOpen(true)
    }

    const handleOpenEditRole = roleToEdit => {
        setEditingRole(roleToEdit)
        setRoleDialogOpen(true)
    }

    const handleRoleSubmit = async formData => {
        if (editingRole) {
            await editRole(editingRole.id, formData)
        } else {
            await addRole(formData)
        }
        setRoleDialogOpen(false)
        setEditingRole(null)
    }

    const handleDeleteRole = async roleToDelete => {
        if (!confirm(`Delete role "${roleToDelete.name}"? This cannot be undone.`)) return
        setRoleActionLoading(roleToDelete.id)
        try {
            await removeRole(roleToDelete.id)
        } finally {
            setRoleActionLoading(null)
        }
    }

    // Set or clear a member's standing department role from the Members tab.
    const handleMemberRoleChange = async (worker, value) => {
        setMemberRoleLoading(worker.id)
        try {
            if (value === NO_ROLE) {
                if (worker.department_role) {
                    await unassignWorkerRole(worker.department_role.id, worker.id)
                }
            } else {
                await assignWorkerRole(value, worker.id)
            }
            await refetch()
        } catch (error) {
            console.error('Failed to update member role:', error)
            alert(error.response?.data?.detail || 'Failed to update role')
        } finally {
            setMemberRoleLoading(null)
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
                    <TabsTrigger value="roles">
                        Roles
                        {roles.length > 0 && (
                            <Badge variant="secondary" className="ml-2 text-xs">
                                {roles.length}
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
                            <div className="flex items-center gap-2">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setCsvImportOpen(true)}
                                >
                                    <Upload size={16} className="mr-2" /> Import CSV
                                </Button>
                                <Button size="sm" onClick={() => setAddMemberOpen(true)}>
                                    <UserPlus size={16} className="mr-2" /> Add Member
                                </Button>
                            </div>
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
                                                    <TableCell>
                                                        {canManage ? (
                                                            <Select
                                                                value={
                                                                    worker.department_role?.id ??
                                                                    NO_ROLE
                                                                }
                                                                onValueChange={value =>
                                                                    handleMemberRoleChange(
                                                                        worker,
                                                                        value
                                                                    )
                                                                }
                                                                disabled={
                                                                    memberRoleLoading ===
                                                                        worker.id ||
                                                                    roles.length === 0
                                                                }
                                                            >
                                                                <SelectTrigger
                                                                    size="sm"
                                                                    className="w-40"
                                                                >
                                                                    <SelectValue
                                                                        placeholder={
                                                                            roles.length === 0
                                                                                ? 'No roles defined'
                                                                                : 'No role'
                                                                        }
                                                                    />
                                                                </SelectTrigger>
                                                                <SelectContent>
                                                                    <SelectItem value={NO_ROLE}>
                                                                        No role
                                                                    </SelectItem>
                                                                    {roles.map(r => (
                                                                        <SelectItem
                                                                            key={r.id}
                                                                            value={r.id}
                                                                        >
                                                                            {r.name}
                                                                        </SelectItem>
                                                                    ))}
                                                                </SelectContent>
                                                            </Select>
                                                        ) : worker.department_role ? (
                                                            <Badge
                                                                variant="secondary"
                                                                className="text-xs"
                                                            >
                                                                {worker.department_role.name}
                                                            </Badge>
                                                        ) : (
                                                            <span className="text-muted-foreground">
                                                                —
                                                            </span>
                                                        )}
                                                    </TableCell>
                                                    <TableCell className="text-right">
                                                        <div className="flex justify-end gap-2">
                                                            {!isHod &&
                                                                (isAdmin || role === 'hod') && (
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
                                            <TableHead className="w-8"></TableHead>
                                            <TableHead>Name</TableHead>
                                            <TableHead>Description</TableHead>
                                            <TableHead>Workers/Slot</TableHead>
                                            <TableHead>Members</TableHead>
                                            {(isAdmin || isDepartmentHead) && (
                                                <TableHead className="text-right">
                                                    Actions
                                                </TableHead>
                                            )}
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {subteams.map(subteam => {
                                            const isExpanded = expandedSubteamId === subteam.id
                                            const workerCount =
                                                isExpanded && !loadingSubteamWorkers
                                                    ? subteamWorkers.filter(w => w.worker).length
                                                    : '—'

                                            return (
                                                <Fragment key={subteam.id}>
                                                    <TableRow
                                                        className="cursor-pointer hover:bg-accent/50"
                                                        onClick={() => {
                                                            handleToggleSubteamExpansion(subteam.id)
                                                            setSelectedSubteam(subteam)
                                                        }}
                                                    >
                                                        <TableCell>
                                                            {isExpanded ? (
                                                                <ChevronDown size={16} />
                                                            ) : (
                                                                <ChevronRight size={16} />
                                                            )}
                                                        </TableCell>
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
                                                        <TableCell>
                                                            <span className="text-sm text-muted-foreground">
                                                                {loadingSubteamWorkers && isExpanded
                                                                    ? 'Loading...'
                                                                    : isExpanded
                                                                      ? `${workerCount} ${workerCount === 1 ? 'worker' : 'workers'}`
                                                                      : 'Click to view'}
                                                            </span>
                                                        </TableCell>
                                                        {(isAdmin || isDepartmentHead) && (
                                                            <TableCell
                                                                className="text-right"
                                                                onClick={e => e.stopPropagation()}
                                                            >
                                                                <div className="flex justify-end gap-2">
                                                                    <Button
                                                                        variant="outline"
                                                                        size="sm"
                                                                        onClick={() => {
                                                                            handleOpenAddSubteamMember(
                                                                                subteam
                                                                            )
                                                                        }}
                                                                    >
                                                                        <UserPlus
                                                                            size={14}
                                                                            className="mr-1"
                                                                        />{' '}
                                                                        Add Member
                                                                    </Button>
                                                                    <Button
                                                                        variant="outline"
                                                                        size="sm"
                                                                        onClick={() =>
                                                                            handleOpenEditSubteam(
                                                                                subteam
                                                                            )
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
                                                                                handleDeleteSubteam(
                                                                                    subteam
                                                                                )
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

                                                    {/* Expanded row showing workers */}
                                                    {isExpanded && (
                                                        <TableRow>
                                                            <TableCell colSpan={6} className="p-0">
                                                                <div className="bg-muted/30 p-4 border-t">
                                                                    {loadingSubteamWorkers ? (
                                                                        <div className="flex items-center justify-center py-8">
                                                                            <p className="text-sm text-muted-foreground">
                                                                                Loading workers...
                                                                            </p>
                                                                        </div>
                                                                    ) : subteamWorkers.filter(
                                                                          w => w.worker
                                                                      ).length === 0 ? (
                                                                        <div className="flex flex-col items-center justify-center py-8">
                                                                            <p className="text-sm text-muted-foreground">
                                                                                No workers assigned
                                                                                to this subteam yet
                                                                            </p>
                                                                            {(isAdmin ||
                                                                                isDepartmentHead) && (
                                                                                <Button
                                                                                    variant="outline"
                                                                                    size="sm"
                                                                                    className="mt-3"
                                                                                    onClick={() =>
                                                                                        handleOpenAddSubteamMember(
                                                                                            subteam
                                                                                        )
                                                                                    }
                                                                                >
                                                                                    <UserPlus
                                                                                        size={14}
                                                                                        className="mr-2"
                                                                                    />
                                                                                    Add first worker
                                                                                </Button>
                                                                            )}
                                                                        </div>
                                                                    ) : (
                                                                        <div className="space-y-2">
                                                                            <p className="text-sm font-medium mb-3">
                                                                                Subteam Members
                                                                            </p>
                                                                            <div className="bg-background border rounded-lg overflow-hidden">
                                                                                <Table>
                                                                                    <TableHeader>
                                                                                        <TableRow>
                                                                                            <TableHead>
                                                                                                Name
                                                                                            </TableHead>
                                                                                            <TableHead>
                                                                                                Email
                                                                                            </TableHead>
                                                                                            {(isAdmin ||
                                                                                                isDepartmentHead) && (
                                                                                                <TableHead className="text-right">
                                                                                                    Actions
                                                                                                </TableHead>
                                                                                            )}
                                                                                        </TableRow>
                                                                                    </TableHeader>
                                                                                    <TableBody>
                                                                                        {subteamWorkers
                                                                                            .filter(
                                                                                                w =>
                                                                                                    w.worker
                                                                                            )
                                                                                            .map(
                                                                                                ({
                                                                                                    worker,
                                                                                                }) => (
                                                                                                    <TableRow
                                                                                                        key={
                                                                                                            worker.id
                                                                                                        }
                                                                                                    >
                                                                                                        <TableCell>
                                                                                                            {
                                                                                                                worker.first_name
                                                                                                            }{' '}
                                                                                                            {
                                                                                                                worker.last_name
                                                                                                            }
                                                                                                        </TableCell>
                                                                                                        <TableCell className="text-muted-foreground text-sm">
                                                                                                            {
                                                                                                                worker.email
                                                                                                            }
                                                                                                        </TableCell>
                                                                                                        {(isAdmin ||
                                                                                                            isDepartmentHead) && (
                                                                                                            <TableCell className="text-right">
                                                                                                                <Button
                                                                                                                    variant="outline"
                                                                                                                    size="sm"
                                                                                                                    disabled={
                                                                                                                        subteamMemberActionLoading ===
                                                                                                                        worker.id
                                                                                                                    }
                                                                                                                    onClick={() =>
                                                                                                                        handleRemoveSubteamMember(
                                                                                                                            worker
                                                                                                                        )
                                                                                                                    }
                                                                                                                    className="text-destructive hover:text-destructive"
                                                                                                                >
                                                                                                                    <UserMinus
                                                                                                                        size={
                                                                                                                            14
                                                                                                                        }
                                                                                                                        className="mr-1"
                                                                                                                    />
                                                                                                                    Remove
                                                                                                                </Button>
                                                                                                            </TableCell>
                                                                                                        )}
                                                                                                    </TableRow>
                                                                                                )
                                                                                            )}
                                                                                    </TableBody>
                                                                                </Table>
                                                                            </div>
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            </TableCell>
                                                        </TableRow>
                                                    )}
                                                </Fragment>
                                            )
                                        })}
                                    </TableBody>
                                </Table>
                            </div>
                        )}
                    </div>
                </TabsContent>

                {/* Roles tab */}
                <TabsContent value="roles" className="mt-4">
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <p className="text-sm text-muted-foreground">
                                Define functional roles (e.g. Teacher, Helper) and assign them to
                                members on the Members tab
                            </p>
                            {canManage && (
                                <Button size="sm" onClick={handleOpenCreateRole}>
                                    <Plus size={16} className="mr-2" /> Add Role
                                </Button>
                            )}
                        </div>

                        {rolesLoading && (
                            <div className="flex items-center justify-center h-32">
                                <p className="text-muted-foreground text-sm">Loading roles...</p>
                            </div>
                        )}

                        {!rolesLoading && roles.length === 0 && (
                            <div className="flex flex-col items-center justify-center h-40 border rounded-lg">
                                <p className="text-muted-foreground text-sm">No roles yet</p>
                                {canManage && (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        className="mt-3"
                                        onClick={handleOpenCreateRole}
                                    >
                                        Add first role
                                    </Button>
                                )}
                            </div>
                        )}

                        {!rolesLoading && roles.length > 0 && (
                            <div className="border rounded-lg overflow-hidden">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Name</TableHead>
                                            <TableHead>Description</TableHead>
                                            {canManage && (
                                                <TableHead className="text-right">
                                                    Actions
                                                </TableHead>
                                            )}
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {roles.map(roleItem => (
                                            <TableRow key={roleItem.id}>
                                                <TableCell className="font-medium">
                                                    {roleItem.name}
                                                </TableCell>
                                                <TableCell className="text-muted-foreground">
                                                    {roleItem.description ?? '—'}
                                                </TableCell>
                                                {canManage && (
                                                    <TableCell className="text-right">
                                                        <div className="flex justify-end gap-2">
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                onClick={() =>
                                                                    handleOpenEditRole(roleItem)
                                                                }
                                                            >
                                                                <Pencil
                                                                    size={14}
                                                                    className="mr-1"
                                                                />{' '}
                                                                Edit
                                                            </Button>
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                disabled={
                                                                    roleActionLoading ===
                                                                    roleItem.id
                                                                }
                                                                onClick={() =>
                                                                    handleDeleteRole(roleItem)
                                                                }
                                                                className="text-destructive hover:text-destructive"
                                                            >
                                                                <Trash2
                                                                    size={14}
                                                                    className="mr-1"
                                                                />{' '}
                                                                Delete
                                                            </Button>
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

            {/* CSV import dialog */}
            <CsvImportDialog
                open={csvImportOpen}
                onOpenChange={setCsvImportOpen}
                departmentId={id}
                onImported={refetch}
            />

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

            {/* Add worker to subteam dialog */}
            <Dialog open={addSubteamMemberOpen} onOpenChange={setAddSubteamMemberOpen}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>
                            Add Member to {selectedSubteam?.name ?? 'Subteam'}
                        </DialogTitle>
                        <p className="text-sm text-muted-foreground mt-2">
                            Only showing members of {department?.name ?? 'this department'}
                        </p>
                    </DialogHeader>
                    {(() => {
                        // Get workers already in this subteam
                        const subteamWorkerIds = new Set(
                            subteamWorkers.filter(w => w.worker).map(w => w.worker.id)
                        )
                        // Filter to department members not in subteam
                        const availableSubteamWorkers = (department?.workers ?? []).filter(
                            w => !subteamWorkerIds.has(w.id)
                        )

                        if (availableSubteamWorkers.length === 0) {
                            return (
                                <p className="text-sm text-muted-foreground py-4 text-center">
                                    All department members are already assigned to this subteam.
                                </p>
                            )
                        }

                        return (
                            <div className="space-y-2 max-h-80 overflow-y-auto">
                                {availableSubteamWorkers.map(worker => (
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
                                            disabled={subteamMemberActionLoading === worker.id}
                                            onClick={() => handleAddSubteamMember(worker.id)}
                                        >
                                            Add
                                        </Button>
                                    </div>
                                ))}
                            </div>
                        )
                    })()}
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

            {/* Create / Edit role dialog */}
            <Dialog open={roleDialogOpen} onOpenChange={setRoleDialogOpen}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>{editingRole ? 'Edit Role' : 'Add Role'}</DialogTitle>
                    </DialogHeader>
                    <RoleForm
                        initial={editingRole ?? undefined}
                        onSubmit={handleRoleSubmit}
                        onCancel={() => {
                            setRoleDialogOpen(false)
                            setEditingRole(null)
                        }}
                    />
                </DialogContent>
            </Dialog>
        </div>
    )
}
