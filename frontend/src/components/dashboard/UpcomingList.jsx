import { Link } from 'react-router-dom'
import { format, parseISO } from 'date-fns'
import { ChevronRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

/**
 * Everything after the next service, one line each.
 *
 * The badge is how many people are on the rota, matching the schedules table and the month grid.
 * It reads as a bare count until the app knows what each department asked for; once a schedule
 * carries its own smallest and largest numbers, this is where "short" gets said.
 */
export default function UpcomingList({ entries }) {
    if (entries.length === 0) return null

    return (
        <ul className="divide-y overflow-hidden rounded-lg border">
            {entries.map(({ schedule, department, summary }) => (
                <li key={schedule.id}>
                    <Link
                        to={`/schedules/${schedule.id}`}
                        className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-accent"
                    >
                        <span className="w-[5.5rem] shrink-0 text-xs font-semibold tabular-nums">
                            {format(parseISO(`${schedule.scheduled_date}T00:00:00`), 'EEE d MMM')}
                        </span>
                        <span className="min-w-0 flex-1 truncate text-sm">{department.name}</span>
                        <Badge variant="secondary">{summary.assigned}</Badge>
                        <ChevronRight size={15} className="shrink-0 text-muted-foreground" />
                    </Link>
                </li>
            ))}
        </ul>
    )
}
