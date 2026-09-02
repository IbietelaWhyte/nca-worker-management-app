import { useState } from 'react'
import { addMonths, format, startOfMonth, subMonths } from 'date-fns'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { useSubteams } from '@/hooks/useSubteams'
import MonthPreviewTable, { groupKey } from './MonthPreviewTable'

const SCOPE_OPTIONS = {
    DEPARTMENT_ONLY: 'department_only',
    DEPARTMENT_ALL: 'department_all',
    SUBTEAM: 'subteam',
}

// Backend DayOfWeek is lowercase with Sunday first, matching JS getDay() — no conversion.
const DAYS_OF_WEEK = [
    { value: 'sunday', label: 'Sun' },
    { value: 'monday', label: 'Mon' },
    { value: 'tuesday', label: 'Tue' },
    { value: 'wednesday', label: 'Wed' },
    { value: 'thursday', label: 'Thu' },
    { value: 'friday', label: 'Fri' },
    { value: 'saturday', label: 'Sat' },
]

const defaultForm = {
    title: '',
    start_time: '09:00',
    end_time: '11:00',
    notes: '',
    reminder_days_before: 1,
}

/**
 * Generate a whole month's rota: choose the weekdays the department meets, review the
 * proposed assignments, then save. Nothing is written until the HOD confirms.
 */
