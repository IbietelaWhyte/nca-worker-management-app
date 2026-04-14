import { useParams, useNavigate } from 'react-router-dom'
import { useScheduleDetail } from '@/hooks/useScheduleDetail'
import { useAuth } from '@/context/AuthContext'
import AssignmentsList from '@/components/schedules/AssignmentsList'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert } from '@/components/ui/alert'
import { Label } from '@/components/ui/label'
import { ArrowLeft, Bell } from 'lucide-react'
import { format } from 'date-fns'
import { useState, useEffect, useMemo } from 'react'
import { getSubteamsByDepartment } from '@/api/subteams'

export default function ScheduleDetailPage() {
    const { id } = useParams()
    const navigate = useNavigate()
    const { isAdmin, isDepartmentHead } = useAuth()
    const { schedule, loading, error, changeAssignmentStatus, sendRemindersForSchedule } =
        useScheduleDetail(id)
    const [reminderLoading, setReminderLoading] = useState(false)
    const [reminderMessage, setReminderMessage] = useState(null)
    const [showEmptySubteams, setShowEmptySubteams] = useState(true)
    const [allSubteams, setAllSubteams] = useState([])
    const [subteamsLoading, setSubteamsLoading] = useState(false)

    // Fetch all subteams for the department
    useEffect(() => {
        const fetchSubteams = async () => {
            if (!schedule?.department_id) return
            setSubteamsLoading(true)
            try {
                const response = await getSubteamsByDepartment(schedule.department_id)
                setAllSubteams(response.data || [])
            } catch (err) {
                console.error('Failed to fetch subteams:', err)
                setAllSubteams([])
            } finally {
                setSubteamsLoading(false)
            }
        }
        fetchSubteams()
    }, [schedule?.department_id])

    // Group and filter assignments by subteam
    const groupedAssignments = useMemo(() => {
        if (!schedule) return []

        const assignments = schedule?.schedule_assignments ?? []

        // Group assignments by subteam
        const grouped = {}

        // Group by subteam_id (null = unassigned)
        assignments.forEach(assignment => {
            const key = assignment.subteam_id || 'unassigned'
            if (!grouped[key]) {
                grouped[key] = {
                    subteamId: assignment.subteam_id,
                    subteamName: assignment.subteams?.name || 'Unassigned',
                    assignments: [],
                }
            }
            grouped[key].assignments.push(assignment)
        })

        // Add empty subteams if toggle is on
        if (showEmptySubteams) {
            allSubteams.forEach(subteam => {
                const key = subteam.id
                if (!grouped[key]) {
                    grouped[key] = {
                        subteamId: subteam.id,
                        subteamName: subteam.name,
                        assignments: [],
                    }
                }
            })
        }

        // Convert to array and sort
        const result = Object.values(grouped).sort((a, b) => {
            // Unassigned first
            if (a.subteamName === 'Unassigned') return -1
            if (b.subteamName === 'Unassigned') return 1
            // Then alphabetical
            return a.subteamName.localeCompare(b.subteamName)
        })

        return result
    }, [schedule, showEmptySubteams, allSubteams])

    const handleSendReminders = async schedule => {
        if (!confirm('Send SMS reminders to all assigned workers now?')) return
        setReminderLoading(true)
        setReminderMessage(null)
        try {
            const result = await sendRemindersForSchedule(schedule.id)
            setReminderMessage(result.message)
        } catch (err) {
            setReminderMessage(`Failed to send reminders: ${err.message}`)
        } finally {
            setReminderLoading(false)
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <p className="text-muted-foreground">Loading schedule...</p>
            </div>
        )
    }

    if (error || !schedule) {
        return (
            <div className="space-y-4">
                <Button variant="outline" onClick={() => navigate('/schedules')}>
                    <ArrowLeft size={16} className="mr-2" /> Back
                </Button>
                <Alert variant="destructive">
                    <p className="text-sm">{error ?? 'Schedule not found'}</p>
                </Alert>
            </div>
        )
    }

    const assignments = schedule?.schedule_assignments ?? []
    const confirmedCount = assignments.filter(a => a.status === 'confirmed').length
    const totalCount = assignments.length
    const allConfirmed = confirmedCount === totalCount && totalCount > 0

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between">
                <div className="flex items-center gap-4">
                    <Button variant="outline" size="sm" onClick={() => navigate('/schedules')}>
                        <ArrowLeft size={16} className="mr-2" /> Back
                    </Button>
                    <div>
                        <h2 className="text-2xl font-bold">{schedule.title}</h2>
                        <p className="text-muted-foreground text-sm mt-1">
                            {format(new Date(schedule.scheduled_date + 'T00:00:00'), 'PPPP')}
                            {' · '}
                            {schedule.start_time?.slice(0, 5)} – {schedule.end_time?.slice(0, 5)}
                        </p>
                    </div>
                </div>

                {(isAdmin || isDepartmentHead) && (
                    <Button
                        variant="outline"
                        onClick={() => handleSendReminders(schedule)}
                        disabled={reminderLoading}
                    >
                        <Bell size={16} className="mr-2" />
                        {reminderLoading ? 'Sending...' : 'Send Reminders'}
                    </Button>
                )}
            </div>

            {/* Stats bar */}
            <div className="flex items-center gap-4 p-4 border rounded-lg bg-muted/30">
                <div className="text-center">
                    <p className="text-2xl font-bold">{totalCount}</p>
                    <p className="text-xs text-muted-foreground">Assigned</p>
                </div>
                <div className="text-center">
                    <p className="text-2xl font-bold text-primary">{confirmedCount}</p>
                    <p className="text-xs text-muted-foreground">Confirmed</p>
                </div>
                <div className="text-center">
                    <p className="text-2xl font-bold text-destructive">
                        {assignments.filter(a => a.status === 'declined').length}
                    </p>
                    <p className="text-xs text-muted-foreground">Declined</p>
                </div>
                <div className="ml-auto">
                    <Badge variant={allConfirmed ? 'default' : 'secondary'}>
                        {allConfirmed
                            ? 'Fully confirmed'
                            : `${confirmedCount}/${totalCount} confirmed`}
                    </Badge>
                </div>
            </div>

            {/* Notes */}
            {schedule.notes && (
                <div className="p-4 border rounded-lg bg-muted/20">
                    <p className="text-sm text-muted-foreground">{schedule.notes}</p>
                </div>
            )}

            {/* Reminder feedback */}
            {reminderMessage && (
                <Alert>
                    <p className="text-sm">{reminderMessage}</p>
                </Alert>
            )}

            {/* Assignments */}
            <div className="space-y-3">
                <div className="flex items-center justify-between">
                    <h3 className="font-semibold">Assigned Workers</h3>
                    <Label className="flex items-center gap-2 cursor-pointer text-sm font-normal">
                        <input
                            type="checkbox"
                            checked={showEmptySubteams}
                            onChange={e => setShowEmptySubteams(e.target.checked)}
                            className="cursor-pointer"
                        />
                        Show subteams with no assignments
                    </Label>
                </div>
                {subteamsLoading ? (
                    <div className="flex items-center justify-center py-8">
                        <p className="text-sm text-muted-foreground">
                            Loading subteam information...
                        </p>
                    </div>
                ) : (
                    <AssignmentsList
                        groupedAssignments={groupedAssignments}
                        onStatusChange={changeAssignmentStatus}
                        canManage={isAdmin || isDepartmentHead}
                    />
                )}
            </div>
        </div>
    )
}
