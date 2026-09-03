import { useState } from 'react'
import { format, parseISO } from 'date-fns'
import { Check } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardFooter, CardHeader } from '@/components/ui/card'

const relativeDay = date => {
    const days = Math.round((date - new Date().setHours(0, 0, 0, 0)) / 86400000)
    if (days === 0) return 'today'
    if (days === 1) return 'tomorrow'
    return `in ${days} days`
}

/**
 * One of the viewer's own duties.
 *
 * A duty they have not answered gets Confirm and Decline inline — the same two actions the SMS
 * link offers, so somebody already signed in does not have to go and find the text message.
 */
export default function DutyCard({ assignment, onAnswer }) {
    const [busy, setBusy] = useState(null)
    const schedule = assignment.schedules
    if (!schedule) return null

    const when = parseISO(`${schedule.scheduled_date}T00:00:00`)
    const pending = assignment.status === 'pending'

    const answer = async status => {
        setBusy(status)
        try {
            await onAnswer(assignment.id, status)
        } finally {
            setBusy(null)
        }
    }

    return (
        <Card>
            <CardHeader muted={!pending} className={pending ? 'bg-warning/15' : undefined}>
                <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline">{relativeDay(when)}</Badge>
                    {pending ? (
                        <Badge variant="warning">Needs your reply</Badge>
                    ) : (
                        <Badge variant="success">You confirmed</Badge>
                    )}
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

            <CardFooter>
                <Button
                    variant="outline"
                    size="sm"
                    disabled={busy !== null}
                    onClick={() => answer('declined')}
                >
                    {busy === 'declined' ? 'Saving…' : pending ? 'Decline' : "Can't make it"}
                </Button>
                {pending && (
                    <Button size="sm" disabled={busy !== null} onClick={() => answer('confirmed')}>
                        <Check size={14} className="mr-2" />
                        {busy === 'confirmed' ? 'Saving…' : 'Confirm'}
                    </Button>
                )}
            </CardFooter>
        </Card>
    )
}
