import { useState } from 'react'
import { useWorkers } from '@/hooks/useWorkers'
import { useAvailability } from '@/hooks/useAvailability'
import { useAuth } from '@/context/AuthContext'
import SpecificDatesCalendar from '@/components/availability/SpecificDatesCalendar'
import { Button } from '@/components/ui/button'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Trash2 } from 'lucide-react'

export default function AvailabilityPage() {
    const { user, isAdmin, isDepartmentHead } = useAuth()
    const { workers, loading: workersLoading } = useWorkers()
    const [selectedWorkerId, setSelectedWorkerId] = useState('')

    // Workers are linked to auth users by email (auth_user_id is not serialized
    // to the client). Compare case-insensitively to avoid spurious mismatches.
    const currentWorker = workers.find(w => w.email?.toLowerCase() === user?.email?.toLowerCase())

    // HODs and assistant HODs get the picker too — the backend already permits them to manage
    // workers in departments they lead, and GET /workers is scoped to exactly those workers, so
    // the list needs no filtering here. isDepartmentHead is true for admins as well.
    const canPickWorker = isDepartmentHead

    // An HOD who is not themselves a member of a department they lead will not appear in that
    // scoped list, so union them in and start the picker on their own record.
    const pickableWorkers = [
        ...(currentWorker && !workers.some(w => w.id === currentWorker.id) ? [currentWorker] : []),
        ...workers,
    ].filter(w => w.is_active)

    const defaultWorkerId = isAdmin ? '' : (currentWorker?.id ?? '')
    const resolvedWorkerId = canPickWorker
        ? selectedWorkerId || defaultWorkerId
        : (currentWorker?.id ?? '')
    const noProfileLinked = !isAdmin && !workersLoading && !currentWorker

    const {
        specificDates,
        loading: availabilityLoading,
        error,
        toggleSpecificDate,
        clearAll,
    } = useAvailability(resolvedWorkerId)

    const selectedWorker = workers.find(w => w.id === resolvedWorkerId)

    const handleClearAll = async () => {
        if (!confirm(`Clear all availability for ${selectedWorker?.first_name}?`)) return
        await clearAll()
    }

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-2xl font-bold">Availability</h2>
                <p className="text-muted-foreground text-sm mt-1">
                    {canPickWorker
                        ? 'Manage specific date availability for the workers you oversee'
                        : 'Manage your specific date availability'}
                </p>
            </div>

            {/* Worker selector — admins, HODs and assistant HODs */}
            {canPickWorker && (
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
                    <label className="text-sm font-medium whitespace-nowrap">Select worker</label>
                    <select
                        value={selectedWorkerId}
                        onChange={e => setSelectedWorkerId(e.target.value)}
                        disabled={workersLoading}
                        className="w-full max-w-sm px-3 py-2 border rounded-md text-base sm:text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                        <option value="">— Choose a worker —</option>
                        {pickableWorkers.map(w => (
                            <option key={w.id} value={w.id}>
                                {w.first_name} {w.last_name}
                                {w.id === currentWorker?.id ? ' (you)' : ''}
                            </option>
                        ))}
                    </select>
                </div>
            )}

            {/* No worker resolved — admin hasn't picked one, profile is loading, or none is linked */}
            {!resolvedWorkerId && (
                <div className="flex items-center justify-center h-48 border rounded-lg border-dashed">
                    <p className="text-muted-foreground text-sm">
                        {canPickWorker
                            ? 'Select a worker above to manage their availability'
                            : noProfileLinked
                              ? 'No worker profile is linked to your account. Please contact an administrator.'
                              : 'Loading your availability...'}
                    </p>
                </div>
            )}

            {/* Availability editor */}
            {resolvedWorkerId && (
                <div className="space-y-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div className="flex flex-wrap items-center gap-3">
                            <span className="font-medium">
                                {selectedWorker?.first_name} {selectedWorker?.last_name}
                            </span>
                            {specificDates.length > 0 && (
                                <Badge variant="outline">
                                    {specificDates.length} date override
                                    {specificDates.length !== 1 ? 's' : ''}
                                </Badge>
                            )}
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleClearAll}
                            disabled={availabilityLoading || specificDates.length === 0}
                            className="text-destructive hover:text-destructive"
                        >
                            <Trash2 size={14} className="mr-2" />
                            Clear all
                        </Button>
                    </div>

                    {error && (
                        <Alert variant="destructive">
                            <p className="text-sm">{error}</p>
                        </Alert>
                    )}

                    <p className="text-sm text-muted-foreground">
                        Click a date once to mark available, again to mark unavailable, once more to
                        clear.
                    </p>

                    <SpecificDatesCalendar
                        specificDates={specificDates}
                        onDateClick={toggleSpecificDate}
                        loading={availabilityLoading}
                    />
                </div>
            )}
        </div>
    )
}
