import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDepartments } from '@/hooks/useDepartments'
import { useSchedules } from '@/hooks/useSchedules'
import { useAuth } from '@/context/AuthContext'
import GenerateScheduleForm from '@/components/schedules/GenerateScheduleForm'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert } from '@/components/ui/alert'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table'
import { Plus, ChevronRight, Trash2, Calendar } from 'lucide-react'
import { format } from 'date-fns'

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

    // For assistant_hod users, auto-select first department if only one available
    const isAssistantHod = role === 'assistant_hod'

    // Auto-select department for assistant_hod if they only have one
    useEffect(() => {
        if (isAssistantHod && departments.length === 1 && !selectedDepartmentId) {
            setSelectedDepartmentId(departments[0].id)
        }
    }, [departments, isAssistantHod, selectedDepartmentId])

    const { schedules, loading, error, createSchedule, removeSchedule } =
        useSchedules(selectedDepartmentId)

    const selectedDepartment = departments.find(d => d.id === selectedDepartmentId)

    const handleGenerate = async formData => {
        await createSchedule(formData)
        setGenerateOpen(false)
    }

    const handleDelete = async schedule => {
        if (!confirm(`Delete "${schedule.title}"? This cannot be undone.`)) return
        await removeSchedule(schedule.id)
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold">Schedules</h2>
                    <p className="text-muted-foreground text-sm mt-1">
                        Generate and manage service schedules by department
                    </p>
                </div>
                {(isAdmin || isDepartmentHead) && selectedDepartmentId && (
                    <Button onClick={() => setGenerateOpen(true)}>
                        <Plus size={16} className="mr-2" />
                        Generate Schedule
                    </Button>
                )}
            </div>

            {/* Department selector - dropdown for admins/HODs, tabs for assistant_hod */}
            {!isAssistantHod ? (
                <div className="flex items-center gap-3">
                    <label className="text-sm font-medium whitespace-nowrap">Department</label>
                    <select
                        value={selectedDepartmentId}
                        onChange={e => setSelectedDepartmentId(e.target.value)}
                        className="w-full max-w-sm px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring"
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

                    {loading && (
                        <div className="flex items-center justify-center h-40">
                            <p className="text-muted-foreground">Loading schedules...</p>
                        </div>
                    )}

                    {!loading && !error && schedules.length === 0 && (
                        <div className="flex flex-col items-center justify-center h-48 border rounded-lg border-dashed">
                            <Calendar size={32} className="text-muted-foreground mb-3" />
                            <p className="text-muted-foreground text-sm">
                                No schedules yet for {selectedDepartment?.name}
                            </p>
                            {(isAdmin || isDepartmentHead) && (
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="mt-3"
                                    onClick={() => setGenerateOpen(true)}
                                >
                                    Generate first schedule
                                </Button>
                            )}
                        </div>
                    )}

                    {!loading && schedules.length > 0 && (
                        <div className="border rounded-lg overflow-hidden">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Title</TableHead>
                                        <TableHead>Date</TableHead>
                                        <TableHead>Time</TableHead>
                                        <TableHead>Assignments</TableHead>
                                        <TableHead className="text-right">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {schedules
                                        .sort((a, b) =>
                                            b.scheduled_date.localeCompare(a.scheduled_date)
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
                                                        navigate(`/schedules/${schedule.id}`)
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
                                                        {schedule.start_time?.slice(0, 5)} –{' '}
                                                        {schedule.end_time?.slice(0, 5)}
                                                    </TableCell>
                                                    <TableCell>
                                                        <Badge
                                                            variant={
                                                                confirmed === total && total > 0
                                                                    ? 'default'
                                                                    : 'secondary'
                                                            }
                                                        >
                                                            {confirmed}/{total} confirmed
                                                        </Badge>
                                                    </TableCell>
                                                    <TableCell className="text-right">
                                                        <div
                                                            className="flex justify-end gap-2"
                                                            onClick={e => e.stopPropagation()}
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
                                                                <ChevronRight size={14} />
                                                            </Button>
                                                            {(isAdmin || isDepartmentHead) && (
                                                                <Button
                                                                    variant="outline"
                                                                    size="sm"
                                                                    onClick={() =>
                                                                        handleDelete(schedule)
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
        </div>
    )
}
