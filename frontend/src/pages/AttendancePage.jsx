import { useState } from 'react'
import { addMonths, format, parseISO, startOfMonth, subMonths } from 'date-fns'
import { ChevronLeft, ChevronRight, Download, ShieldAlert } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { useDepartments } from '@/hooks/useDepartments'
import { useAttendanceReport } from '@/hooks/useAttendanceReport'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table'
import { absenceRate, isRepeatAbsentee, toAbsenceCsv, workerName } from '@/lib/attendance'
import { downloadCsv, toCsv } from '@/lib/csv'

const RANGES = [
    { key: 'month', label: 'This month' },
    { key: 'quarter', label: 'Last 3 months' },
    { key: 'half', label: 'Last 6 months' },
]

const slug = text =>
    text
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '')

const percent = row => `${Math.round(absenceRate(row) * 100)}%`

/**
 * Who has been turning up, per department, over a window.
 *
 * Deliberately the same furniture as SchedulesPage — department selector, month arrows, an action
 * in the header — because a head who can drive that page can drive this one without being taught.
 *
 * Its own page rather than a tab on the department: nothing else there is month-scoped, and
 * DepartmentDetailPage is already long. Not on the dashboard either, which is forward-looking and
 * derives everything from schedules it has already fetched; this is a retrospective over data it
 * does not hold.
 */
