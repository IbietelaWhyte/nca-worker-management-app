import { useState } from 'react'
import { format } from 'date-fns'
import { CalendarIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert } from '@/components/ui/alert'
import { Calendar } from '@/components/ui/calendar'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn } from '@/lib/utils'

const defaultForm = {
    title: '',
    scheduled_date: null,
    start_time: '09:00',
    end_time: '11:00',
    notes: '',
    reminder_days_before: 1,
}

export default function GenerateScheduleForm({ departmentId, subteams = [], onSubmit, onCancel }) {
    const [form, setForm] = useState(defaultForm)
    const [selectedSubteamId, setSelectedSubteamId] = useState('')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const [calendarOpen, setCalendarOpen] = useState(false)

    const handleChange = e => {
        const { name, value } = e.target
        setForm(prev => ({ ...prev, [name]: value }))
    }

    const handleSubmit = async () => {
        if (!form.title.trim()) return setError('Title is required')
        if (!form.scheduled_date) return setError('Date is required')
        if (!form.start_time || !form.end_time) return setError('Start and end time are required')

        setError(null)
        setLoading(true)

        try {
            await onSubmit({
                department_id: departmentId,
                subteam_id: selectedSubteamId || null,
                title: form.title,
                scheduled_date: format(form.scheduled_date, 'yyyy-MM-dd'),
                start_time: form.start_time + ':00',
                end_time: form.end_time + ':00',
                notes: form.notes || null,
                reminder_days_before: parseInt(form.reminder_days_before),
            })
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to generate schedule')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="space-y-4">
            {error && (
                <Alert variant="destructive">
                    <p className="text-sm">{error}</p>
                </Alert>
            )}

            {/* Title */}
            <div className="space-y-2">
                <Label htmlFor="title">Title</Label>
                <Input
                    id="title"
                    name="title"
                    value={form.title}
                    onChange={handleChange}
                    placeholder="e.g. Sunday Morning Service"
                />
            </div>

            {/* Date picker */}
            <div className="space-y-2">
                <Label>Date</Label>
                <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
                    <PopoverTrigger asChild>
                        <Button
                            variant="outline"
                            className={cn(
                                'w-full justify-start text-left font-normal',
                                !form.scheduled_date && 'text-muted-foreground'
                            )}
                        >
                            <CalendarIcon size={16} className="mr-2" />
                            {form.scheduled_date
                                ? format(form.scheduled_date, 'PPP')
                                : 'Pick a date'}
                        </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="start">
                        <Calendar
                            mode="single"
                            selected={form.scheduled_date}
                            onSelect={date => {
                                setForm(prev => ({ ...prev, scheduled_date: date }))
                                setCalendarOpen(false)
                            }}
                            disabled={date => date < new Date()}
                            initialFocus
                        />
                    </PopoverContent>
                </Popover>
            </div>

            {/* Start and end time */}
            <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                    <Label htmlFor="start_time">Start time</Label>
                    <Input
                        id="start_time"
                        name="start_time"
                        type="time"
                        value={form.start_time}
                        onChange={handleChange}
                    />
                </div>
                <div className="space-y-2">
                    <Label htmlFor="end_time">End time</Label>
                    <Input
                        id="end_time"
                        name="end_time"
                        type="time"
                        value={form.end_time}
                        onChange={handleChange}
                    />
                </div>
            </div>

            {/* Subteam selector — only shown if department has subteams */}
            {subteams.length > 0 && (
                <div className="space-y-2">
                    <Label htmlFor="subteam">Subteam (optional)</Label>
                    <select
                        id="subteam"
                        value={selectedSubteamId}
                        onChange={e => setSelectedSubteamId(e.target.value)}
                        className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                        <option value="">— Whole department —</option>
                        {subteams.map(s => (
                            <option key={s.id} value={s.id}>
                                {s.name}
                            </option>
                        ))}
                    </select>
                </div>
            )}

            {/* Reminder days */}
            <div className="space-y-2">
                <Label htmlFor="reminder_days_before">Send reminder (days before)</Label>
                <Input
                    id="reminder_days_before"
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
                <Label htmlFor="notes">Notes (optional)</Label>
                <Input
                    id="notes"
                    name="notes"
                    value={form.notes}
                    onChange={handleChange}
                    placeholder="Any additional information"
                />
            </div>

            <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={onCancel} disabled={loading}>
                    Cancel
                </Button>
                <Button onClick={handleSubmit} disabled={loading}>
                    {loading ? 'Generating...' : 'Generate Schedule'}
                </Button>
            </div>
        </div>
    )
}
