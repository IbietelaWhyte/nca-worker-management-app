import { useState, useEffect, useCallback, useRef } from 'react'
import {
    getDepartments,
    createDepartment,
    updateDepartment,
    deleteDepartment,
} from '@/api/departments'

/**
 * With no argument this loads the whole list, as every picker expects. Pass `params` (forwarded to
 * the API as query params) to load one filtered page; `total` is then the count across all pages.
 * `total` stays null until the first load succeeds, so a page can tell "first load" from "refetch".
 */
export function useDepartments(params) {
    // Keyed on the serialised params so a new-but-equal object literal each render does not refetch.
    const key = JSON.stringify(params ?? null)
    const [total, setTotal] = useState(null)
    // Only the latest request may land: typing fast must not let an older page overwrite a newer one.
    const latestRequest = useRef(0)
    const [departments, setDepartments] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const fetchDepartments = useCallback(async () => {
        const request = ++latestRequest.current
        try {
            setLoading(true)
            setError(null)
            const response = await getDepartments(JSON.parse(key) ?? undefined)
            if (request !== latestRequest.current) return
            setDepartments(response.data)
            setTotal(Number(response.headers?.['x-total-count'] ?? response.data.length))
        } catch (err) {
            if (request !== latestRequest.current) return
            setError(err.response?.data?.detail ?? 'Failed to load departments')
        } finally {
            if (request === latestRequest.current) setLoading(false)
        }
    }, [key])

    useEffect(() => {
        fetchDepartments()
    }, [fetchDepartments])

    const addDepartment = async data => {
        const response = await createDepartment(data)
        setDepartments(prev => [...prev, response.data])
        return response.data
    }

    const editDepartment = async (id, data) => {
        const response = await updateDepartment(id, data)
        setDepartments(prev => prev.map(d => (d.id === id ? response.data : d)))
        return response.data
    }

    const removeDepartment = async id => {
        await deleteDepartment(id)
        setDepartments(prev => prev.filter(d => d.id !== id))
    }

    return {
        departments,
        total,
        loading,
        error,
        refetch: fetchDepartments,
        addDepartment,
        editDepartment,
        removeDepartment,
    }
}
