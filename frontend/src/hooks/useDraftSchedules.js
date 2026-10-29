import { useCallback, useEffect, useState } from 'react'
import { deleteMonth, finalizeMonth, getSchedulesByDepartment } from '@/api/schedules'

/**
 * Every draft a department has, whatever the month, for the Drafts tab. Department-wide: any head
 * of the department can finish a draft somebody else started.
 */
export function useDraftSchedules(departmentId) {
    const [drafts, setDrafts] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const fetchDrafts = useCallback(async () => {
        if (!departmentId) {
            setDrafts([])
            setLoading(false)
            return
        }
        try {
            setLoading(true)
            setError(null)
            const response = await getSchedulesByDepartment(departmentId, null, 'draft')
            setDrafts(response.data)
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to load drafts')
        } finally {
            setLoading(false)
        }
    }, [departmentId])

    useEffect(() => {
        fetchDrafts()
    }, [fetchDrafts])

    // Both drop the month's drafts from local state on success: finalized ones move to the
    // Month and List views, deleted ones are gone.
    const dropMonth = (year, month) =>
        setDrafts(prev =>
            prev.filter(
                s => !s.scheduled_date.startsWith(`${year}-${String(month).padStart(2, '0')}`)
            )
        )

    const finalizeDraftMonth = async (year, month) => {
        const response = await finalizeMonth(departmentId, year, month)
        dropMonth(year, month)
        return response.data
    }

    const deleteDraftMonth = async (year, month) => {
        const response = await deleteMonth(departmentId, year, month, 'draft')
        dropMonth(year, month)
        return response.data
    }

    return {
        drafts,
        loading,
        error,
        refetch: fetchDrafts,
        finalizeDraftMonth,
        deleteDraftMonth,
    }
}