export default function GenerateMonthDialog({
    departmentId,
    onPreview,
    onCommit,
    onDone,
    onCancel,
}) {
    const { subteams } = useSubteams(departmentId)
    const [step, setStep] = useState('form')
    const [form, setForm] = useState(defaultForm)
    const [scope, setScope] = useState(SCOPE_OPTIONS.DEPARTMENT_ONLY)
    const [selectedSubteamId, setSelectedSubteamId] = useState('')
    const [month, setMonth] = useState(() => startOfMonth(addMonths(new Date(), 1)))
    const [daysOfWeek, setDaysOfWeek] = useState(['sunday'])
    const [preview, setPreview] = useState(null)
    // scheduled_date -> subteam key -> ordered worker ids. Seeded from the preview and
    // edited by swaps. Keyed by group so a swap can't move someone between subteams.
    const [selection, setSelection] = useState({})
    const [result, setResult] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    const handleChange = e => {
        const { name, value } = e.target
        setForm(prev => ({ ...prev, [name]: value }))
    }

    const toggleDay = day =>
        setDaysOfWeek(prev => (prev.includes(day) ? prev.filter(d => d !== day) : [...prev, day]))

    const basePayload = () => ({
        department_id: departmentId,
        scope,
        subteam_id: scope === SCOPE_OPTIONS.SUBTEAM ? selectedSubteamId : null,
        title: form.title,
        start_time: form.start_time + ':00',
        end_time: form.end_time + ':00',
        notes: form.notes || null,
        reminder_days_before: parseInt(form.reminder_days_before),
    })

    const handlePreview = async e => {
        e?.preventDefault()
        if (!form.title.trim()) return setError('Title is required')
        if (daysOfWeek.length === 0) return setError('Pick at least one day of the week')
        if (form.end_time <= form.start_time) return setError('End time must be after start time')
        if (scope === SCOPE_OPTIONS.SUBTEAM && !selectedSubteamId) {
            return setError('Please select a subteam')
        }

        setError(null)
        setLoading(true)
        try {
            const data = await onPreview({
                ...basePayload(),
                year: month.getFullYear(),
                month: month.getMonth() + 1,
                days_of_week: daysOfWeek,
            })
            setPreview(data)
            setSelection(
                Object.fromEntries(
                    data.dates
                        .filter(d => !d.status.startsWith('skipped'))
                        .map(d => [
                            d.scheduled_date,
                            Object.fromEntries(
                                d.groups.map(g => [
                                    groupKey(g),
                                    g.assignments.map(a => a.worker.id),
                                ])
                            ),
                        ])
                )
            )
            setStep('preview')
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to plan this month')
        } finally {
            setLoading(false)
        }
    }

    const handleSwap = (dateStr, key, index, workerId) =>
        setSelection(prev => {
            const byGroup = prev[dateStr] ?? {}
            const next = [...(byGroup[key] ?? [])]
            next[index] = workerId
            return { ...prev, [dateStr]: { ...byGroup, [key]: next } }
        })

    const handleCommit = async () => {
        // The backend resolves each worker's subteam itself, so the groups flatten into
        // one id list per date.
        const dates = Object.entries(selection)
            .map(([scheduled_date, byGroup]) => ({
                scheduled_date,
                worker_ids: Object.values(byGroup).flat(),
            }))
            .filter(d => d.worker_ids.length > 0)

        if (dates.length === 0) return setError('There is nothing to save for this month')

        setError(null)
        setLoading(true)
        try {
            setResult(await onCommit({ ...basePayload(), dates }))
            setStep('result')
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to save this month')
        } finally {
            setLoading(false)
        }
    }

    if (step === 'result' && result) {
        return (
            <div className="space-y-4">
                <Alert>
                    <p className="text-sm">
                        Created {result.created.length} schedule
                        {result.created.length === 1 ? '' : 's'} for {format(month, 'MMMM yyyy')}.
                    </p>
                </Alert>

                {result.skipped.length > 0 && (
                    <div className="space-y-1">
                        <p className="text-sm font-medium">
                            Skipped {result.skipped.length} date
                            {result.skipped.length === 1 ? '' : 's'}
                        </p>
                        <div className="border rounded-lg divide-y max-h-40 overflow-y-auto">
                            {result.skipped.map(s => (
                                <div
                                    key={s.scheduled_date}
                                    className="px-3 py-2 flex items-center justify-between gap-3"
                                >
                                    <span className="text-sm">
                                        {format(
                                            new Date(s.scheduled_date + 'T00:00:00'),
                                            'EEE, MMM d'
                                        )}
                                    </span>
                                    <span className="text-xs text-muted-foreground">
                                        {s.reason}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                <div className="flex justify-end pt-2">
                    <Button onClick={onDone}>Done</Button>
                </div>
            </div>
        )
    }

    if (step === 'preview' && preview) {
        return (
            <div className="space-y-4">
                {error && (
                    <Alert variant="destructive">
                        <p className="text-sm">{error}</p>
                    </Alert>
                )}

                <div className="flex items-center justify-between">
                    <p className="text-sm font-medium">{format(month, 'MMMM yyyy')}</p>
                    <Badge variant="secondary">{form.title}</Badge>
                </div>

                <MonthPreviewTable preview={preview} selection={selection} onSwap={handleSwap} />

                <div className="flex justify-end gap-2 pt-2">
                    <Button variant="outline" onClick={() => setStep('form')} disabled={loading}>
                        Back
                    </Button>
                    <Button onClick={handleCommit} disabled={loading}>
                        {loading ? 'Saving...' : 'Confirm & save'}
                    </Button>
                </div>
            </div>
        )
    }

    return (
        <form onSubmit={handlePreview} className="space-y-4">
            {error && (
                <Alert variant="destructive">
                    <p className="text-sm">{error}</p>
                </Alert>
            )}

            {/* Month navigation */}
            <div className="space-y-2">
                <Label>Month</Label>
                <div className="flex items-center justify-between border rounded-md px-2 py-1.5">
                    <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => setMonth(prev => subMonths(prev, 1))}
                    >
                        <ChevronLeft size={16} />
                    </Button>
                    <span className="text-sm font-medium">{format(month, 'MMMM yyyy')}</span>
                    <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => setMonth(prev => addMonths(prev, 1))}
                    >
                        <ChevronRight size={16} />
                    </Button>
                </div>
            </div>

            {/* Which weekdays the department meets */}
            <div className="space-y-2">
                <Label>Repeats on</Label>
                <div className="flex flex-wrap gap-3">
                    {DAYS_OF_WEEK.map(day => (
                        <label
                            key={day.value}
                            className="flex items-center gap-1.5 text-sm cursor-pointer"
                        >
                            <Checkbox
                                checked={daysOfWeek.includes(day.value)}
                                onCheckedChange={() => toggleDay(day.value)}
                            />
                            {day.label}
                        </label>
                    ))}
                </div>
            </div>

            {/* Title */}
            <div className="space-y-2">
                <Label htmlFor="month-title">Title</Label>
                <Input
                    id="month-title"
                    name="title"
                    value={form.title}
                    onChange={handleChange}
                    placeholder="e.g. Sunday Morning Service"
                />
                <p className="text-xs text-muted-foreground">
                    Used for every schedule created this month
                </p>
            </div>

            {/* Start and end time */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                    <Label htmlFor="month-start-time">Start time</Label>
                    <Input
                        id="month-start-time"
                        name="start_time"
                        type="time"
                        value={form.start_time}
                        onChange={handleChange}
                    />
                </div>
                <div className="space-y-2">
                    <Label htmlFor="month-end-time">End time</Label>
                    <Input
                        id="month-end-time"
                        name="end_time"
                        type="time"
                        value={form.end_time}
                        onChange={handleChange}
                    />
                </div>
            </div>

            {/* Scope selector */}
            <div className="space-y-2">
                <Label htmlFor="month-scope">Schedule scope</Label>
                <Select
                    value={scope}
                    onValueChange={value => {
                        setScope(value)
                        if (value !== SCOPE_OPTIONS.SUBTEAM) setSelectedSubteamId('')
                    }}
                >
                    <SelectTrigger id="month-scope">
                        <SelectValue placeholder="Select scope" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value={SCOPE_OPTIONS.DEPARTMENT_ONLY}>
                            Department only (workers not in subteams)
                        </SelectItem>
                        {subteams.length > 0 && (
                            <>
                                <SelectItem value={SCOPE_OPTIONS.DEPARTMENT_ALL}>
                                    All workers (entire department)
                                </SelectItem>
                                <SelectItem value={SCOPE_OPTIONS.SUBTEAM}>
                                    Specific subteam
                                </SelectItem>
                            </>
                        )}
                    </SelectContent>
                </Select>
            </div>

            {/* Subteam selector — only shown when scope is SUBTEAM */}
            {scope === SCOPE_OPTIONS.SUBTEAM && subteams.length > 0 && (
                <div className="space-y-2">
                    <Label htmlFor="month-subteam">Subteam</Label>
                    <Select value={selectedSubteamId} onValueChange={setSelectedSubteamId}>
                        <SelectTrigger id="month-subteam">
                            <SelectValue placeholder="Select a subteam" />
                        </SelectTrigger>
                        <SelectContent>
                            {subteams.map(s => (
                                <SelectItem key={s.id} value={s.id}>
                                    {s.name}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            )}

            {/* Reminder days */}
            <div className="space-y-2">
                <Label htmlFor="month-reminder">Send reminder (days before)</Label>
                <Input
                    id="month-reminder"
                    name="reminder_days_before"
                    type="number"
                    min="0"
                    max="14"
                    value={form.reminder_days_before}
                    onChange={handleChange}
                    className="w-24"
                />
            </div>

            {/* Notes */}
            <div className="space-y-2">
                <Label htmlFor="month-notes">Notes (optional)</Label>
                <Input
                    id="month-notes"
                    name="notes"
                    value={form.notes}
                    onChange={handleChange}
                    placeholder="Any additional information"
                />
            </div>

            <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={onCancel} disabled={loading}>
                    Cancel
                </Button>
                <Button type="submit" disabled={loading}>
                    {loading ? 'Planning...' : 'Preview month'}
                </Button>
            </div>
        </form>
    )
}
