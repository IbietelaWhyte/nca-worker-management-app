import { useState } from 'react'
import { addMonths, format, startOfMonth, subMonths } from 'date-fns'
import { ChevronLeft, ChevronRight, Pencil } from 'lucide-react'
import { useMonthlyLeads } from '@/hooks/useMonthlyLeads'
import { monthKey } from '@/api/monthlyLeads'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'

// Mirrors settings.max_monthly_leads. The server enforces it regardless; this only stops the
// picker offering a fourth name that would be refused.
const MAX_LEADS = 3

/**
 * Name a department's monthly leads ("Teacher of the Month"), one month at a time.
 *
 * Rendered only for a department with a title. A lead serves every service that month, so
 * generation leaves them off the department's rota — but only rotas generated from now on,
 * which the copy says so a head knows to fix any month they had already generated.
 */
export default function MonthlyLeadsPanel({ department }) {
    const [month, setMonth] = useState(() => startOfMonth(new Date()))
    const { title, leads, loading, error, save } = useMonthlyLeads(department.id, monthKey(month))

    const [pickerOpen, setPickerOpen] = useState(false)
    const [picked, setPicked] = useState([])
    const [saving, setSaving] = useState(false)
    const [saveError, setSaveError] = useState(null)

    const label = title ?? department.monthly_lead_title
    const members = (department.workers ?? []).filter(w => w.is_active)
    const named = leads.filter(lead => lead.worker)

    const openPicker = () => {
        setPicked(leads.map(lead => lead.worker_id))
        setSaveError(null)
        setPickerOpen(true)
    }

    const togglePicked = workerId =>
        setPicked(prev =>
            prev.includes(workerId) ? prev.filter(id => id !== workerId) : [...prev, workerId]
        )

    const handleSave = async () => {
        setSaving(true)
        setSaveError(null)
        try {
            await save(picked)
            setPickerOpen(false)
        } catch (err) {
            setSaveError(err.response?.data?.detail ?? 'Failed to save')
        } finally {
            setSaving(false)
        }
    }

    const atCap = picked.length >= MAX_LEADS

    return (
        <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
                Name up to {MAX_LEADS} people in charge of {department.name} for a month. They are
                shown at the top of that month&apos;s schedules and on the shared rota, and are left
                out when that month&apos;s rotas are generated, since they serve every service.
                Schedules you have already generated are not changed — remove them from those
                yourself.
            </p>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-2">
                    <Button
                        variant="outline"
                        size="icon-sm"
                        aria-label="Previous month"
                        onClick={() => setMonth(prev => subMonths(prev, 1))}
                    >
                        <ChevronLeft size={16} />
                    </Button>
                    <span className="w-36 text-center text-sm font-medium">
                        {format(month, 'MMMM yyyy')}
                    </span>
                    <Button
                        variant="outline"
                        size="icon-sm"
                        aria-label="Next month"
                        onClick={() => setMonth(prev => addMonths(prev, 1))}
                    >
                        <ChevronRight size={16} />
                    </Button>
                </div>
                <Button size="sm" onClick={openPicker} disabled={loading}>
                    <Pencil size={14} className="mr-1" /> Edit {format(month, 'MMMM')}
                </Button>
            </div>

            {error && (
                <Alert variant="destructive">
                    <p className="text-sm">{error}</p>
                </Alert>
            )}

            {loading ? (
                <p className="text-sm text-muted-foreground">Loading...</p>
            ) : named.length === 0 ? (
                <div className="rounded-lg border border-dashed p-6 text-center">
                    <p className="text-sm text-muted-foreground">
                        Nobody is named as {label} for {format(month, 'MMMM yyyy')} yet.
                    </p>
                </div>
            ) : (
                <ul className="divide-y rounded-lg border">
                    {named.map(lead => (
                        <li key={lead.id} className="flex flex-col p-3">
                            <span className="text-sm font-medium">
                                {lead.worker.first_name} {lead.worker.last_name}
                            </span>
                            <span className="truncate text-xs text-muted-foreground">
                                {lead.worker.email}
                            </span>
                        </li>
                    ))}
                </ul>
            )}

            <Dialog open={pickerOpen} onOpenChange={setPickerOpen}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>
                            {label} — {format(month, 'MMMM yyyy')}
                        </DialogTitle>
                        <p className="mt-2 text-sm text-muted-foreground">
                            Pick up to {MAX_LEADS} active members of {department.name}.
                        </p>
                    </DialogHeader>

                    {saveError && (
                        <Alert variant="destructive">
                            <p className="text-sm">{saveError}</p>
                        </Alert>
                    )}

                    {members.length === 0 ? (
                        <p className="py-4 text-center text-sm text-muted-foreground">
                            This department has no active members yet.
                        </p>
                    ) : (
                        <div className="max-h-80 space-y-2 overflow-y-auto">
                            {members.map(worker => {
                                const isPicked = picked.includes(worker.id)
                                return (
                                    <div
                                        key={worker.id}
                                        className={`flex items-center justify-between gap-3 rounded-md border p-3 transition-colors ${
                                            isPicked
                                                ? 'border-primary bg-primary/5'
                                                : 'hover:bg-accent'
                                        }`}
                                    >
                                        <div className="min-w-0">
                                            <p className="text-sm font-medium">
                                                {worker.first_name} {worker.last_name}
                                            </p>
                                            <p className="truncate text-xs text-muted-foreground">
                                                {worker.email}
                                            </p>
                                        </div>
                                        <Button
                                            size="sm"
                                            variant={isPicked ? 'outline' : 'default'}
                                            disabled={saving || (!isPicked && atCap)}
                                            onClick={() => togglePicked(worker.id)}
                                        >
                                            {isPicked ? 'Remove' : 'Add'}
                                        </Button>
                                    </div>
                                )
                            })}
                        </div>
                    )}

                    {atCap && (
                        <p className="text-xs text-muted-foreground">
                            That&apos;s the most for one month. Remove someone to pick another.
                        </p>
                    )}

                    <DialogFooter>
                        <Button
                            variant="outline"
                            disabled={saving}
                            onClick={() => setPickerOpen(false)}
                        >
                            Cancel
                        </Button>
                        <Button disabled={saving} onClick={handleSave}>
                            {saving ? 'Saving...' : 'Save'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
