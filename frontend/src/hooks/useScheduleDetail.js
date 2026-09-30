import { useState, useEffect, useCallback } from 'react'
import {
    checkIn as apiCheckIn,
    closeAttendance as apiCloseAttendance,
    reopenAttendance as apiReopenAttendance,
    setExcused as apiSetExcused,
    undoCheckIn as apiUndoCheckIn,
} from '@/api/attendance'
import {
    addAssignment,
    getSchedule,
    removeAssignment,
    replaceAssignmentWorker,
    setAssignmentRole,
    triggerReminders,
    triggerRemindersForSchedule,
} from '@/api/schedules'

export function useScheduleDetail(scheduleId) {
    const [schedule, setSchedule] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const fetchSchedule = useCallback(async () => {
        if (!scheduleId) return
        try {
            setLoading(true)
            setError(null)
            const response = await getSchedule(scheduleId)
            setSchedule(response.data)
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to load schedule')
        } finally {
            setLoading(false)
        }
    }, [scheduleId])

    useEffect(() => {
        fetchSchedule()
    }, [fetchSchedule])

    const changeAssignmentRole = async (assignmentId, departmentRoleId) => {
        const response = await setAssignmentRole(assignmentId, departmentRoleId)
        setSchedule(prev => ({
            ...prev,
            schedule_assignments: prev.schedule_assignments.map(a =>
                a.id === assignmentId ? response.data : a
            ),
        }))
        return response.data
    }

    // The three edit paths all return the whole schedule, so they replace it rather than
    // patching a row — which is what keeps the subteam grouping and the staffing counts
    // right after an edit without a second request. The warnings are handed back to the
    // caller to render; the hook deliberately does not hold them, because they belong to
    // the action the head just took rather than to the schedule.
    const replaceFrom = response => {
        setSchedule(response.data.schedule)
        return response.data.warnings ?? []
    }

    const addWorker = async workerId => replaceFrom(await addAssignment(scheduleId, workerId))

    const swapWorker = async (assignmentId, workerId) =>
        replaceFrom(await replaceAssignmentWorker(assignmentId, workerId))

    const removeWorker = async assignmentId => replaceFrom(await removeAssignment(assignmentId))

    // Attendance. Same wholesale-replace shape as the edit paths above, for the same reason:
    // closing attendance changes every row at once, so patching one would leave the tally and
    // the badges disagreeing with each other.
    //
    // Deliberately optimistic where the others are not. An operator taking a register is looking
    // at a person, not at the screen; a tap that waits for a round-trip on church wifi before it
    // turns green gets tapped again, and the second tap toggles it back off. The row flips at
    // once and reverts if the write fails, with the error surfacing through the page's existing
    // band rather than silently.
    const patchAssignment = (assignmentId, changes) =>
        setSchedule(prev =>
            prev
                ? {
                      ...prev,
                      schedule_assignments: prev.schedule_assignments.map(a =>
                          a.id === assignmentId ? { ...a, ...changes } : a
                      ),
                  }
                : prev
        )

    const optimistically = async (assignmentId, changes, request) => {
        const before = schedule?.schedule_assignments.find(a => a.id === assignmentId)
        patchAssignment(assignmentId, changes)
        try {
            return replaceFrom(await request())
        } catch (err) {
            if (before) patchAssignment(assignmentId, before)
            throw err
        }
    }

    const markHere = async assignmentId =>
        optimistically(
            assignmentId,
            // is_late is left to the server: only it knows the grace period, and guessing here
            // would flash the wrong badge for as long as the round-trip takes.
            { checked_in_at: new Date().toISOString(), marked_absent_at: null, excused: false },
            () => apiCheckIn(assignmentId)
        )

    const undoHere = async assignmentId =>
        optimistically(
            assignmentId,
            { checked_in_at: null, is_late: false, minutes_late: null },
            () => apiUndoCheckIn(assignmentId)
        )

    const excuseAbsence = async (assignmentId, excused) =>
        optimistically(assignmentId, { excused }, () => apiSetExcused(assignmentId, excused))

    const finishAttendance = async () => replaceFrom(await apiCloseAttendance(scheduleId))

    const reopenAttendance = async () => replaceFrom(await apiReopenAttendance(scheduleId))

    const sendReminders = async () => {
        const response = await triggerReminders()
        return response.data
    }

    const sendRemindersForSchedule = async () => {
        const response = await triggerRemindersForSchedule(scheduleId)
        return response.data
    }

    return {
        schedule,
        loading,
        error,
        refetch: fetchSchedule,
        changeAssignmentRole,
        addWorker,
        swapWorker,
        removeWorker,
        markHere,
        undoHere,
        excuseAbsence,
        finishAttendance,
        reopenAttendance,
        sendReminders,
        sendRemindersForSchedule,
    }
}
