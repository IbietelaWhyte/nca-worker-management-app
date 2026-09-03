import { Link } from 'react-router-dom'
import { format, parseISO } from 'date-fns'
import { ChevronRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

/**
 * Everything after the next service, one line each.
 *
 * The confirmation badge follows the convention already used on the schedules table and month
 * grid — solid when everyone has confirmed, grey otherwise — with a red variant added for a rota
 * nobody has answered, which is the state that quietly becomes a Sunday morning problem.
 */
export default function UpcomingList({ entries }) {
    if (entries.length === 0) return null

    return (
        <ul className="divide-y overflow-hidden rounded-lg border">
            {entries.map(({ schedule, department, summary }) => {
                const complete = summary.total > 0 && summary.confirmed === summary.total
                const silent = summary.total > 0 && summary.confirmed === 0
                return (
                    <li key={schedule.id}>
                        <Link
                            to={`/schedules/${schedule.id}`}
                            className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-accent"
                        >
                            <span className="w-[5.5rem] shrink-0 text-xs font-semibold tabular-nums">
                                {format(
                                    parseISO(`${schedule.scheduled_date}T00:00:00`),
                                    'EEE d MMM'
                                )}
                            </span>
                            <span className="min-w-0 flex-1 truncate text-sm">
                                {department.name}
                            </span>
                            <Badge
                                variant={
                                    complete ? 'default' : silent ? 'destructive' : 'secondary'
                                }
                            >
                                {summary.confirmed}/{summary.total}
                            </Badge>
                            <ChevronRight size={15} className="shrink-0 text-muted-foreground" />
                        </Link>
                    </li>
                )
            })}
        </ul>
    )
}
