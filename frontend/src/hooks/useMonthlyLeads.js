import { useState, useEffect, useCallback } from 'react'
import { getMonthlyLeads, setMonthlyLeads } from '@/api/monthlyLeads'

/**
 * A department's monthly leads ("Teacher of the Month") for one month.
 *
 * `month` is a month key from `monthKey()` ("2026-11-01"). `title` is null when the department does not use the
 * feature, and then `leads` is always empty — callers render nothing rather than checking both.
 */
export function useMonthlyLeads(departmentId, month) {
    const [title, setTitle] = useState(null)
    const [leads, setLeads] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const fetchLeads = useCallback(async () => {
        if (!departmentId || !month) {
            setTitle(null)
            setLeads([])
            setLoading(false)
            return
        }
        try {
            setLoading(true)
            setError(null)
            const response = await getMonthlyLeads(departmentId, month)
            setTitle(response.data.title)
            setLeads(response.data.leads)
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to load monthly leads')
        } finally {
            setLoading(false)
        }
    }, [departmentId, month])

    useEffect(() => {
        fetchLeads()
    }, [fetchLeads])

    const save = async workerIds => {
        const response = await setMonthlyLeads(departmentId, month, workerIds)
        setTitle(response.data.title)
        setLeads(response.data.leads)
        return response.data
    }

    return { title, leads, loading, error, refetch: fetchLeads, save }
}
