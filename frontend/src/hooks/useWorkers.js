import { useState, useEffect, useCallback, useRef } from 'react'
import {
    getWorkers,
    createWorker,
    updateWorker,
    deactivateWorker,
    deleteWorkerPermanently,
} from '@/api/workers'

/**
 * With no argument this loads the whole list, as every picker expects. Pass `params` (forwarded to
 * the API as query params) to load one filtered page; `total` is then the count across all pages.
 * `total` stays null until the first load succeeds, so a page can tell "first load" from "refetch".
 */
export function useWorkers(params) {
    // Keyed on the serialised params so a new-but-equal object literal each render does not refetch.
    const key = JSON.stringify(params ?? null)
    const [total, setTotal] = useState(null)
    // Only the latest request may land: typing fast must not let an older page overwrite a newer one.
    const latestRequest = useRef(0)
    const [workers, setWorkers] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const fetchWorkers = useCallback(async () => {
        const request = ++latestRequest.current
        try {
            setLoading(true)
            setError(null)
            const response = await getWorkers(JSON.parse(key) ?? undefined)
            if (request !== latestRequest.current) return
            setWorkers(response.data)
            setTotal(Number(response.headers?.['x-total-count'] ?? response.data.length))
        } catch (err) {
            if (request !== latestRequest.current) return
            setError(err.response?.data?.detail ?? 'Failed to load workers')
        } finally {
            if (request === latestRequest.current) setLoading(false)
        }
    }, [key])

    useEffect(() => {
        fetchWorkers()
    }, [fetchWorkers])

    const addWorker = async (data, departmentId) => {
        const response = await createWorker(data, departmentId)
        setWorkers(prev => [...prev, response.data])
        return response.data
    }

    const editWorker = async (id, data) => {
        const response = await updateWorker(id, data)
        setWorkers(prev => prev.map(w => (w.id === id ? response.data : w)))
        return response.data
    }

    const removeWorker = async id => {
        await deactivateWorker(id)
        setWorkers(prev => prev.map(w => (w.id === id ? { ...w, is_active: false } : w)))
    }

    // Unlike removeWorker, the row is gone for good — drop it from the list rather than
    // marking it inactive. Throws so the caller can surface the reason (e.g. a 409 for a
    // worker who still has upcoming assignments).
    const destroyWorker = async id => {
        await deleteWorkerPermanently(id)
        setWorkers(prev => prev.filter(w => w.id !== id))
    }

    return {
        workers,
        total,
        loading,
        error,
        refetch: fetchWorkers,
        addWorker,
        editWorker,
        removeWorker,
        destroyWorker,
    }
}
