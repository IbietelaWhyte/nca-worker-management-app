import { format, parseISO } from 'date-fns'
import { Badge } from '@/components/ui/badge'
import { Card, CardHeader } from '@/components/ui/card'

const relativeDay = date => {
    const days = Math.round((date - new Date().setHours(0, 0, 0, 0)) / 86400000)
    if (days === 0) return 'today'
    if (days === 1) return 'tomorrow'
    return `in ${days} days`
}

/**
 * One of the viewer's own duties.
 *
 * Read-only by design. It used to carry Confirm and Decline, mirroring the two actions the SMS
 * link offered; neither exists now. A worker who cannot make a date speaks to their head of
 * department, who edits the rota — so the card's job is to say clearly what is expected of them
 * and when, and nothing else.
 */
export default function DutyCard({ assignment }) {
    const schedule = assignment.schedules
    if (!schedule) return null

    const when = parseISO(`${schedule.scheduled_date}T00:00:00`)

    return (
        <Card>
            <CardHeader muted>
                <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline">{relativeDay(when)}</Badge>
                </div>
                <p className="text-lg font-bold tracking-tight text-foreground">
                    {format(when, 'EEEE d MMMM')}
                </p>
                <p className="text-sm text-muted-foreground">
                    <span className="font-semibold text-secondary-foreground">
                        {schedule.departments?.name ?? schedule.title}
                    </span>
                    {assignment.department_roles && ` · ${assignment.department_roles.name}`}
                    {' · '}
                    {schedule.start_time?.slice(0, 5)} – {schedule.end_time?.slice(0, 5)}
                </p>
            </CardHeader>
        </Card>
    )
}
