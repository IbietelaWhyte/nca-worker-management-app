import { useCallback, useEffect, useState } from 'react'
import { format } from 'date-fns'
import { AlertTriangle, CalendarOff, Trash2 } from 'lucide-react'
import {
    createWorkerLeave,
    deleteWorkerLeave,
    endWorkerLeave,
    getLeaveClashes,
    getWorkerLeave,
} from '@/api/leave'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const today = () => format(new Date(), 'yyyy-MM-dd')

// Parsed from local date parts: new Date('2026-10-20') is read as UTC and renders as the 19th
// west of Greenwich.
const readable = dateStr =>
    new Date(dateStr + 'T00:00:00').toLocaleDateString('en-CA', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
    })

/**
 * Record that a worker is away for a stretch.
 *
 * Leave takes somebody out of schedule generation and stops the availability prompt texting
 * them, without deactivating them — they keep their departments, roles and history, so they
 * come back without being re-added.
 *
 * It never edits the rota. Duties already booked inside the window are listed before the head
 * confirms, so they know what to reassign; dropping people off a rota as a side effect of
 * recording an absence would be the worse surprise.
 *
 * "No end date yet" records leave with a null end_date, covering every date from the start on.
 * The head sets the last day once it is known, from the list below — an update, so the absence
 * stays in the worker's history rather than being deleted and re-entered.
 */
