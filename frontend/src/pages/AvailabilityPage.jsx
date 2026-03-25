import { useState } from 'react'
import { useWorkers } from '@/hooks/useWorkers'
import { useAvailability } from '@/hooks/useAvailability'
import WeeklyGrid from '@/components/availability/WeeklyGrid'
import { Button } from '@/components/ui/button'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Trash2 } from 'lucide-react'

export default function AvailabilityPage() {
  const { workers, loading: workersLoading } = useWorkers()
  const [selectedWorkerId, setSelectedWorkerId] = useState('')

  const {
    availabilityByDay,
    loading: availabilityLoading,
    error,
    toggleDay,
    clearAll,
  } = useAvailability(selectedWorkerId)

  const selectedWorker = workers.find(w => w.id === selectedWorkerId)
  const availableCount = Object.values(availabilityByDay).filter(r => r?.is_available).length

  const handleClearAll = async () => {
    if (!confirm(`Clear all availability for ${selectedWorker?.first_name}?`)) return
    await clearAll()
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold">Availability</h2>
        <p className="text-muted-foreground text-sm mt-1">
          Set which days of the week each worker is available
        </p>
      </div>

      {/* Worker selector */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Select worker</label>
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
            ))
          }
        </select>
      </div>

      {/* Availability grid */}
      {selectedWorkerId && (
        <div className="space-y-4">
          {/* Worker info bar */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="font-medium">
                {selectedWorker?.first_name} {selectedWorker?.last_name}
              </span>
              <Badge variant="outline">
                {availableCount} / 7 days available
              </Badge>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleClearAll}
              disabled={availabilityLoading || availableCount === 0}
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

          {/* The weekly grid */}
          <WeeklyGrid
            availabilityByDay={availabilityByDay}
            onToggle={toggleDay}
            loading={availabilityLoading}
          />

          <p className="text-xs text-muted-foreground">
            Click a day to toggle availability. Changes are saved immediately.
          </p>
        </div>
      )}

      {/* Empty state — no worker selected */}
      {!selectedWorkerId && (
        <div className="flex items-center justify-center h-48 border rounded-lg border-dashed">
          <p className="text-muted-foreground text-sm">
            Select a worker above to manage their availability
          </p>
        </div>
      )}
    </div>
  )
}