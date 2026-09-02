import {
    eachDayOfInterval,
    endOfMonth,
    endOfWeek,
    format,
    isSameDay,
    isSameMonth,
    startOfMonth,
    startOfWeek,
} from 'date-fns'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

const statusSummary = assignments => {
    const list = assignments ?? []
    return { confirmed: list.filter(a => a.status === 'confirmed').length, total: list.length }
}

/**
 * A month grid of a department's schedules.
 *
 * Hand-rolled with `grid grid-cols-7` rather than the shared `ui/calendar` component, because
 * day cells need to hold several worker names rather than a single date.
 */
export default function MonthCalendar({ month, schedules, onDayClick }) {
    // Pad out to whole weeks so the grid always starts on a Sunday and ends on a Saturday.
    const days = eachDayOfInterval({
        start: startOfWeek(startOfMonth(month)),
        end: endOfWeek(endOfMonth(month)),
    })

    // Bucket by date string — schedules carry yyyy-MM-dd, and parsing every one per cell
    // would be wasteful.
    const byDate = {}
    for (const schedule of schedules ?? []) {
        ;(byDate[schedule.scheduled_date] ??= []).push(schedule)
    }

    const today = new Date()

    // overflow-x-auto, not hidden: the seven columns need ~364px, and `hidden` simply clipped
    // Friday and Saturday with no way to reach them.
    return (
        <div className="overflow-x-auto rounded-lg border">
            <div className="min-w-[24rem]">
                <div className="grid grid-cols-7 border-b bg-muted/50">
                    {WEEKDAYS.map(day => (
                        <div
                            key={day}
                            className="px-2 py-2 text-xs font-medium text-muted-foreground text-center"
                        >
                            {day}
                        </div>
                    ))}
                </div>

                <div className="grid grid-cols-7">
                    {days.map(day => {
                        const dateStr = format(day, 'yyyy-MM-dd')
                        const daySchedules = byDate[dateStr] ?? []
                        const inMonth = isSameMonth(day, month)

                        return (
                            <div
                                key={dateStr}
                                className={cn(
                                    'min-h-[6.5rem] border-b border-r p-1.5 [&:nth-child(7n)]:border-r-0',
                                    !inMonth && 'bg-muted/30'
                                )}
                            >
                                <div
                                    className={cn(
                                        'text-xs mb-1 flex items-center justify-center w-6 h-6 rounded-full',
                                        !inMonth && 'text-muted-foreground/50',
                                        isSameDay(day, today) &&
                                            'bg-primary text-primary-foreground font-semibold'
                                    )}
                                >
                                    {format(day, 'd')}
                                </div>

                                <div className="space-y-1">
                                    {daySchedules.map(schedule => {
                                        const { confirmed, total } = statusSummary(
                                            schedule.schedule_assignments
                                        )
                                        return (
                                            <button
                                                key={schedule.id}
                                                type="button"
                                                onClick={() => onDayClick?.(schedule)}
                                                className="w-full text-left rounded border bg-background px-1.5 py-1 hover:bg-accent transition-colors"
                                            >
                                                <p className="text-xs font-medium truncate">
                                                    {schedule.title}
                                                </p>
                                                <div className="flex items-center gap-1 mt-0.5">
                                                    <Badge
                                                        variant={
                                                            total > 0 && confirmed === total
                                                                ? 'default'
                                                                : 'secondary'
                                                        }
                                                    >
                                                        {confirmed}/{total}
                                                    </Badge>
                                                    <span className="text-[10px] text-muted-foreground">
                                                        {schedule.start_time?.slice(0, 5)}
                                                    </span>
                                                </div>
                                            </button>
                                        )
                                    })}
                                </div>
                            </div>
                        )
                    })}
                </div>
            </div>
        </div>
    )
}