export default function WorkerLeaveDialog({ worker, open, onOpenChange, onChanged }) {
    const [leave, setLeave] = useState([])
    const [startDate, setStartDate] = useState(today())
    const [endDate, setEndDate] = useState(today())
    const [openEnded, setOpenEnded] = useState(false)
    // The leave whose last day is being set, and the date being entered for it.
    const [ending, setEnding] = useState(null)
    const [endingDate, setEndingDate] = useState(today())
    const [reason, setReason] = useState('')
    const [clashes, setClashes] = useState([])
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState(null)

    const workerId = worker?.id

    useEffect(() => {
        if (!open || !workerId) return
        let cancelled = false
        setError(null)
        getWorkerLeave(workerId)
            .then(response => {
                if (!cancelled) setLeave(response.data)
            })
            .catch(() => {
                if (!cancelled) setError("Could not load this worker's leave.")
            })
        return () => {
            cancelled = true
        }
    }, [open, workerId])

    // Look up clashing duties whenever the range changes, so the warning is on screen before
    // the head commits rather than after.
    const loadClashes = useCallback(async () => {
        if (!workerId || !startDate || (!openEnded && (!endDate || endDate < startDate))) {
            setClashes([])
            return
        }
        try {
            const response = await getLeaveClashes(workerId, startDate, openEnded ? null : endDate)
            setClashes(response.data.clashes ?? [])
        } catch {
            // Advisory only. A failed lookup must not block recording the absence.
            setClashes([])
        }
    }, [workerId, startDate, endDate, openEnded])

    useEffect(() => {
        if (!open) return
        loadClashes()
    }, [open, loadClashes])

    if (!worker) return null

    const name = `${worker.first_name} ${worker.last_name}`
    const rangeInvalid = Boolean(!openEnded && startDate && endDate && endDate < startDate)

    const handleSave = async () => {
        setBusy(true)
        setError(null)
        try {
            const response = await createWorkerLeave(workerId, {
                start_date: startDate,
                end_date: openEnded ? null : endDate,
                reason: reason.trim() || null,
            })
            setLeave(prev =>
                [...prev, response.data].sort((a, b) => a.start_date.localeCompare(b.start_date))
            )
            setReason('')
            setClashes([])
            onChanged?.()
        } catch (err) {
            // The backend names the leave it collided with, which is what the head needs.
            setError(err.response?.data?.detail ?? 'Could not save this leave.')
        } finally {
            setBusy(false)
        }
    }

    const handleEnd = async () => {
        setBusy(true)
        setError(null)
        try {
            const response = await endWorkerLeave(ending.id, endingDate)
            setLeave(prev => prev.map(l => (l.id === ending.id ? response.data : l)))
            setEnding(null)
            onChanged?.()
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Could not set the last day of this leave.')
        } finally {
            setBusy(false)
        }
    }

    const handleDelete = async leaveId => {
        setError(null)
        try {
            await deleteWorkerLeave(leaveId)
            setLeave(prev => prev.filter(l => l.id !== leaveId))
            onChanged?.()
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Could not remove this leave.')
        }
    }

    return (
        <Dialog open={open} onOpenChange={next => !busy && onOpenChange(next)}>
            <DialogContent className="sm:max-w-lg">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <CalendarOff size={18} />
                        Leave for {name}
                    </DialogTitle>
                    <DialogDescription>
                        While away they are not scheduled and are not texted for availability. They
                        keep their departments and roles, so nothing needs re-adding when they
                        return.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-5">
                    {error && (
                        <Alert variant="destructive">
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    )}

                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <div className="space-y-1.5">
                            <Label htmlFor="leave-start">First day away</Label>
                            <Input
                                id="leave-start"
                                type="date"
                                value={startDate}
                                onChange={e => setStartDate(e.target.value)}
                            />
                        </div>
                        <div className="space-y-1.5">
                            <Label htmlFor="leave-end">Last day away</Label>
                            <Input
                                id="leave-end"
                                type="date"
                                value={openEnded ? '' : endDate}
                                disabled={openEnded}
                                onChange={e => setEndDate(e.target.value)}
                            />
                        </div>
                    </div>

                    <div className="space-y-1">
                        <div className="flex items-center gap-2">
                            <Checkbox
                                id="leave-open-ended"
                                checked={openEnded}
                                onCheckedChange={checked => setOpenEnded(checked === true)}
                            />
                            <Label htmlFor="leave-open-ended" className="font-normal">
                                No end date yet
                            </Label>
                        </div>
                        {openEnded && (
                            <p className="text-xs text-muted-foreground">
                                They stay on leave until you set their last day here.
                            </p>
                        )}
                    </div>

                    {rangeInvalid && (
                        <p className="text-sm text-destructive">
                            The last day cannot be before the first.
                        </p>
                    )}

                    <div className="space-y-1.5">
                        <Label htmlFor="leave-reason">Note (optional)</Label>
                        <Input
                            id="leave-reason"
                            value={reason}
                            maxLength={500}
                            placeholder="Travelling, maternity leave, unwell…"
                            onChange={e => setReason(e.target.value)}
                        />
                        <p className="text-xs text-muted-foreground">
                            Only heads see this. It is never sent to the worker.
                        </p>
                    </div>

                    {clashes.length > 0 && (
                        <Alert className="border-warning/50">
                            <AlertTriangle size={16} className="text-warning" />
                            <AlertDescription>
                                <p className="font-medium">
                                    {clashes.length === 1
                                        ? '1 duty falls in this period'
                                        : `${clashes.length} duties fall in this period`}
                                </p>
                                <ul className="mt-1 space-y-0.5 text-sm">
                                    {clashes.map(clash => (
                                        <li key={clash.schedule_id}>
                                            {readable(clash.scheduled_date)}
                                            {clash.department_name
                                                ? ` — ${clash.department_name}`
                                                : ''}
                                        </li>
                                    ))}
                                </ul>
                                <p className="mt-2 text-sm">
                                    These stay on the rota. Reassign them from the schedule page.
                                </p>
                            </AlertDescription>
                        </Alert>
                    )}

                    <div className="flex flex-wrap justify-end gap-2">
                        <Button
                            onClick={handleSave}
                            disabled={
                                busy || rangeInvalid || !startDate || (!openEnded && !endDate)
                            }
                        >
                            Set on leave
                        </Button>
                    </div>

                    {leave.length > 0 && (
                        <div className="space-y-2 border-t pt-4">
                            <p className="text-sm font-medium">Recorded leave</p>
                            <ul className="max-h-48 space-y-1 overflow-y-auto">
                                {leave.map(entry => (
                                    <li
                                        key={entry.id}
                                        className="space-y-2 rounded-md border px-3 py-2 text-sm"
                                    >
                                        <div className="flex items-center justify-between gap-3">
                                            <div className="min-w-0">
                                                <p>
                                                    {entry.end_date
                                                        ? `${readable(entry.start_date)} – ${readable(entry.end_date)}`
                                                        : `From ${readable(entry.start_date)}, no end date`}
                                                </p>
                                                {entry.reason && (
                                                    <p className="truncate text-xs text-muted-foreground">
                                                        {entry.reason}
                                                    </p>
                                                )}
                                            </div>
                                            <div className="flex shrink-0 items-center gap-2">
                                                {entry.end_date && entry.end_date < today() && (
                                                    <Badge variant="secondary">Past</Badge>
                                                )}
                                                {!entry.end_date && ending?.id !== entry.id && (
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        onClick={() => {
                                                            setEnding(entry)
                                                            setEndingDate(
                                                                entry.start_date > today()
                                                                    ? entry.start_date
                                                                    : today()
                                                            )
                                                        }}
                                                    >
                                                        Set last day
                                                    </Button>
                                                )}
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => handleDelete(entry.id)}
                                                    className="text-destructive hover:text-destructive"
                                                    aria-label="Remove this leave"
                                                >
                                                    <Trash2 size={14} />
                                                </Button>
                                            </div>
                                        </div>
                                        {ending?.id === entry.id && (
                                            <div className="flex flex-wrap items-end gap-2">
                                                <div className="space-y-1">
                                                    <Label htmlFor={`leave-last-${entry.id}`}>
                                                        Last day away
                                                    </Label>
                                                    <Input
                                                        id={`leave-last-${entry.id}`}
                                                        type="date"
                                                        value={endingDate}
                                                        min={entry.start_date}
                                                        onChange={e =>
                                                            setEndingDate(e.target.value)
                                                        }
                                                    />
                                                </div>
                                                <Button
                                                    size="sm"
                                                    onClick={handleEnd}
                                                    disabled={
                                                        busy ||
                                                        !endingDate ||
                                                        endingDate < entry.start_date
                                                    }
                                                >
                                                    Save
                                                </Button>
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => setEnding(null)}
                                                    disabled={busy}
                                                >
                                                    Cancel
                                                </Button>
                                            </div>
                                        )}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    )
}
