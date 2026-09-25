import { useParams, useNavigate } from 'react-router-dom'
import { useScheduleDetail } from '@/hooks/useScheduleDetail'
import { useAuth } from '@/context/AuthContext'
import AssignmentsList from '@/components/schedules/AssignmentsList'
import WorkerPickerDialog from '@/components/schedules/WorkerPickerDialog'
import { describeLeadTime } from '@/components/schedules/ReminderLeadTimesField'
import { Button } from '@/components/ui/button'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { formatSlotRange, summarizeStaffing } from '@/lib/staffing'
import { Label } from '@/components/ui/label'
import { ArrowLeft, Bell, UserPlus } from 'lucide-react'
import { format } from 'date-fns'
import { useState, useEffect, useMemo } from 'react'
import { getSubteamsByDepartment } from '@/api/subteams'
import { getAssignableWorkers } from '@/api/schedules'
import { getRolesByDepartment } from '@/api/roles'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'

export default function ScheduleDetailPage() {
    const { id } = useParams()
    const navigate = useNavigate()
    const { isAdmin, isDepartmentHead } = useAuth()
    const {
        schedule,
        loading,
        error,
        changeAssignmentRole,
        addWorker,
        swapWorker,
        removeWorker,
        sendRemindersForSchedule,
    } = useScheduleDetail(id)
    const [reminderLoading, setReminderLoading] = useState(false)
    const [reminderMessage, setReminderMessage] = useState(null)
    const [showEmptySubteams, setShowEmptySubteams] = useState(true)
    const [allSubteams, setAllSubteams] = useState([])
    const [subteamsLoading, setSubteamsLoading] = useState(false)
    const [departmentRoles, setDepartmentRoles] = useState([])
    // Who may still be added, each with the subteam they would land in. Fetched when the
    // picker opens rather than with the page: it changes with every edit, and nothing else
    // on screen needs it.
    const [candidates, setCandidates] = useState([])
    const [candidatesLoading, setCandidatesLoading] = useState(false)
    // null | { mode: 'add' } | { mode: 'swap', assignment } — one picker for the whole page.
    const [picker, setPicker] = useState(null)
    const [removeTarget, setRemoveTarget] = useState(null)
    const [editBusy, setEditBusy] = useState(false)
    const [editError, setEditError] = useState(null)
    const [editWarnings, setEditWarnings] = useState([])

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

    // Fetch the department's roles for the per-assignment role selector
    useEffect(() => {
        const fetchRoles = async () => {
            if (!schedule?.department_id) return
            try {
                const response = await getRolesByDepartment(schedule.department_id)
                setDepartmentRoles(response.data || [])
            } catch (err) {
                console.error('Failed to fetch roles:', err)
                setDepartmentRoles([])
            }
        }
        fetchRoles()
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

    const runEdit = async action => {
        setEditBusy(true)
        setEditError(null)
        try {
            setEditWarnings(await action())
            return true
        } catch (err) {
            setEditError(err.response?.data?.detail ?? 'That change could not be saved')
            return false
        } finally {
            setEditBusy(false)
        }
    }

    const handlePick = async workerId => {
        const done = await runEdit(() =>
            picker?.mode === 'swap'
                ? swapWorker(picker.assignment.id, workerId)
                : addWorker(workerId)
        )
        if (done) setPicker(null)
    }

    const handleRemove = async () => {
        const done = await runEdit(() => removeWorker(removeTarget.id))
        if (done) setRemoveTarget(null)
    }

    const openPicker = async next => {
        setEditError(null)
        setEditWarnings([])
        setPicker(next)
        // Always refetched: an add or a removal changes who is still eligible, and a stale
        // list would offer somebody who is already serving.
        setCandidatesLoading(true)
        try {
            const response = await getAssignableWorkers(id)
            setCandidates(response.data ?? [])
        } catch (err) {
            console.error('Failed to fetch assignable workers:', err)
            setCandidates([])
        } finally {
            setCandidatesLoading(false)
        }
    }

    const handleSendReminders = async schedule => {
        // Worth saying out loud, because it used to be false: a manual send once burned the
        // automatic reminder, and now records nothing, so the ladder still fires as planned.
        if (
            !confirm(
                'Text everyone on this rota now? Their scheduled reminders still go out as planned.'
            )
        )
            return
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
    const totalCount = assignments.length
    const staffing = summarizeStaffing(schedule)
    const reminderLadder = schedule.reminder_days_before ?? []
    const canManage = isAdmin || isDepartmentHead

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex min-w-0 items-center gap-4">
                    <Button variant="outline" size="sm" onClick={() => navigate('/schedules')}>
                        <ArrowLeft size={16} className="mr-2" /> Back
                    </Button>
                    <div>
                        <div className="flex flex-wrap items-center gap-2">
                            <h2 className="text-2xl font-bold">{schedule.title}</h2>
                            {/* The snapshot, not a lookup: it keeps reading correctly after
                                the rule is renamed or deleted. */}
                            {schedule.special_service_name && (
                                <Badge variant="warning">{schedule.special_service_name}</Badge>
                            )}
                        </div>
                        <p className="text-muted-foreground text-sm mt-1">
                            {format(new Date(schedule.scheduled_date + 'T00:00:00'), 'PPPP')}
                            {' · '}
                            {schedule.start_time?.slice(0, 5)} – {schedule.end_time?.slice(0, 5)}
                        </p>
                        {/* Read-only: the ladder is chosen at generation and nowhere else, so
                            this is the only place a head can see what a rota will actually send. */}
                        <p className="text-muted-foreground text-xs mt-1">
                            {reminderLadder.length === 0
                                ? 'No reminders'
                                : `Reminders: ${reminderLadder.map(describeLeadTime).join(', ').toLowerCase()}`}
                        </p>
                    </div>
                </div>

                {canManage && (
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
                    <p className="text-2xl font-bold text-muted-foreground">
                        {formatSlotRange(staffing.min, staffing.max)}
                    </p>
                    <p className="text-xs text-muted-foreground">Wanted</p>
                </div>
                <div className="ml-auto">
                    {staffing.understaffed ? (
                        <Badge variant="destructive">{staffing.short} short</Badge>
                    ) : staffing.full ? (
                        <Badge>Fully staffed</Badge>
                    ) : (
                        <Badge variant="secondary">Room for {staffing.max - totalCount} more</Badge>
                    )}
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

            {/* What an edit went through with anyway. Never red: none of these stopped it, and
                a rota can be both short and correct — the head is being told, not blocked. */}
            {editWarnings.length > 0 && (
                <Alert variant="warning">
                    <ul className="space-y-1 text-sm">
                        {editWarnings.map(warning => (
                            <li key={warning}>{warning}</li>
                        ))}
                    </ul>
                </Alert>
            )}

            {/* A refusal from a path with no dialog in front of it (a removal). The picker
                shows its own, because the dialog covers this. */}
            {editError && !picker && (
                <Alert variant="destructive">
                    <p className="text-sm">{editError}</p>
                </Alert>
            )}

            {/* Assignments */}
            <div className="space-y-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <h3 className="font-semibold">Assigned Workers</h3>
                    <div className="flex flex-wrap items-center gap-3">
                        <Label className="flex items-center gap-2 cursor-pointer text-sm font-normal">
                            <input
                                type="checkbox"
                                checked={showEmptySubteams}
                                onChange={e => setShowEmptySubteams(e.target.checked)}
                                className="cursor-pointer"
                            />
                            Show subteams with no assignments
                        </Label>
                        {canManage && (
                            <Button
                                variant="outline"
                                size="sm"
                                disabled={staffing.full}
                                onClick={() => openPicker({ mode: 'add' })}
                            >
                                <UserPlus size={16} className="mr-2" />
                                Add worker
                            </Button>
                        )}
                    </div>
                </div>
                {/* On screen rather than in a tooltip: there is no hover on a phone, so a
                    disabled button with no reason beside it is just a broken button. */}
                {canManage && staffing.full && (
                    <p className="text-xs text-muted-foreground">
                        This rota is full at {staffing.max}. Take somebody off to add another.
                    </p>
                )}
                {subteamsLoading ? (
                    <div className="flex items-center justify-center py-8">
                        <p className="text-sm text-muted-foreground">
                            Loading subteam information...
                        </p>
                    </div>
                ) : (
                    <AssignmentsList
                        groupedAssignments={groupedAssignments}
                        onRoleChange={changeAssignmentRole}
                        onSwap={
                            canManage
                                ? assignment => openPicker({ mode: 'swap', assignment })
                                : null
                        }
                        onRemove={
                            canManage
                                ? assignment => {
                                      setEditError(null)
                                      setEditWarnings([])
                                      setRemoveTarget(assignment)
                                  }
                                : null
                        }
                        roles={departmentRoles}
                        canManage={canManage}
                    />
                )}
            </div>

            {/* One picker for the whole page, not one per row. */}
            <WorkerPickerDialog
                open={picker !== null}
                onOpenChange={next => !next && setPicker(null)}
                title={picker?.mode === 'swap' ? 'Swap this duty' : 'Add a worker'}
                description={
                    picker?.mode === 'swap'
                        ? `${workerName(picker.assignment)} comes off this date and whoever you pick goes on. Both of them get a text.`
                        : 'Whoever you pick goes on this date and gets a text straight away.'
                }
                candidates={candidates}
                loading={candidatesLoading}
                busy={editBusy}
                error={editError}
                onPick={handlePick}
            />

            {/* Its own dialog rather than window.confirm: this sends a text, and every message
                that costs money gets a button somebody chose to press. */}
            <Dialog
                open={removeTarget !== null}
                onOpenChange={next => !editBusy && !next && setRemoveTarget(null)}
            >
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>
                            Take {removeTarget ? workerName(removeTarget) : 'this worker'} off?
                        </DialogTitle>
                        <DialogDescription>
                            They come off this date and get a text saying so. The rota keeps every
                            other change you have made to it.
                        </DialogDescription>
                    </DialogHeader>

                    {editError && (
                        <Alert variant="destructive">
                            <p className="text-sm">{editError}</p>
                        </Alert>
                    )}

                    <DialogFooter>
                        <Button
                            variant="outline"
                            disabled={editBusy}
                            onClick={() => setRemoveTarget(null)}
                        >
                            Cancel
                        </Button>
                        <Button variant="destructive" disabled={editBusy} onClick={handleRemove}>
                            {editBusy ? 'Removing...' : 'Remove and text them'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}

/** An assignment's worker as a person reads it, or a neutral fallback if the embed is missing. */
const workerName = assignment =>
    assignment?.workers
        ? `${assignment.workers.first_name} ${assignment.workers.last_name}`
        : 'this worker'
