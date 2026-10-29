import { useEffect, useState } from 'react'
import { format } from 'date-fns'
import { Download, History } from 'lucide-react'
import { getWorkerAssignments } from '@/api/schedules'
import { downloadCsv, slug, toCsv } from '@/lib/csv'
import { summarizeHistory, toHistoryCsv } from '@/lib/workerExport'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'

// Parsed from local date parts: a bare yyyy-MM-dd is read as UTC and renders a day early west
// of Greenwich.
const readable = dateStr => format(new Date(dateStr + 'T00:00:00'), 'EEE d MMM yyyy')

/**
 * When somebody has served, for checking that scheduling is fair: how many times in a year, when
 * they last served and when they are next on, with every date and a CSV to keep.
 *
 * Reads the worker's own duty list, which is finalized rotas only - a draft has not been
 * announced, so it is not something they have been asked to do yet. It covers every department
 * they serve in, so a head can see somebody who is busy elsewhere.
 */
export default function WorkerHistoryDialog({ worker, open, onOpenChange }) {
    const [assignments, setAssignments] = useState([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const [year, setYear] = useState(() => new Date().getFullYear())

    const workerId = worker?.id

    useEffect(() => {
        if (!open || !workerId) return
        let cancelled = false
        setLoading(true)
        setError(null)
        setYear(new Date().getFullYear())
        getWorkerAssignments(workerId)
            .then(response => {
                if (!cancelled) setAssignments(response.data)
            })
            .catch(() => {
                if (!cancelled) setError("Could not load this worker's schedule history.")
            })
            .finally(() => {
                if (!cancelled) setLoading(false)
            })
        return () => {
            cancelled = true
        }
    }, [open, workerId])

    if (!worker) return null

    const name = `${worker.first_name} ${worker.last_name}`
    const today = format(new Date(), 'yyyy-MM-dd')
    const { rows, count, lastServed, next, years } = summarizeHistory(assignments, year, today)
    const yearOptions = [...new Set([new Date().getFullYear(), ...years])].sort((a, b) => b - a)

    const handleExport = () => {
        const { headers, rows: csvRows } = toHistoryCsv(rows, today)
        downloadCsv(`${slug(name)}-schedule-${year}.csv`, toCsv(headers, csvRows))
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-lg">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <History size={18} />
                        Schedule history for {name}
                    </DialogTitle>
                    <DialogDescription>
                        Published rotas in every department they serve in. Drafts are not included.
                    </DialogDescription>
                </DialogHeader>

                {error && (
                    <Alert variant="destructive">
                        <AlertDescription>{error}</AlertDescription>
                    </Alert>
                )}

                {loading ? (
                    <p className="py-6 text-center text-sm text-muted-foreground">Loading...</p>
                ) : (
                    <div className="space-y-4">
                        <div className="grid grid-cols-3 gap-2 rounded-md border p-3 text-center">
                            <div>
                                <p className="text-2xl font-bold">{count}</p>
                                <p className="text-xs text-muted-foreground">in {year}</p>
                            </div>
                            <div>
                                <p className="text-sm font-medium">
                                    {lastServed ? readable(lastServed) : 'Never'}
                                </p>
                                <p className="text-xs text-muted-foreground">Last served</p>
                            </div>
                            <div>
                                <p className="text-sm font-medium">
                                    {next ? readable(next) : 'Nothing booked'}
                                </p>
                                <p className="text-xs text-muted-foreground">Next on</p>
                            </div>
                        </div>

                        <div className="flex flex-wrap items-center justify-between gap-2">
                            {/* text-base below sm: iOS zooms the page on focus under 16px. */}
                            <select
                                aria-label="Year"
                                value={year}
                                onChange={e => setYear(Number(e.target.value))}
                                className="rounded-md border bg-background px-3 py-2 text-base sm:text-sm"
                            >
                                {yearOptions.map(y => (
                                    <option key={y} value={y}>
                                        {y}
                                    </option>
                                ))}
                            </select>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handleExport}
                                disabled={rows.length === 0}
                            >
                                <Download size={14} className="mr-1.5" />
                                Export CSV
                            </Button>
                        </div>

                        {rows.length === 0 ? (
                            <p className="py-4 text-center text-sm text-muted-foreground">
                                Not scheduled in {year}.
                            </p>
                        ) : (
                            <ul className="max-h-72 space-y-1 overflow-y-auto">
                                {rows.map(a => (
                                    <li
                                        key={a.id}
                                        className="flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm"
                                    >
                                        <div className="min-w-0">
                                            <p className="font-medium">
                                                {readable(a.schedules.scheduled_date)}
                                            </p>
                                            <p className="truncate text-xs text-muted-foreground">
                                                {[
                                                    a.schedules.departments?.name,
                                                    a.department_roles?.name,
                                                    a.schedules.special_service_name,
                                                ]
                                                    .filter(Boolean)
                                                    .join(' · ')}
                                            </p>
                                        </div>
                                        {a.schedules.scheduled_date > today && (
                                            <Badge variant="secondary">Upcoming</Badge>
                                        )}
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                )}
            </DialogContent>
        </Dialog>
    )
}
