import { useState, useEffect, useCallback } from 'react'
import { addDays, format, startOfToday } from 'date-fns'
import { getDepartments } from '@/api/departments'
import { getSchedulesByDepartment } from '@/api/schedules'
import { buildAttentionItems, buildUpcoming } from '@/lib/dashboard'

// How far ahead the board looks. Two months so a department that has already planned next month
// still shows something once the current one runs out.
const HORIZON_DAYS = 60

/**
 * The department board: every upcoming service across the departments the viewer can see.
 *
 * Scope comes from the server, not from a role check here — `GET /departments` already returns
 * only the departments a head of department manages, and all of them for an admin. Callers must
 * still gate on `isDepartmentHead`, because a plain worker falls through that endpoint to the
 * full list.
 *
 * There is no whole-church schedule endpoint, so this fans out one request per department. Fine
 * at a handful; worth a real endpoint past ~15.
 *
 * @param {{enabled?: boolean}} options Pass `enabled: false` to skip fetching entirely.
 */
export function useDashboard({ enabled = true } = {}) {
    const [departments, setDepartments] = useState([])
    const [upcoming, setUpcoming] = useState([])
    const [attention, setAttention] = useState([])
    const [loading, setLoading] = useState(enabled)
    const [error, setError] = useState(null)

    const fetchDashboard = useCallback(async () => {
        if (!enabled) {
            setLoading(false)
            return
        }
        try {
            setLoading(true)
            setError(null)

            const today = startOfToday()
            const { data: depts } = await getDepartments()

            const results = await Promise.all(
                depts.map(async department => {
                    const { data } = await getSchedulesByDepartment(department.id, {
                        from: format(today, 'yyyy-MM-dd'),
                        to: format(addDays(today, HORIZON_DAYS), 'yyyy-MM-dd'),
                    })
                    return { department, schedules: data }
                })
            )

            const timeline = buildUpcoming(results, today)
            setDepartments(depts)
            setUpcoming(timeline)
            // Only an admin sees more than one department's worth of setup gaps, and only they can
            // fix a missing HOD, so the flag rides on having the whole church in view.
            setAttention(
                buildAttentionItems(timeline, depts, today, { includeSetupGaps: depts.length > 1 })
            )
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to load the dashboard')
        } finally {
            setLoading(false)
        }
    }, [enabled])

    useEffect(() => {
        fetchDashboard()
    }, [fetchDashboard])

    return { departments, upcoming, attention, loading, error, refetch: fetchDashboard }
}
