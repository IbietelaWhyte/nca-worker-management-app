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
  const { user, isAdmin } = useAuth()
  const { workers, loading: workersLoading } = useWorkers()
  const [selectedWorkerId, setSelectedWorkerId] = useState('')

  const currentWorker = workers.find(w => w.email === user?.email)
  const resolvedWorkerId = isAdmin ? selectedWorkerId : currentWorker?.id ?? ''

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
          {isAdmin
            ? 'Manage specific date availability for any worker'
            : 'Manage your specific date availability'}
        </p>
      </div>

      {/* Worker selector — admins only */}
      {isAdmin && (
        <div className="flex items-center gap-3">
          <label className="text-sm font-medium whitespace-nowrap">Select worker</label>
          <select
            value={selectedWorkerId}
            onChange={(e) => setSelectedWorkerId(e.target.value)}
            disabled={workersLoading}
            className="w-full max-w-sm px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">— Choose a worker —</option>
            {workers
              .filter(w => w.is_active)
              .map(w => (
                <option key={w.id} value={w.id}>
                  {w.first_name} {w.last_name}
                </option>
              ))}
          </select>
        </div>
      )}

      {/* No worker selected yet — admin only */}
      {!resolvedWorkerId && (
        <div className="flex items-center justify-center h-48 border rounded-lg border-dashed">
          <p className="text-muted-foreground text-sm">
            {isAdmin
              ? 'Select a worker above to manage their availability'
              : 'Loading your availability...'}
          </p>
        </div>
      )}

      {/* Availability editor */}
      {resolvedWorkerId && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="font-medium">
                {selectedWorker?.first_name} {selectedWorker?.last_name}
              </span>
              {specificDates.length > 0 && (
                <Badge variant="outline">
                  {specificDates.length} date override{specificDates.length !== 1 ? 's' : ''}
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
            Click a date once to mark available, again to mark unavailable, once more to clear.
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