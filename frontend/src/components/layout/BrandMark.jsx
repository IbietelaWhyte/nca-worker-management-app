import { cn } from '@/lib/utils'

/**
 * The church wordmark, for the pages that sit outside the app shell — sign in, password reset,
 * and the two public pages a worker opens from an SMS link. Those last two are often somebody's
 * first sight of the app, so they need to say who is asking before they ask anything.
 *
 * The sidebar carries the white variant directly; it sits on purple rather than on a card.
 */
export default function BrandMark({ className }) {
    return (
        <img
            src="/nca-logo.png"
            alt="New Covenant Assembly"
            width={752}
            height={214}
            className={cn('h-auto w-44', className)}
        />
    )
}