export default function AttendancePage() {
    const { isAdmin, isDepartmentHead } = useAuth()
    const canManage = isAdmin || isDepartmentHead
    const { departments } = useDepartments()
    const [departmentId, setDepartmentId] = useState('')
    const { report, loading, error, range, setRange, month, setMonth, bounds } =
        useAttendanceReport(departmentId)

    // Says so rather than redirecting, like SpecialServicesPage: ProtectedRoute has no role prop,
    // and somebody who follows a link here deserves an explanation.
    if (!canManage) {
        return (
            <Alert>
                <div className="flex items-start gap-3">
                    <ShieldAlert size={18} className="mt-0.5 shrink-0 text-muted-foreground" />
                    <div>
                        <p className="text-sm font-medium">
                            Heads of department and administrators only
                        </p>
                        <p className="mt-1 text-sm text-muted-foreground">
                            Attendance is recorded and reviewed by whoever runs the rota. If you
                            think one of your duties is recorded wrongly, speak to your head of
                            department.
                        </p>
                    </div>
                </div>
            </Alert>
        )
    }

    const department = departments.find(d => d.id === departmentId)
    const rows = report?.rows ?? []
    const threshold = report?.repeat_threshold ?? 2
    const unrecorded = report ? report.services - report.services_with_attendance : 0

    const handleExport = () => {
        const { headers, rows: csvRows } = toAbsenceCsv(report)
        downloadCsv(
            `${slug(department?.name ?? 'department')}-attendance-${bounds.from}-to-${bounds.to}.csv`,
            toCsv(headers, csvRows)
        )
    }

    const label =
        range === 'month'
            ? format(month, 'MMMM yyyy')
            : `${format(parseISO(bounds.from), 'MMM')} – ${format(parseISO(bounds.to), 'MMM yyyy')}`

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h2 className="text-2xl font-bold">Attendance</h2>
                    <p className="text-sm text-muted-foreground">
                        Who has been turning up, from attendances your team has taken.
                    </p>
                </div>
                {/* A plain button, not a dialog: the table on screen is the preview, and the
                    filename comes from the department and the window. A CSV opens in a
                    spreadsheet where a head can sort and filter, which is what this data is for —
                    the rota's shareable JPEG is the right artefact for a roster, not for this. */}
                <Button variant="outline" onClick={handleExport} disabled={!rows.length}>
                    <Download size={16} className="mr-2" />
                    Export CSV
                </Button>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
                <label className="text-sm font-medium whitespace-nowrap">Department</label>
                {/* text-base below sm: iOS Safari zooms the viewport on focus under 16px. */}
                <select
                    value={departmentId}
                    onChange={e => setDepartmentId(e.target.value)}
                    className="w-full max-w-sm px-3 py-2 border rounded-md text-base sm:text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring"
                >
                    <option value="">— Select a department —</option>
                    {departments.map(d => (
                        <option key={d.id} value={d.id}>
                            {d.name}
                        </option>
                    ))}
                </select>
            </div>

            {!departmentId ? (
                <p className="text-sm text-muted-foreground">
                    Choose a department to see its attendance.
                </p>
            ) : (
                <>
                    <div className="flex flex-wrap items-center gap-2">
                        <Button
                            variant="outline"
                            size="icon-sm"
                            onClick={() => setMonth(prev => subMonths(prev, 1))}
                        >
                            <ChevronLeft size={16} />
                        </Button>
                        <span className="text-sm font-medium w-40 text-center">{label}</span>
                        <Button
                            variant="outline"
                            size="icon-sm"
                            onClick={() => setMonth(prev => addMonths(prev, 1))}
                        >
                            <ChevronRight size={16} />
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setMonth(startOfMonth(new Date()))}
                        >
                            Today
                        </Button>
                        <div className="ml-auto flex flex-wrap gap-2">
                            {RANGES.map(option => (
                                <Button
                                    key={option.key}
                                    size="sm"
                                    variant={range === option.key ? 'default' : 'outline'}
                                    onClick={() => setRange(option.key)}
                                >
                                    {option.label}
                                </Button>
                            ))}
                        </div>
                    </div>

                    {error && (
                        <Alert variant="destructive">
                            <p className="text-sm">{error}</p>
                        </Alert>
                    )}

                    {/* The honesty caveat, and it is load-bearing. Without it a month whose roll
                        call was taken twice out of twelve reads as near-perfect attendance, and
                        the first report anybody opens quietly teaches them to distrust this.
                        Warning, never destructive: nobody did anything wrong, the data is thin. */}
                    {report && unrecorded > 0 && (
                        <Alert variant="warning">
                            <p className="text-sm">
                                Attendance was taken at {report.services_with_attendance} of{' '}
                                {report.services} services in this period. The other {unrecorded}{' '}
                                {unrecorded === 1 ? 'is' : 'are'} not counted here.
                            </p>
                        </Alert>
                    )}

                    {loading ? (
                        <div className="flex items-center justify-center h-40">
                            <p className="text-muted-foreground">Loading attendance...</p>
                        </div>
                    ) : rows.length === 0 ? (
                        <p className="text-sm text-muted-foreground">
                            Nothing recorded for this period yet. Open a past service and take the
                            attendance to start.
                        </p>
                    ) : (
                        <>
                            <div className="hidden border rounded-lg overflow-hidden md:block">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Worker</TableHead>
                                            <TableHead className="text-right">Recorded</TableHead>
                                            <TableHead className="text-right">Here</TableHead>
                                            <TableHead className="text-right">Late</TableHead>
                                            <TableHead className="text-right">Absent</TableHead>
                                            <TableHead className="text-right">Excused</TableHead>
                                            <TableHead className="text-right">
                                                Not recorded
                                            </TableHead>
                                            <TableHead className="text-right">Rate</TableHead>
                                            <TableHead>Last absence</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {rows.map(row => (
                                            <TableRow key={row.worker_id}>
                                                <TableCell className="font-medium">
                                                    <span className="flex flex-wrap items-center gap-2">
                                                        {workerName(row)}
                                                        {isRepeatAbsentee(row, threshold) && (
                                                            <Badge variant="destructive">
                                                                Needs a word
                                                            </Badge>
                                                        )}
                                                    </span>
                                                </TableCell>
                                                <TableCell className="text-right">
                                                    {row.duties}
                                                </TableCell>
                                                <TableCell className="text-right">
                                                    {row.present}
                                                </TableCell>
                                                <TableCell className="text-right">
                                                    {row.late}
                                                </TableCell>
                                                <TableCell className="text-right">
                                                    {row.absences}
                                                </TableCell>
                                                <TableCell className="text-right">
                                                    {row.excused}
                                                </TableCell>
                                                <TableCell className="text-right text-muted-foreground">
                                                    {row.not_recorded}
                                                </TableCell>
                                                <TableCell className="text-right">
                                                    {percent(row)}
                                                </TableCell>
                                                <TableCell className="text-muted-foreground">
                                                    {row.last_absent_on
                                                        ? format(
                                                              parseISO(row.last_absent_on),
                                                              'd MMM'
                                                          )
                                                        : '—'}
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>

                            {/* Below md the nine-column table becomes a card per worker. Email,
                                "not recorded" and the rate drop out; the four figures that drive
                                a conversation stay. */}
                            <ul className="space-y-2 md:hidden">
                                {rows.map(row => (
                                    <li key={row.worker_id} className="rounded-lg border p-4">
                                        <div className="flex items-start justify-between gap-3">
                                            <p className="min-w-0 truncate font-medium">
                                                {workerName(row)}
                                            </p>
                                            {isRepeatAbsentee(row, threshold) && (
                                                <Badge variant="destructive">Needs a word</Badge>
                                            )}
                                        </div>
                                        <div className="mt-3 flex flex-wrap gap-4 text-sm">
                                            <span>
                                                <span className="font-medium">{row.absences}</span>
                                                <span className="text-muted-foreground">
                                                    {' '}
                                                    absent of {row.duties}
                                                </span>
                                            </span>
                                            {row.late > 0 && (
                                                <span>
                                                    <span className="font-medium">{row.late}</span>
                                                    <span className="text-muted-foreground">
                                                        {' '}
                                                        late
                                                    </span>
                                                </span>
                                            )}
                                            {row.excused > 0 && (
                                                <span className="text-muted-foreground">
                                                    {row.excused} excused
                                                </span>
                                            )}
                                        </div>
                                    </li>
                                ))}
                            </ul>
                        </>
                    )}
                </>
            )}
        </div>
    )
}
