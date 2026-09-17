import { useState } from 'react'
import { DayPicker } from 'react-day-picker'
import { format } from 'date-fns'
import { Badge } from '@/components/ui/badge'
import 'react-day-picker/dist/style.css'

/**
 * The one calendar behind both availability editors, signed-in and public.
 *
 * It asks a single question — which dates can you NOT serve — because that is the only answer
 * the rota acts on: a date with no record is already treated as available. So a day has two
 * states, not three: unmarked, or marked off. Tapping toggles between them.
 *
 * @param {Array<{ id: string, specific_date: string }>} unavailableDates - Dates marked off.
 * @param {(dateStr: string, existing?: object) => void} onDateClick - Toggle handler.
 * @param {boolean} loading - Disables every day while a save is in flight.
 * @param {string} [editableFrom] - Earliest date still open for changes, as yyyy-MM-dd. Days
 *   before it are closed: past the cut-off there is no longer time to act on the answer.
 */
export default function SpecificDatesCalendar({
    unavailableDates = [],
    onDateClick,
    loading,
    editableFrom,
}) {
    const [month, setMonth] = useState(new Date())

    const markedDays = unavailableDates.map(r => new Date(r.specific_date + 'T00:00:00'))

    // Parsed from local date parts for the same reason the click handler formats that way:
    // new Date('2026-09-17') is parsed as UTC and lands on the 16th west of Greenwich.
    const cutoff = editableFrom ? new Date(editableFrom + 'T00:00:00') : null

    // `true` disables every day; a matcher closes the ones before the cut-off. Both shapes are
    // valid `disabled` values, so the pair collapses to whichever applies.
    const disabled = loading || (cutoff ? { before: cutoff } : false)

    const handleDayClick = (date, modifiers) => {
        if (!date || loading || modifiers?.disabled) return
        // Format from local date parts — toISOString() would convert to UTC and
        // roll back a day in UTC-positive timezones.
        const dateStr = format(date, 'yyyy-MM-dd')
        const existing = unavailableDates.find(r => r.specific_date === dateStr)
        onDateClick(dateStr, existing)
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center gap-2 text-sm">
                <div className="w-3 h-3 rounded-full bg-destructive" />
                <span className="text-muted-foreground">Cannot serve</span>
            </div>

            {/* react-day-picker fixes day cells at 44px, so the grid is a hard 308px. Scroll it
                rather than let it burst the card on a narrow phone. */}
            <div className="max-w-full overflow-x-auto rounded-lg border p-2 sm:inline-block sm:p-4">
                <DayPicker
                    mode="multiple"
                    // Controlled: with no `selected`, react-day-picker keeps its own internal
                    // selection, so a clicked day picked up a ring even when the save failed —
                    // which made a rejected write look like it had half worked.
                    selected={markedDays}
                    onSelect={() => {}}
                    month={month}
                    onMonthChange={setMonth}
                    onDayClick={handleDayClick}
                    modifiers={{ unavailable: markedDays }}
                    modifiersClassNames={{ unavailable: 'rdp-day-unavailable' }}
                    disabled={disabled}
                />
            </div>

            {/* The dates they have marked off */}
            {unavailableDates.length > 0 && (
                <div className="space-y-2">
                    <p className="text-sm font-medium">Dates you cannot serve</p>
                    <div className="space-y-1 max-h-48 overflow-y-auto">
                        {[...unavailableDates]
                            .sort((a, b) => a.specific_date.localeCompare(b.specific_date))
                            .map(record => (
                                <div
                                    key={record.id}
                                    className="flex items-center justify-between px-3 py-2 border rounded-md text-sm"
                                >
                                    <span>
                                        {new Date(
                                            record.specific_date + 'T00:00:00'
                                        ).toLocaleDateString('en-CA', {
                                            weekday: 'short',
                                            year: 'numeric',
                                            month: 'short',
                                            day: 'numeric',
                                        })}
                                    </span>
                                    <Badge variant="destructive">Cannot serve</Badge>
                                </div>
                            ))}
                    </div>
                </div>
            )}

            {unavailableDates.length === 0 && (
                <p className="text-sm text-muted-foreground">
                    No dates marked. Every date counts as one you can serve until you tap it.
                </p>
            )}
        </div>
    )
}
