import { useState, useEffect, useCallback } from 'react'
import {
    getSchedule,
    updateAssignmentStatus,
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

    const changeAssignmentStatus = async (assignmentId, status) => {
        const response = await updateAssignmentStatus(assignmentId, status)
        setSchedule(prev => ({
            ...prev,
            schedule_assignments: prev.schedule_assignments.map(a =>
                a.id === assignmentId ? response.data : a
            ),
        }))
        return response.data
    }

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
        changeAssignmentStatus,
        sendReminders,
        sendRemindersForSchedule,
    }
}
