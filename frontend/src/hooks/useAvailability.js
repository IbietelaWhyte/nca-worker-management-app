import { useState, useEffect, useCallback } from 'react'
import {
    getAvailabilityConfig,
    getWorkerAvailability,
    setAvailability,
    deleteAvailability,
    clearWorkerAvailability,
} from '@/api/availability'

export function useAvailability(workerId) {
    const [availability, setAvailabilityState] = useState([])
    const [editableFrom, setEditableFrom] = useState(null)
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

    // The cut-off is a server setting, not a per-worker one, so it is fetched once rather than
    // alongside each worker's records. A failure here is left silent: the server enforces the
    // cut-off regardless, so the worst case is a date that looks open and is refused on tap.
    useEffect(() => {
        let cancelled = false
        getAvailabilityConfig()
            .then(response => {
                if (!cancelled) setEditableFrom(response.data.editable_from)
            })
            .catch(() => {})
        return () => {
            cancelled = true
        }
    }, [])

    // The dates this worker cannot serve, sorted. Rows saying "available" are left out: the page
    // used to ask that question too, so old ones still exist, but an unmarked date already means
    // the same thing and showing them would read as a contradiction.
    const unavailableDates = availability
        .filter(a => a.availability_type === 'specific_date' && !a.is_available)
        .sort((a, b) => a.specific_date?.localeCompare(b.specific_date))

    // Two states, not three: a date is either unmarked or marked as one this worker cannot
    // serve. There is no "mark available", because the rota already treats an unmarked date that
    // way and a row saying so changes nothing.
    //
    // Both writers report failures through `error`. Without this the page was silent when a save
    // failed — the day picked up its own selection ring and nothing else happened, which read as
    // "the click did nothing" rather than "the save was rejected".
    const toggleSpecificDate = async (dateStr, existingRecord) => {
        setError(null)
        try {
            if (existingRecord) {
                await deleteAvailability(existingRecord.id)
                setAvailabilityState(prev => prev.filter(a => a.id !== existingRecord.id))
            } else {
                const response = await setAvailability({
                    worker_id: workerId,
                    availability_type: 'specific_date',
                    specific_date: dateStr,
                    is_available: false,
                })
                // Upsert, so a leftover "available" row for this date comes back with its own id
                // rather than a new one. Replacing by id keeps it from appearing twice.
                setAvailabilityState(prev => [
                    ...prev.filter(a => a.id !== response.data.id),
                    response.data,
                ])
            }
        } catch (err) {
            // An unhandled backend error reaches the browser without CORS headers, so axios
            // reports a bare network error with no response body — hence the fallback text.
            setError(err.response?.data?.detail ?? 'Could not save that date. Please try again.')
        }
    }

    const clearAll = async () => {
        setError(null)
        try {
            await clearWorkerAvailability(workerId)
            setAvailabilityState([])
        } catch (err) {
            setError(
                err.response?.data?.detail ?? 'Could not clear availability. Please try again.'
            )
        }
    }

    return {
        availability,
        unavailableDates,
        editableFrom,
        loading,
        error,
        toggleSpecificDate,
        clearAll,
        refetch: fetchAvailability,
    }
}
