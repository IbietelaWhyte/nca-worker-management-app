import { useState, useEffect, useCallback } from 'react'
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
        sendReminders,
        sendRemindersForSchedule,
    }
}
