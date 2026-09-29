import { useState } from 'react'
import { ArrowLeftRight, Check, UserMinus } from 'lucide-react'
import AttendanceBadge from '@/components/schedules/AttendanceBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { isHere } from '@/lib/attendance'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'

// Radix Select disallows an empty-string value, so use a sentinel for "no role".
const NO_ROLE = '__none__'

export default function AssignmentsList({
    groupedAssignments = [],
    onRoleChange,
    onSwap,
    onRemove,
    onMarkHere,
    attendanceBusyId = null,
    roles = [],
    canManage = false,
}) {
    const [roleLoadingId, setRoleLoadingId] = useState(null)

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

                                    return (
                                        <div
                                            key={assignment.id}
                                            className="flex flex-col gap-3 p-3 border rounded-md sm:flex-row sm:items-center sm:justify-between"
                                        >
                                            <div className="flex min-w-0 items-center gap-3">
                                                <div className="w-8 h-8 shrink-0 rounded-full bg-muted flex items-center justify-center text-xs font-medium">
                                                    {worker
                                                        ? `${worker.first_name[0]}${worker.last_name[0]}`
                                                        : '?'}
                                                </div>
                                                <div className="min-w-0">
                                                    <p className="truncate text-sm font-medium">
                                                        {worker
                                                            ? `${worker.first_name} ${worker.last_name}`
                                                            : 'Unknown worker'}
                                                    </p>
                                                    {worker && (
                                                        <p className="truncate text-xs text-muted-foreground">
                                                            {worker.email}
                                                        </p>
                                                    )}
                                                </div>
                                            </div>

                                            <div className="flex flex-wrap items-center gap-2 sm:shrink-0">
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
                                                        <SelectTrigger
                                                            size="sm"
                                                            className="w-full sm:w-36"
                                                        >
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

                                                {/* The cluster Confirm/Decline used to sit in.
                                                    A worker who cannot make a date now speaks to
                                                    their head, and this is what the head does
                                                    about it — and, once the service has happened,
                                                    records about it.

                                                    Roll call is a mode rather than an extra
                                                    column: this cluster already holds a role
                                                    select, Swap and Remove, and five controls
                                                    will not fit 375px or be aimed at reliably.
                                                    While taking the register you are not editing
                                                    the rota, so the editing controls stand down
                                                    and the tap target takes their place. */}
                                                {onMarkHere ? (
                                                    <Button
                                                        type="button"
                                                        variant={
                                                            isHere(assignment)
                                                                ? 'default'
                                                                : 'outline'
                                                        }
                                                        /* No Button size reaches 44px — sm is
                                                           h-9 and default h-10 — and a roll call
                                                           is forty taps on a phone, so they have
                                                           to land. min-h-11 is the idiom the
                                                           sidebar already uses for this. */
                                                        className="min-h-11 min-w-28"
                                                        disabled={
                                                            attendanceBusyId === assignment.id
                                                        }
                                                        onClick={() => onMarkHere(assignment)}
                                                    >
                                                        {isHere(assignment) && (
                                                            <Check size={16} className="mr-1" />
                                                        )}
                                                        {isHere(assignment) ? 'Here' : 'Mark here'}
                                                    </Button>
                                                ) : (
                                                    <AttendanceBadge assignment={assignment} />
                                                )}

                                                {canManage && !onMarkHere && onSwap && (
                                                    <Button
                                                        type="button"
                                                        variant="outline"
                                                        size="sm"
                                                        onClick={() => onSwap(assignment)}
                                                    >
                                                        <ArrowLeftRight
                                                            size={14}
                                                            className="mr-1"
                                                        />
                                                        Swap
                                                    </Button>
                                                )}
                                                {canManage && !onMarkHere && onRemove && (
                                                    <Button
                                                        type="button"
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => onRemove(assignment)}
                                                        className="text-destructive hover:text-destructive"
                                                    >
                                                        <UserMinus size={14} className="mr-1" />
                                                        Remove
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
