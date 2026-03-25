import { useState } from 'react'
import { DayPicker } from 'react-day-picker'
import { Badge } from '@/components/ui/badge'
import 'react-day-picker/dist/style.css'

export default function SpecificDatesCalendar({
    specificDates = [],
    onDateClick,
    loading,
}) {
    const [month, setMonth] = useState(new Date())

    // Build lookup maps for available and unavailable specific dates
    const availableDates = specificDates
        .filter(r => r.is_available)
        .map(r => new Date(r.specific_date + 'T00:00:00'))

    const unavailableDates = specificDates
        .filter(r => !r.is_available)
        .map(r => new Date(r.specific_date + 'T00:00:00'))

    // Find record for a given date click
    const handleDayClick = (date) => {
        if (!date || loading) return
        const dateStr = date.toISOString().split('T')[0]
        const existing = specificDates.find(r => r.specific_date === dateStr)
        onDateClick(dateStr, existing)
    }

    return (
        <div className="space-y-4">
        <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-primary" />
            <span className="text-muted-foreground">Available (override)</span>
            </div>
            <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-destructive" />
            <span className="text-muted-foreground">Unavailable (override)</span>
            </div>
        </div>

        <div className="border rounded-lg p-4 inline-block">
            <DayPicker
            mode="multiple"
            month={month}
            onMonthChange={setMonth}
            onDayClick={handleDayClick}
            modifiers={{
                available: availableDates,
                unavailable: unavailableDates,
            }}
            modifiersClassNames={{
                available: 'rdp-day-available',
                unavailable: 'rdp-day-unavailable',
            }}
            disabled={loading}
            />
        </div>

        {/* Active overrides list */}
        {specificDates.length > 0 && (
            <div className="space-y-2">
            <p className="text-sm font-medium">Active date overrides</p>
            <div className="space-y-1 max-h-48 overflow-y-auto">
                {specificDates
                .sort((a, b) => a.specific_date.localeCompare(b.specific_date))
                .map(record => (
                    <div
                    key={record.id}
                    className="flex items-center justify-between px-3 py-2 border rounded-md text-sm"
                    >
                    <span>{new Date(record.specific_date + 'T00:00:00').toLocaleDateString('en-CA', {
                        weekday: 'short',
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                    })}</span>
                    <Badge variant={record.is_available ? 'default' : 'destructive'}>
                        {record.is_available ? 'Available' : 'Unavailable'}
                    </Badge>
                    </div>
                ))}
            </div>
            </div>
        )}

        {specificDates.length === 0 && (
            <p className="text-sm text-muted-foreground">
            No specific date overrides set. Click any date on the calendar to add one.
            </p>
        )}
        </div>
    )
}