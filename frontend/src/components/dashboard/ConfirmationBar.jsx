import { cn } from '@/lib/utils'

/**
 * One segment per assigned worker, rather than a percentage bar.
 *
 * At four people "three green, one grey" reads faster than "75%", and it shows the shape of the
 * problem — a decline is a different situation from a missing reply, and a percentage hides that.
 */
export default function ConfirmationBar({ summary, className }) {
    const { confirmed, declined, pending, total } = summary
    if (total === 0) return null

    const segments = [
        ...Array(confirmed).fill('bg-success'),
        ...Array(pending).fill('bg-border'),
        ...Array(declined).fill('bg-destructive'),
    ]

    return (
        // Capped: stretched across a full-width card, four segments read as four slabs rather than
        // a bar you can take in at a glance.
        <div className={cn('max-w-xs space-y-1.5', className)}>
            <div
                className="flex gap-1"
                role="img"
                aria-label={`${confirmed} of ${total} confirmed${declined > 0 ? `, ${declined} declined` : ''}`}
            >
                {segments.map((tone, i) => (
                    <span key={i} className={cn('h-1.5 flex-1 rounded-full', tone)} />
                ))}
            </div>
            <p className="text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">
                    {confirmed} of {total}
                </span>{' '}
                confirmed
                {declined > 0 && ` · ${declined} declined`}
                {pending > 0 && ` · ${pending} waiting`}
            </p>
        </div>
    )
}
