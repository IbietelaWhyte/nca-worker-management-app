import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { CheckCircle, XCircle, Clock } from 'lucide-react'

const STATUS_CONFIG = {
    pending: { label: 'Pending', variant: 'secondary', icon: Clock },
    confirmed: { label: 'Confirmed', variant: 'default', icon: CheckCircle },
    declined: { label: 'Declined', variant: 'destructive', icon: XCircle },
}

// Radix Select disallows an empty-string value, so use a sentinel for "no role".
const NO_ROLE = '__none__'

export default function AssignmentsList({
    groupedAssignments = [],
    onStatusChange,
    onRoleChange,
    roles = [],
    canManage = false,
}) {
    const [loadingId, setLoadingId] = useState(null)
    const [roleLoadingId, setRoleLoadingId] = useState(null)

    const handleStatusChange = async (assignmentId, status) => {
        setLoadingId(assignmentId)
        try {
            await onStatusChange(assignmentId, status)
        } finally {
            setLoadingId(null)
        }
    }

    const handleRoleChange = async (assignmentId, value) => {
        setRoleLoadingId(assignmentId)
        try {
            await onRoleChange(assignmentId, value === NO_ROLE ? null : value)
        } finally {
            setRoleLoadingId(null)
        }
    }

    if (groupedAssignments.length === 0) {
        return (
            <p className="text-sm text-muted-foreground text-center py-8">
                No workers assigned yet.
            </p>
        )
    }

    return (
        <div className="space-y-6">
            {groupedAssignments.map(group => {
                const assignmentCount = group.assignments.length

                return (
                    <div key={group.subteamId || 'unassigned'} className="space-y-2">
                        {/* Subteam header */}
                        <h4 className="text-sm font-semibold text-muted-foreground">
                            {group.subteamName} ({assignmentCount})
                        </h4>

                        {/* Assignments in this subteam */}
                        {assignmentCount === 0 ? (
                            <p className="text-xs text-muted-foreground italic pl-4">
                                No assignments
                            </p>
                        ) : (
                            <div className="space-y-2">
                                {group.assignments.map(assignment => {
                                    const worker = assignment.workers
                                    const config =
                                        STATUS_CONFIG[assignment.status] ?? STATUS_CONFIG.pending
                                    const Icon = config.icon
                                    const isLoading = loadingId === assignment.id

                                    return (
                                        <div
                                            key={assignment.id}
                                            className="flex items-center justify-between p-3 border rounded-md"
                                        >
                                            <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-xs font-medium">
                                                    {worker
                                                        ? `${worker.first_name[0]}${worker.last_name[0]}`
                                                        : '?'}
                                                </div>
                                                <div>
                                                    <p className="text-sm font-medium">
                                                        {worker
                                                            ? `${worker.first_name} ${worker.last_name}`
                                                            : 'Unknown worker'}
                                                    </p>
                                                    {worker && (
                                                        <p className="text-xs text-muted-foreground">
                                                            {worker.email}
                                                        </p>
                                                    )}
                                                </div>
                                            </div>

                                            <div className="flex items-center gap-2">
                                                {canManage ? (
                                                    <Select
                                                        value={
                                                            assignment.department_roles?.id ??
                                                            NO_ROLE
                                                        }
                                                        onValueChange={value =>
                                                            handleRoleChange(assignment.id, value)
                                                        }
                                                        disabled={
                                                            roleLoadingId === assignment.id ||
                                                            roles.length === 0
                                                        }
                                                    >
                                                        <SelectTrigger size="sm" className="w-36">
                                                            <SelectValue
                                                                placeholder={
                                                                    roles.length === 0
                                                                        ? 'No roles'
                                                                        : 'No role'
                                                                }
                                                            />
                                                        </SelectTrigger>
                                                        <SelectContent>
                                                            <SelectItem value={NO_ROLE}>
                                                                No role
                                                            </SelectItem>
                                                            {roles.map(r => (
                                                                <SelectItem key={r.id} value={r.id}>
                                                                    {r.name}
                                                                </SelectItem>
                                                            ))}
                                                        </SelectContent>
                                                    </Select>
                                                ) : (
                                                    assignment.department_roles && (
                                                        <Badge
                                                            variant="outline"
                                                            className="text-xs"
                                                        >
                                                            {assignment.department_roles.name}
                                                        </Badge>
                                                    )
                                                )}

                                                <Badge
                                                    variant={config.variant}
                                                    className="flex items-center gap-1"
                                                >
                                                    <Icon size={12} />
                                                    {config.label}
                                                </Badge>

                                                {canManage && assignment.status !== 'confirmed' && (
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        disabled={isLoading}
                                                        onClick={() =>
                                                            handleStatusChange(
                                                                assignment.id,
                                                                'confirmed'
                                                            )
                                                        }
                                                    >
                                                        Confirm
                                                    </Button>
                                                )}
                                                {canManage && assignment.status !== 'declined' && (
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        disabled={isLoading}
                                                        className="text-destructive hover:text-destructive"
                                                        onClick={() =>
                                                            handleStatusChange(
                                                                assignment.id,
                                                                'declined'
                                                            )
                                                        }
                                                    >
                                                        Decline
                                                    </Button>
                                                )}
                                            </div>
                                        </div>
                                    )
                                })}
                            </div>
                        )}
                    </div>
                )
            })}
        </div>
    )
}
