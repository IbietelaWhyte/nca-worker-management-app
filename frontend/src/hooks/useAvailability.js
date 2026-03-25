import { useState, useEffect, useCallback } from 'react'
import {
    getWorkerAvailability,
    setAvailability,
    deleteAvailability,
    clearWorkerAvailability,
} from '@/api/availability'

export function useAvailability(workerId) {
    const [availability, setAvailabilityState] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const fetchAvailability = useCallback(async () => {
        if (!workerId) {
        setLoading(false)
        return
        }
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

    // Specific date records — array sorted by date
    const specificDates = availability
        .filter(a => a.availability_type === 'specific_date')
        .sort((a, b) => a.specific_date?.localeCompare(b.specific_date))

    const toggleSpecificDate = async (dateStr, existingRecord) => {
        if (existingRecord) {
        // Cycle through: available → unavailable → removed
        if (existingRecord.is_available) {
            // Flip to unavailable
            const response = await setAvailability({
            worker_id: workerId,
            availability_type: 'specific_date',
            specific_date: dateStr,
            is_available: false,
            })
            setAvailabilityState(prev =>
            prev.map(a => a.id === existingRecord.id ? response.data : a)
            )
        } else {
            // Remove the override entirely
            await deleteAvailability(existingRecord.id)
            setAvailabilityState(prev => prev.filter(a => a.id !== existingRecord.id))
        }
        } else {
        // No record — create as available override
        const response = await setAvailability({
            worker_id: workerId,
            availability_type: 'specific_date',
            specific_date: dateStr,
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
        specificDates,
        loading,
        error,
        toggleSpecificDate,
        clearAll,
        refetch: fetchAvailability,
    }
}