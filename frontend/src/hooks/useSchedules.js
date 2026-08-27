import { useState, useEffect, useCallback } from 'react'
import { endOfMonth, format, startOfMonth } from 'date-fns'
import {
    getSchedulesByDepartment,
    generateSchedule,
    generateMonthlySchedule,
    previewMonthlySchedule,
    deleteSchedule,
} from '@/api/schedules'

export function useSchedules(departmentId) {
    const [schedules, setSchedules] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    // The month the calendar view is showing. Also bounds what we fetch, so opening a
    // month never pulls the department's entire history.
    const [month, setMonth] = useState(() => startOfMonth(new Date()))

    const fetchSchedules = useCallback(async () => {
        if (!departmentId) {
            setLoading(false)
            return
        }
        try {
            setLoading(true)
            setError(null)
            const response = await getSchedulesByDepartment(departmentId, {
                from: format(startOfMonth(month), 'yyyy-MM-dd'),
                to: format(endOfMonth(month), 'yyyy-MM-dd'),
            })
            setSchedules(response.data)
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to load schedules')
        } finally {
            setLoading(false)
        }
    }, [departmentId, month])

    useEffect(() => {
        fetchSchedules()
    }, [fetchSchedules])

    const createSchedule = async data => {
        const response = await generateSchedule(data)
        setSchedules(prev => [response.data, ...prev])
        return response.data
    }

    const previewMonth = async data => {
        const response = await previewMonthlySchedule(data)
        return response.data
    }

    const commitMonth = async data => {
        const response = await generateMonthlySchedule(data)
        // Only the schedules landing in the month on screen belong in local state; the
        // rest would show up as phantom entries when the user pages to another month.
        const from = format(startOfMonth(month), 'yyyy-MM-dd')
        const to = format(endOfMonth(month), 'yyyy-MM-dd')
        const visible = response.data.created.filter(
            s => s.scheduled_date >= from && s.scheduled_date <= to
        )
        setSchedules(prev => [...visible, ...prev])
        return response.data
    }

    const removeSchedule = async scheduleId => {
        await deleteSchedule(scheduleId)
        setSchedules(prev => prev.filter(s => s.id !== scheduleId))
    }

    return {
        schedules,
        loading,
        error,
        month,
        setMonth,
        refetch: fetchSchedules,
        createSchedule,
        previewMonth,
        commitMonth,
        removeSchedule,
    }
}
