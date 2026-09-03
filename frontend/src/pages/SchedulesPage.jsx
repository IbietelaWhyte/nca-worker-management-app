import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDepartments } from '@/hooks/useDepartments'
import { useSchedules } from '@/hooks/useSchedules'
import { useAuth } from '@/context/AuthContext'
import GenerateScheduleForm from '@/components/schedules/GenerateScheduleForm'
import GenerateMonthDialog from '@/components/schedules/GenerateMonthDialog'
import RotaExportDialog from '@/components/schedules/RotaExportDialog'
import MonthCalendar from '@/components/schedules/MonthCalendar'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert } from '@/components/ui/alert'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table'
import {
    Plus,
    ChevronLeft,
    ChevronRight,
    Trash2,
    Calendar,
    CalendarRange,
    ImageDown,
} from 'lucide-react'
import { addMonths, format, startOfMonth, subMonths } from 'date-fns'

const STATUS_SUMMARY = schedule_assignments => {
    const confirmed = (schedule_assignments ?? []).filter(a => a.status === 'confirmed').length
    const total = (schedule_assignments ?? []).length
    return { confirmed, total }
}

export default function SchedulesPage() {
    const navigate = useNavigate()
    const { isAdmin, isDepartmentHead, role } = useAuth()
    const { departments } = useDepartments()
    const [selectedDepartmentId, setSelectedDepartmentId] = useState('')
    const [generateOpen, setGenerateOpen] = useState(false)
    const [generateMonthOpen, setGenerateMonthOpen] = useState(false)
    const [exportOpen, setExportOpen] = useState(false)

    // For assistant_hod users, auto-select first department if only one available
    const isAssistantHod = role === 'assistant_hod'

    // Auto-select department for assistant_hod if they only have one
    useEffect(() => {
        if (isAssistantHod && departments.length === 1 && !selectedDepartmentId) {
            setSelectedDepartmentId(departments[0].id)
        }
    }, [departments, isAssistantHod, selectedDepartmentId])

    const {
        schedules,
        loading,
        error,
        month,
        setMonth,
        refetch,
        createSchedule,
        previewMonth,
        commitMonth,
        removeSchedule,
    } = useSchedules(selectedDepartmentId)

    const selectedDepartment = departments.find(d => d.id === selectedDepartmentId)

    const handleGenerate = async formData => {
        await createSchedule(formData)
        setGenerateOpen(false)
    }

    const handleMonthDone = () => {
        setGenerateMonthOpen(false)
        // The commit may have landed in a different month than the one on screen.
        refetch()
    }

    const handleDelete = async schedule => {
        if (!confirm(`Delete "${schedule.title}"? This cannot be undone.`)) return
        await removeSchedule(schedule.id)
    }

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h2 className="text-2xl font-bold">Schedules</h2>
                    <p className="text-muted-foreground text-sm mt-1">
                        Generate and manage service schedules by department
                    </p>
                </div>
                {(isAdmin || isDepartmentHead) && selectedDepartmentId && (
                    <div className="flex flex-wrap gap-2">
                        <Button variant="outline" onClick={() => setExportOpen(true)}>
                            <ImageDown size={16} className="mr-2" />
                            Export as Image
                        </Button>
                        <Button variant="outline" onClick={() => setGenerateOpen(true)}>
                            <Plus size={16} className="mr-2" />
                            Generate Schedule
                        </Button>
                        <Button onClick={() => setGenerateMonthOpen(true)}>
                            <CalendarRange size={16} className="mr-2" />
                            Generate Month
                        </Button>
                    </div>
                )}
            </div>

            {/* Department selector - dropdown for admins/HODs, tabs for assistant_hod */}
            {!isAssistantHod ? (
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
                    <label className="text-sm font-medium whitespace-nowrap">Department</label>
                    {/* text-base below sm: iOS Safari zooms the viewport on focus for any control
                        under 16px, which ui/input.jsx already avoids the same way. */}
                    <select
                        value={selectedDepartmentId}
                        onChange={e => setSelectedDepartmentId(e.target.value)}
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
            ) : (
                <div className="flex gap-2 flex-wrap">
                    {departments.map(dept => (
                        <Button
                            key={dept.id}
                            variant={selectedDepartmentId === dept.id ? 'default' : 'outline'}
                            onClick={() => setSelectedDepartmentId(dept.id)}
                            size="sm"
                        >
                            {dept.name}
                        </Button>
                    ))}
                </div>
            )}

            {/* No department selected */}
            {!selectedDepartmentId && (
                <div className="flex items-center justify-center h-48 border rounded-lg border-dashed">
                    <p className="text-muted-foreground text-sm">
                        Select a department to view its schedules
                    </p>
                </div>
            )}

            {/* Department selected — show schedules */}
            {selectedDepartmentId && (
                <>
                    {error && (
                        <Alert variant="destructive">
                            <p className="text-sm">{error}</p>
                        </Alert>
                    )}

                    {/* Month navigation — scopes both views, and bounds what is fetched */}
                    <div className="flex items-center gap-2">
                        <Button
                            variant="outline"
                            size="icon-sm"
                            onClick={() => setMonth(prev => subMonths(prev, 1))}
                        >
                            <ChevronLeft size={16} />
                        </Button>
                        <span className="text-sm font-medium w-36 text-center">
                            {format(month, 'MMMM yyyy')}
                        </span>
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
                    </div>

                    {loading && (
                        <div className="flex items-center justify-center h-40">
                            <p className="text-muted-foreground">Loading schedules...</p>
                        </div>
                    )}

                    {!loading && !error && (
                        <Tabs defaultValue="month">
                            <TabsList>
                                <TabsTrigger value="month">Month</TabsTrigger>
                                <TabsTrigger value="list">
                                    List
                                    <Badge variant="secondary" className="ml-2">
                                        {schedules.length}
                                    </Badge>
                                </TabsTrigger>
                            </TabsList>

                            <TabsContent value="month" className="mt-4">
                                <MonthCalendar
                                    month={month}
                                    schedules={schedules}
                                    onDayClick={schedule => navigate(`/schedules/${schedule.id}`)}
                                />
                            </TabsContent>

                            <TabsContent value="list" className="mt-4">
                                {schedules.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center h-48 border rounded-lg border-dashed">
                                        <Calendar
                                            size={32}
                                            className="text-muted-foreground mb-3"
                                        />
                                        <p className="text-muted-foreground text-sm">
                                            No schedules in {format(month, 'MMMM yyyy')} for{' '}
                                            {selectedDepartment?.name}
                                        </p>
                                        {(isAdmin || isDepartmentHead) && (
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                className="mt-3"
                                                onClick={() => setGenerateMonthOpen(true)}
                                            >
                                                Generate this month
                                            </Button>
                                        )}
                                    </div>
                                ) : (
                                    <div className="hidden border rounded-lg overflow-hidden md:block">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Title</TableHead>
                                                    <TableHead>Date</TableHead>
                                                    <TableHead>Time</TableHead>
                                                    <TableHead>Assignments</TableHead>
                                                    <TableHead className="text-right">
                                                        Actions
                                                    </TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {[...schedules]
                                                    .sort((a, b) =>
                                                        b.scheduled_date.localeCompare(
                                                            a.scheduled_date
                                                        )
                                                    )
                                                    .map(schedule => {
                                                        const { confirmed, total } = STATUS_SUMMARY(
                                                            schedule.schedule_assignments
                                                        )

                                                        return (
                                                            <TableRow
                                                                key={schedule.id}
                                                                className="cursor-pointer"
                                                                onClick={() =>
                                                                    navigate(
                                                                        `/schedules/${schedule.id}`
                                                                    )
                                                                }
                                                            >
                                                                <TableCell className="font-medium">
                                                                    {schedule.title}
                                                                </TableCell>
                                                                <TableCell>
                                                                    {format(
                                                                        new Date(
                                                                            schedule.scheduled_date +
                                                                                'T00:00:00'
                                                                        ),
                                                                        'PPP'
                                                                    )}
                                                                </TableCell>
                                                                <TableCell className="text-muted-foreground">
                                                                    {schedule.start_time?.slice(
                                                                        0,
                                                                        5
                                                                    )}{' '}
                                                                    –{' '}
                                                                    {schedule.end_time?.slice(0, 5)}
                                                                </TableCell>
                                                                <TableCell>
                                                                    <Badge
                                                                        variant={
                                                                            confirmed === total &&
                                                                            total > 0
                                                                                ? 'default'
                                                                                : 'secondary'
                                                                        }
                                                                    >
                                                                        {confirmed}/{total}{' '}
                                                                        confirmed
                                                                    </Badge>
                                                                </TableCell>
                                                                <TableCell className="text-right">
                                                                    <div
                                                                        className="flex justify-end gap-2"
                                                                        onClick={e =>
                                                                            e.stopPropagation()
                                                                        }
                                                                    >
                                                                        <Button
                                                                            variant="outline"
                                                                            size="sm"
                                                                            onClick={() =>
                                                                                navigate(
                                                                                    `/schedules/${schedule.id}`
                                                                                )
                                                                            }
                                                                        >
                                                                            <ChevronRight
                                                                                size={14}
                                                                            />
                                                                        </Button>
                                                                        {(isAdmin ||
                                                                            isDepartmentHead) && (
                                                                            <Button
                                                                                variant="outline"
                                                                                size="sm"
                                                                                onClick={() =>
                                                                                    handleDelete(
                                                                                        schedule
                                                                                    )
                                                                                }
                                                                                className="text-destructive hover:text-destructive"
                                                                            >
                                                                                <Trash2 size={14} />
                                                                            </Button>
                                                                        )}
                                                                    </div>
                                                                </TableCell>
                                                            </TableRow>
                                                        )
                                                    })}
                                            </TableBody>
                                        </Table>
                                    </div>
                                )}

                                {/* Below md the same schedules as a card list — five columns,
                                    one of which is a long formatted date, will not fit. */}
                                {schedules.length > 0 && (
                                    <ul className="space-y-2 md:hidden">
                                        {[...schedules]
                                            .sort((a, b) =>
                                                b.scheduled_date.localeCompare(a.scheduled_date)
                                            )
                                            .map(schedule => {
                                                const { confirmed, total } = STATUS_SUMMARY(
                                                    schedule.schedule_assignments
                                                )
                                                return (
                                                    <li key={schedule.id}>
                                                        <button
                                                            type="button"
                                                            onClick={() =>
                                                                navigate(
                                                                    `/schedules/${schedule.id}`
                                                                )
                                                            }
                                                            className="flex w-full items-center justify-between gap-3 rounded-lg border p-4 text-left transition-colors hover:bg-accent"
                                                        >
                                                            <div className="min-w-0">
                                                                <p className="truncate font-medium">
                                                                    {schedule.title}
                                                                </p>
                                                                <p className="text-sm text-muted-foreground">
                                                                    {format(
                                                                        new Date(
                                                                            schedule.scheduled_date +
                                                                                'T00:00:00'
                                                                        ),
                                                                        'EEE d MMM'
                                                                    )}
                                                                    {' · '}
                                                                    {schedule.start_time?.slice(
                                                                        0,
                                                                        5
                                                                    )}
                                                                    {' – '}
                                                                    {schedule.end_time?.slice(0, 5)}
                                                                </p>
                                                                <Badge
                                                                    className="mt-2"
                                                                    variant={
                                                                        confirmed === total &&
                                                                        total > 0
                                                                            ? 'default'
                                                                            : 'secondary'
                                                                    }
                                                                >
                                                                    {confirmed}/{total} confirmed
                                                                </Badge>
                                                            </div>
                                                            <ChevronRight
                                                                size={18}
                                                                className="shrink-0 text-muted-foreground"
                                                            />
                                                        </button>
                                                    </li>
                                                )
                                            })}
                                    </ul>
                                )}
                            </TabsContent>
                        </Tabs>
                    )}
                </>
            )}

            {/* Generate schedule dialog */}
            <Dialog open={generateOpen} onOpenChange={setGenerateOpen}>
                <DialogContent className="sm:max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Generate Schedule</DialogTitle>
                    </DialogHeader>
                    <GenerateScheduleForm
                        departmentId={selectedDepartmentId}
                        onSubmit={handleGenerate}
                        onCancel={() => setGenerateOpen(false)}
                    />
                </DialogContent>
            </Dialog>

            {/* Generate a whole month — preview, then commit */}
            <Dialog open={generateMonthOpen} onOpenChange={setGenerateMonthOpen}>
                <DialogContent className="sm:max-w-xl">
                    <DialogHeader>
                        <DialogTitle>Generate Month</DialogTitle>
                    </DialogHeader>
                    {generateMonthOpen && (
                        <GenerateMonthDialog
                            departmentId={selectedDepartmentId}
                            onPreview={previewMonth}
                            onCommit={commitMonth}
                            onDone={handleMonthDone}
                            onCancel={() => setGenerateMonthOpen(false)}
                        />
                    )}
                </DialogContent>
            </Dialog>

            {/* Export the month on screen as a shareable image */}
            <Dialog open={exportOpen} onOpenChange={setExportOpen}>
                <DialogContent className="sm:max-w-4xl">
                    <DialogHeader>
                        <DialogTitle>Export as Image</DialogTitle>
                    </DialogHeader>
                    {exportOpen && (
                        <RotaExportDialog
                            departmentId={selectedDepartmentId}
                            departmentName={selectedDepartment?.name ?? 'Schedule'}
                            month={month}
                            schedules={schedules}
                            onClose={() => setExportOpen(false)}
                        />
                    )}
                </DialogContent>
            </Dialog>
        </div>
    )
}
