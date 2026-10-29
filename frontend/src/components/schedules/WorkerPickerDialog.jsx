import { useMemo, useState } from 'react'
import { format } from 'date-fns'
import { Search } from 'lucide-react'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'

// Parsed from local date parts: a bare yyyy-MM-dd is read as UTC and renders a day early west
// of Greenwich.
const shortDate = dateStr => format(new Date(dateStr + 'T00:00:00'), 'd MMM')

/**
 * "Last on 12 Oct · next 9 Nov · 1 this month", or "Not scheduled before". The question a head
 * is asking while swapping is whether this person has been on recently, so the answer sits under
 * their name, and the server already lists the fairest first.
 */
const describeRecent = ({ last_scheduled, next_scheduled, month_count }) => {
    const parts = []
    parts.push(last_scheduled ? `Last on ${shortDate(last_scheduled)}` : 'Not scheduled before')
    if (next_scheduled) parts.push(`next ${shortDate(next_scheduled)}`)
    if (month_count) parts.push(`${month_count} this month`)
    return parts.join(' · ')
}

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
 * @param {Array<{worker: {id: string, first_name: string, last_name: string, email?: string},
 *   subteam: {id: string, name: string}|null, last_scheduled: string|null,
 *   next_scheduled: string|null, month_count: number}>} props.candidates - As the server resolved
 *   them, fairest first: fewest dates this month, then longest since they last served.
 *   `subteam` is the group this person would actually land in, not a guess: it comes from the
 *   same call that stamps it. A head picks a person and the rota decides the group, so the
 *   group has to be on screen at the moment they pick.
 * @param {boolean} props.loading - True while the candidate list is being fetched.
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
    loading = false,
    busy = false,
    error = null,
    onPick,
}) {
    const [query, setQuery] = useState('')

    const matches = useMemo(() => {
        const needle = query.trim().toLowerCase()
        if (!needle) return candidates
        // Subteam is searchable too: on a whole-department rota "seekers" is the fastest way
        // to narrow sixty people to the group you are actually short in.
        return candidates.filter(({ worker, subteam }) =>
            `${worker.first_name} ${worker.last_name} ${worker.email ?? ''} ${subteam?.name ?? ''}`
                .toLowerCase()
                .includes(needle)
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

                {loading ? (
                    <p className="py-6 text-center text-sm text-muted-foreground">
                        Loading the roster...
                    </p>
                ) : candidates.length === 0 ? (
                    <Alert>
                        <p className="text-sm">Everybody on this roster is already on the rota.</p>
                    </Alert>
                ) : matches.length === 0 ? (
                    <p className="py-6 text-center text-sm text-muted-foreground">
                        Nobody matches “{query}”.
                    </p>
                ) : (
                    <ul className="max-h-72 space-y-1 overflow-y-auto">
                        {matches.map(candidate => {
                            const { worker, subteam } = candidate
                            return (
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
                                        <span className="min-w-0 flex-1">
                                            <span className="block truncate text-sm font-medium">
                                                {worker.first_name} {worker.last_name}
                                            </span>
                                            <span className="block truncate text-xs text-muted-foreground">
                                                {describeRecent(candidate)}
                                            </span>
                                        </span>
                                        {/* Where they land. Outside the truncating column so the
                                        dates line cannot squeeze it out — this is the fact the
                                        head is choosing on. */}
                                        <Badge variant="secondary" className="shrink-0">
                                            {subteam?.name ?? 'No subteam'}
                                        </Badge>
                                    </button>
                                </li>
                            )
                        })}
                    </ul>
                )}
            </DialogContent>
        </Dialog>
    )
}
