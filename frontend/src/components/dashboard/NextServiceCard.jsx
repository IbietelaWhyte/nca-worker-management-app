import { useState } from 'react'
import { Link } from 'react-router-dom'
import { format, parseISO } from 'date-fns'
import { Bell } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card'
import { triggerRemindersForSchedule } from '@/api/schedules'
import ConfirmationBar from './ConfirmationBar'

const STATUS_LABEL = {
    confirmed: { text: 'Confirmed', className: 'text-success font-medium' },
    declined: { text: 'Declined', className: 'text-destructive font-medium' },
    pending: { text: 'No reply', className: 'text-muted-foreground' },
}

const relativeDay = days => {
    if (days === 0) return 'today'
    if (days === 1) return 'tomorrow'
    return `in ${days} days`
}

// Surnames first, matching the printed rota and `lib/rota.js`.
const bySurname = (a, b) =>
    (a.workers?.last_name ?? '').localeCompare(b.workers?.last_name ?? '') ||
    (a.workers?.first_name ?? '').localeCompare(b.workers?.first_name ?? '')

/**
 * The soonest service, expanded: who is on, and who still owes an answer.
 *
 * This is the thing a head of department checks on the way to church, so it keeps its roster at
 * every width rather than collapsing to a count on a phone.
 */
export default function NextServiceCard({ entry }) {
    const { schedule, department, summary, daysAway } = entry
    const [sending, setSending] = useState(false)
    const [sent, setSent] = useState(false)

    const assignments = (schedule.schedule_assignments ?? []).slice().sort(bySurname)

    const handleRemind = async () => {
        setSending(true)
        try {
            await triggerRemindersForSchedule(schedule.id)
            setSent(true)
        } catch {
            // The reminder job retries on its own schedule, so a failure here is not worth an
            // alert — the button simply stays available.
        } finally {
            setSending(false)
        }
    }

    return (
        <Card>
            <CardHeader muted>
                <div className="flex flex-wrap items-center gap-2">
                    <Badge>Next</Badge>
                    <Badge variant="outline">{relativeDay(daysAway)}</Badge>
                    {summary.declined > 0 && (
                        <Badge variant="destructive">
                            {summary.declined === 1 ? 'One short' : `${summary.declined} short`}
                        </Badge>
                    )}
                </div>
                <p className="text-lg font-bold tracking-tight text-foreground">
                    {format(parseISO(`${schedule.scheduled_date}T00:00:00`), 'EEEE d MMMM')}
                </p>
                <p className="text-sm text-muted-foreground">
                    <span className="font-semibold text-secondary-foreground">
                        {department.name}
                    </span>
                    {' · '}
                    {schedule.title}
                    {' · '}
                    {schedule.start_time?.slice(0, 5)} – {schedule.end_time?.slice(0, 5)}
                </p>
                <ConfirmationBar summary={summary} className="mt-2" />
            </CardHeader>

            <CardContent className="p-0">
                <ul className="divide-y">
                    {assignments.map(assignment => {
                        const status = STATUS_LABEL[assignment.status] ?? STATUS_LABEL.pending
                        return (
                            <li key={assignment.id} className="flex items-center gap-3 px-4 py-2.5">
                                <div className="min-w-0 flex-1">
                                    <p className="truncate text-sm font-medium">
                                        {assignment.workers
                                            ? `${assignment.workers.first_name} ${assignment.workers.last_name}`
                                            : 'Unknown worker'}
                                    </p>
                                    {assignment.department_roles && (
                                        <p className="truncate text-xs text-muted-foreground">
                                            {assignment.department_roles.name}
                                        </p>
                                    )}
                                </div>
                                <span className={`shrink-0 text-xs ${status.className}`}>
                                    {status.text}
                                </span>
                            </li>
                        )
                    })}
                </ul>
            </CardContent>

            <CardFooter>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRemind}
                    disabled={sending || sent || summary.pending === 0}
                >
                    <Bell size={14} className="mr-2" />
                    {sent ? 'Reminder sent' : sending ? 'Sending…' : 'Send reminder'}
                </Button>
                <Link to={`/schedules/${schedule.id}`} className={buttonVariants({ size: 'sm' })}>
                    Open rota
                </Link>
            </CardFooter>
        </Card>
    )
}
