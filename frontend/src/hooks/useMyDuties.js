import { useState, useEffect, useCallback } from 'react'
import { startOfToday } from 'date-fns'
import { getMyProfile } from '@/api/account'
import { getWorkerAssignments, updateAssignmentStatus } from '@/api/schedules'
import { buildMyDuties } from '@/lib/dashboard'

/**
 * A worker's own upcoming duties, for the dashboard they land on.
 *
 * Two calls rather than one: nothing in the Supabase session carries a worker id (`auth_user_id`
 * is excluded from the API's worker schema), so `GET /account/me` resolves it first. That is the
 * clean route — `AvailabilityPage` matches on email against the whole worker list instead, which
 * a plain worker cannot rely on because that list is scoped to people they may manage.
 *
 * @param {{enabled?: boolean}} options
 */
export function useMyDuties({ enabled = true } = {}) {
    const [duties, setDuties] = useState({ next: null, awaitingReply: [], later: [] })
    const [loading, setLoading] = useState(enabled)
    const [error, setError] = useState(null)
    // Null when the signed-in account has no worker record behind it — a real state, and different
    // from "nothing scheduled", so the page can say so instead of showing an empty rota.
    const [profile, setProfile] = useState(null)

    const fetchDuties = useCallback(async () => {
        if (!enabled) {
            setLoading(false)
            return
        }
        try {
            setLoading(true)
            setError(null)
            const { data: me } = await getMyProfile()
            setProfile(me)
            const { data: assignments } = await getWorkerAssignments(me.id)
            setDuties(buildMyDuties(assignments, startOfToday()))
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to load your duties')
        } finally {
            setLoading(false)
        }
    }, [enabled])

    useEffect(() => {
        fetchDuties()
    }, [fetchDuties])

    const answer = async (assignmentId, status) => {
        await updateAssignmentStatus(assignmentId, status)
        // Refetch rather than patch: declining removes the duty from the list and can promote a
        // later one into the "next" slot, which is more re-derivation than a local splice is worth.
        await fetchDuties()
    }

    return { ...duties, profile, loading, error, refetch: fetchDuties, answer }
}
