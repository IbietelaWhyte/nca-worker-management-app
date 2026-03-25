import { useState, useEffect, useCallback } from 'react'
import {
    getWorkerAvailability,
    setAvailability,
    deleteAvailability,
    clearWorkerAvailability,
} from '@/api/availability'

const DAYS = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']

export function useAvailability(workerId) {
    const [availability, setAvailabilityState] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const fetchAvailability = useCallback(async () => {
        if (!workerId) return
        try {
        setLoading(true)
        setError(null)
        const response = await getWorkerAvailability(workerId)
        setAvailabilityState(response.data)
        } catch (err) {
        setError(err.response?.data?.detail ?? 'Failed to load availability')
        } finally {
        setLoading(false)
        }
    }, [workerId])

    useEffect(() => {
        fetchAvailability()
    }, [fetchAvailability])

    // Returns a map of day_of_week -> availability record for easy lookup
    const availabilityByDay = DAYS.reduce((acc, day) => {
        const record = availability.find(
        a => a.availability_type === 'recurring' && a.day_of_week === day
        )
        acc[day] = record ?? null
        return acc
    }, {})

    const toggleDay = async (day, currentRecord) => {
        if (currentRecord) {
        // Already has a record — flip is_available
        if (currentRecord.is_available) {
            // Mark unavailable by deleting the record
            await deleteAvailability(currentRecord.id)
            setAvailabilityState(prev => prev.filter(a => a.id !== currentRecord.id))
        } else {
            // Re-enable
            const response = await setAvailability({
            worker_id: workerId,
            availability_type: 'recurring',
            day_of_week: day,
            is_available: true,
            })
            setAvailabilityState(prev =>
            prev.map(a => a.id === currentRecord.id ? response.data : a)
            )
        }
        } else {
        // No record yet — create one marked available
        const response = await setAvailability({
            worker_id: workerId,
            availability_type: 'recurring',
            day_of_week: day,
            is_available: true,
        })
        setAvailabilityState(prev => [...prev, response.data])
        }
    }

    const clearAll = async () => {
        await clearWorkerAvailability(workerId)
        setAvailabilityState([])
    }

    return {
        availability,
        availabilityByDay,
        loading,
        error,
        toggleDay,
        clearAll,
        refetch: fetchAvailability,
    }
}