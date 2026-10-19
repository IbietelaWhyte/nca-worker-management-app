import { AlertTriangle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

// One place, so the list, the cards, the month grid and the detail page cannot drift on what
// "understaffed" looks like.
//
// Red, like the count it sits beside, and never gold: gold means a special service, and a date
// can be both — see the theming notes in CLAUDE.md. The triangle matches MonthPreviewTable's
// understaffed status, so a saved rota reads like the plan it came from.

/**
 * Says a schedule is below its minimum, and by how many.
 *
 * The caller decides whether to render it (from `summarizeStaffing(schedule).understaffed`), as
 * with every other conditional badge. `compact` is for the month grid, whose day cells have no
 * room for the words: it keeps the icon and the number and moves the label into a tooltip and
 * screen-reader text.
 *
 * @param {{short: number, compact?: boolean, className?: string}} props
 */
export default function UnderstaffedBadge({ short, compact = false, className }) {
    if (compact) {
        return (
            <Badge
                variant="destructive"
                className={className}
                title={`Understaffed: ${short} short`}
            >
                <AlertTriangle />
                <span className="sr-only">Understaffed:</span>
                {short}
                <span className="sr-only">short</span>
            </Badge>
        )
    }

    return (
        <Badge variant="destructive" className={className}>
            <AlertTriangle />
            Understaffed · {short} short
        </Badge>
    )
}
