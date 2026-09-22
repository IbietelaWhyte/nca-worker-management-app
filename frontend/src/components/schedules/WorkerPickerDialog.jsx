import { useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import { Alert } from '@/components/ui/alert'
import { Input } from '@/components/ui/input'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'

/**
 * Pick a worker from a department or subteam roster.
 *
 * A filtered scrollable list rather than a `Select`: `select.jsx` has no typeahead and a
 * department runs to sixty people, so scrolling one is unusable on a phone. It is also not a
 * new `cmdk` combobox — the list-with-filter is a few lines on top of a Dialog, which this
 * codebase already has twice.
 *
 * **It does not filter by availability or leave.** That logic lives in `ScheduleService`, and a
 * second copy in JavaScript would drift from it within a release. The server allows the pick
 * and hands back a warning instead, which the page shows after the fact — a head moving
 * somebody onto a date they marked off has usually already spoken to them.
 *
 * One instance is owned by the page rather than one per row, following the add-member dialog
 * on `DepartmentDetailPage`.
 *
 * @param {object} props
 * @param {boolean} props.open
 * @param {(open: boolean) => void} props.onOpenChange
 * @param {string} props.title
 * @param {string} props.description - What picking somebody will do, including who gets texted.
 * @param {Array<{id: string, first_name: string, last_name: string, email?: string}>} props.candidates
 * @param {boolean} props.busy - True while a pick is in flight; the list locks rather than closing.
 * @param {string|null} props.error - Why the last pick was refused. Shown here rather than on
 *   the page behind, which the dialog covers.
 * @param {(workerId: string) => void} props.onPick
 */
export default function WorkerPickerDialog({
    open,
    onOpenChange,
    title,
    description,
    candidates = [],
    busy = false,
    error = null,
    onPick,
}) {
    const [query, setQuery] = useState('')

    const matches = useMemo(() => {
        const needle = query.trim().toLowerCase()
        if (!needle) return candidates
        return candidates.filter(c =>
            `${c.first_name} ${c.last_name} ${c.email ?? ''}`.toLowerCase().includes(needle)
        )
    }, [candidates, query])

    const handleOpenChange = next => {
        if (busy) return
        if (!next) setQuery('')
        onOpenChange(next)
    }

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>{title}</DialogTitle>
                    <DialogDescription>{description}</DialogDescription>
                </DialogHeader>

                <div className="relative">
                    <Search
                        size={16}
                        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                    />
                    <Input
                        value={query}
                        onChange={e => setQuery(e.target.value)}
                        placeholder="Search by name or email"
                        className="pl-9"
                        autoFocus
                    />
                </div>

                {error && (
                    <Alert variant="destructive">
                        <p className="text-sm">{error}</p>
                    </Alert>
                )}

                {candidates.length === 0 ? (
                    <Alert>
                        <p className="text-sm">Everybody on this roster is already on the rota.</p>
                    </Alert>
                ) : matches.length === 0 ? (
                    <p className="py-6 text-center text-sm text-muted-foreground">
                        Nobody matches “{query}”.
                    </p>
                ) : (
                    <ul className="max-h-72 space-y-1 overflow-y-auto">
                        {matches.map(worker => (
                            <li key={worker.id}>
                                <button
                                    type="button"
                                    disabled={busy}
                                    onClick={() => onPick(worker.id)}
                                    className="flex w-full items-center gap-3 rounded-md p-2 text-left hover:bg-muted disabled:opacity-50"
                                >
                                    <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium">
                                        {worker.first_name[0]}
                                        {worker.last_name[0]}
                                    </span>
                                    <span className="min-w-0">
                                        <span className="block truncate text-sm font-medium">
                                            {worker.first_name} {worker.last_name}
                                        </span>
                                        {worker.email && (
                                            <span className="block truncate text-xs text-muted-foreground">
                                                {worker.email}
                                            </span>
                                        )}
                                    </span>
                                </button>
                            </li>
                        ))}
                    </ul>
                )}
            </DialogContent>
        </Dialog>
    )
}
