import { useState, useEffect, useCallback } from 'react'
import { getSchedulesByDepartment, generateSchedule, deleteSchedule } from '@/api/schedules'

export function useSchedules(departmentId) {
    const [schedules, setSchedules] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const fetchSchedules = useCallback(async () => {
        if (!departmentId) {
            setLoading(false)
            return
        }
        try {
            setLoading(true)
            setError(null)
            const response = await getSchedulesByDepartment(departmentId)
            setSchedules(response.data)
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to load schedules')
        } finally {
            setLoading(false)
        }
    }, [departmentId])

    useEffect(() => {
        fetchSchedules()
    }, [fetchSchedules])

    const createSchedule = async data => {
        const response = await generateSchedule(data)
        setSchedules(prev => [response.data, ...prev])
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
        refetch: fetchSchedules,
        createSchedule,
        removeSchedule,
    }
}
