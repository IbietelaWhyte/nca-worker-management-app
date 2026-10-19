import { Award } from 'lucide-react'
import { cn } from '@/lib/utils'

/** "Ada Obi, Sam Lee" — the names as one line, skipping any lead whose worker was deleted. */
export const leadNames = leads =>
    leads
        .filter(lead => lead.worker)
        .map(lead => `${lead.worker.first_name} ${lead.worker.last_name}`)
        .join(', ')

/**
 * Who is in charge of the department this month — "Teacher of the Month: Ada Obi, Sam Lee".
 *
 * Renders nothing when the department has no title (the feature is off) or nobody is named,
 * so callers can drop it in unconditionally.
 *
 * Purple, the primary colour: it is information, not a warning. Gold is reserved for special
 * services and red for understaffing, and a month can be both. A plain block rather than
 * `Alert`, whose role="alert" would have screen readers announce it on every page load.
 */
export default function MonthlyLeadsBanner({ title, leads, className }) {
    const names = leadNames(leads ?? [])
    if (!title || !names) return null

    return (
        <div
            className={cn(
                'flex items-start gap-2 rounded-lg border border-primary/30 bg-primary/5 px-3 py-2 text-sm',
                className
            )}
        >
            <Award size={16} className="mt-0.5 shrink-0 text-primary" aria-hidden="true" />
            <p className="min-w-0">
                <span className="font-semibold">{title}:</span> {names}
            </p>
        </div>
    )
}
