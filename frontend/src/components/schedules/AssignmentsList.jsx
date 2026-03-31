import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { CheckCircle, XCircle, Clock } from 'lucide-react'

const STATUS_CONFIG = {
    pending: { label: 'Pending', variant: 'secondary', icon: Clock },
    confirmed: { label: 'Confirmed', variant: 'default', icon: CheckCircle },
    declined: { label: 'Declined', variant: 'destructive', icon: XCircle },
}

export default function AssignmentsList({ assignments = [], onStatusChange, canManage = false }) {
    const [loadingId, setLoadingId] = useState(null)

    const handleStatusChange = async (assignmentId, status) => {
        setLoadingId(assignmentId)
        try {
            await onStatusChange(assignmentId, status)
        } finally {
            setLoadingId(null)
        }
    }

    if (assignments.length === 0) {
        return (
            <p className="text-sm text-muted-foreground text-center py-8">
                No workers assigned yet.
            </p>
        )
    }

    return (
        <div className="space-y-2">
            {assignments.map(assignment => {
                const worker = assignment.workers // already nested in the response
                const config = STATUS_CONFIG[assignment.status] ?? STATUS_CONFIG.pending
                const Icon = config.icon
                const isLoading = loadingId === assignment.id

                return (
                    <div
                        key={assignment.id}
                        className="flex items-center justify-between p-3 border rounded-md"
                    >
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-xs font-medium">
                                {worker ? `${worker.first_name[0]}${worker.last_name[0]}` : '?'}
                            </div>
                            <div>
                                <p className="text-sm font-medium">
                                    {worker
                                        ? `${worker.first_name} ${worker.last_name}`
                                        : 'Unknown worker'}
                                </p>
                                {worker && (
                                    <p className="text-xs text-muted-foreground">{worker.email}</p>
                                )}
                            </div>
                        </div>

                        <div className="flex items-center gap-2">
                            <Badge variant={config.variant} className="flex items-center gap-1">
                                <Icon size={12} />
                                {config.label}
                            </Badge>

                            {canManage && assignment.status !== 'confirmed' && (
                                <Button
                                    size="sm"
                                    variant="outline"
                                    disabled={isLoading}
                                    onClick={() => handleStatusChange(assignment.id, 'confirmed')}
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
                                    onClick={() => handleStatusChange(assignment.id, 'declined')}
                                >
                                    Decline
                                </Button>
                            )}
                        </div>
                    </div>
                )
            })}
        </div>
    )
}
