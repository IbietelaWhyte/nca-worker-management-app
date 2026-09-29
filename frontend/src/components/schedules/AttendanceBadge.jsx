import { Badge } from '@/components/ui/badge'
import { ABSENT, EXCUSED, LATE, PRESENT, attendanceState } from '@/lib/attendance'

// One place, so the row, the tally and the report cannot drift on what "late" looks like.
//
// Gold for late and red only for absent: they turned up, and a badge that reads the same as an
// empty chair would say something untrue about them. Same reasoning as a special date never
// being red — see the theming notes in CLAUDE.md.
const LABELS = {
    [PRESENT]: { variant: 'success', text: 'Here' },
    [LATE]: { variant: 'warning', text: 'Late' },
    [ABSENT]: { variant: 'destructive', text: 'Absent' },
    [EXCUSED]: { variant: 'secondary', text: 'Excused' },
}

/**
 * What one row's attendance says, or nothing at all.
 *
 * Renders nothing while the state is NOT_RECORDED, which is deliberate: an empty cell reads as
 * "nobody has said", where any badge would imply somebody decided.
 */
export default function AttendanceBadge({ assignment, className }) {
    const entry = LABELS[attendanceState(assignment)]
    if (!entry) return null

    return (
        <Badge variant={entry.variant} className={className}>
            {entry.text}
            {entry.text === 'Late' && assignment.minutes_late ? ` ${assignment.minutes_late}m` : ''}
        </Badge>
    )
}
