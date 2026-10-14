import { ChevronLeft, ChevronRight } from 'lucide-react'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

/**
 * "Showing 26–50 of 132" with Previous / Next. Renders nothing when everything fits on one page.
 * The buttons are min-h-11 (44px) because no Button size reaches the touch-target minimum alone.
 */
function Pagination({ page, pageSize, total, onPageChange, className }) {
    if (!total || total <= pageSize) return null

    const pageCount = Math.ceil(total / pageSize)
    const first = (page - 1) * pageSize + 1
    const last = Math.min(page * pageSize, total)

    return (
        <nav
            aria-label="Pagination"
            className={cn('flex flex-wrap items-center justify-between gap-3', className)}
        >
            <p className="text-sm text-muted-foreground">
                Showing {first}–{last} of {total}
            </p>
            <div className="flex items-center gap-2">
                <Button
                    variant="outline"
                    className="min-h-11"
                    disabled={page <= 1}
                    onClick={() => onPageChange(page - 1)}
                >
                    <ChevronLeft size={16} />
                    Previous
                </Button>
                <span className="text-sm tabular-nums text-muted-foreground">
                    {page} / {pageCount}
                </span>
                <Button
                    variant="outline"
                    className="min-h-11"
                    disabled={page >= pageCount}
                    onClick={() => onPageChange(page + 1)}
                >
                    Next
                    <ChevronRight size={16} />
                </Button>
            </div>
        </nav>
    )
}

export { Pagination }
