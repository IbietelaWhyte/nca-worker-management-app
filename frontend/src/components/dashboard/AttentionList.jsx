import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

// Severity reads as a dot rather than a coloured card: three tinted panels stacked would shout,
// and most of these are nudges, not alarms.
const DOT = {
    high: 'bg-destructive',
    medium: 'bg-warning',
    low: 'bg-muted-foreground',
}

export default function AttentionList({ items }) {
    if (items.length === 0) return null

    return (
        <ul className="space-y-2">
            {items.map(item => (
                <li key={item.id}>
                    <Link
                        to={item.href}
                        className="flex items-start gap-3 rounded-lg border p-3 transition-colors hover:bg-muted"
                    >
                        <span
                            className={cn(
                                'mt-1.5 size-2 shrink-0 rounded-full',
                                DOT[item.severity]
                            )}
                        />
                        <span className="min-w-0 flex-1">
                            <span className="block text-sm font-medium">{item.title}</span>
                            <span className="block text-xs text-muted-foreground">
                                {item.detail}
                            </span>
                        </span>
                        <ChevronRight size={15} className="mt-0.5 shrink-0 text-muted-foreground" />
                    </Link>
                </li>
            ))}
        </ul>
    )
}
