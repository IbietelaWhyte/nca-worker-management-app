import { useState, useEffect, useCallback } from 'react'
import {
    createSpecialService,
    deleteSpecialService,
    getSpecialServices,
    updateSpecialService,
} from '@/api/specialServices'

/**
 * Church-wide special services, with the usual list/CRUD shape.
 *
 * Local state is patched after each mutation rather than refetching, matching every other
 * `use<Domain>` hook here. The list is tens of rows, so it is held whole.
 */
export function useSpecialServices() {
    const [services, setServices] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const fetchServices = useCallback(async () => {
        try {
            setLoading(true)
            setError(null)
            const response = await getSpecialServices()
            setServices(response.data ?? [])
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to load special services')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        fetchServices()
    }, [fetchServices])

    const addService = async data => {
        const response = await createSpecialService(data)
        setServices(prev => [...prev, response.data])
        return response.data
    }

    const editService = async (id, data) => {
        const response = await updateSpecialService(id, data)
        setServices(prev => prev.map(s => (s.id === id ? response.data : s)))
        return response.data
    }

    const removeService = async id => {
        await deleteSpecialService(id)
        setServices(prev => prev.filter(s => s.id !== id))
    }

    return {
        services,
        loading,
        error,
        refetch: fetchServices,
        addService,
        editService,
        removeService,
    }
}
