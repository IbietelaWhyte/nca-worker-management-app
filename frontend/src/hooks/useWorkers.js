import { useState, useEffect, useCallback } from 'react'
import { getWorkers, createWorker, updateWorker, deactivateWorker } from '@/api/workers'

export function useWorkers() {
    const [workers, setWorkers] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const fetchWorkers = useCallback(async () => {
        try {
            setLoading(true)
            setError(null)
            const response = await getWorkers()
            setWorkers(response.data)
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to load workers')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        fetchWorkers()
    }, [fetchWorkers])

    const addWorker = async data => {
        const response = await createWorker(data)
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

    return {
        workers,
        loading,
        error,
        refetch: fetchWorkers,
        addWorker,
        editWorker,
        removeWorker,
    }
}
