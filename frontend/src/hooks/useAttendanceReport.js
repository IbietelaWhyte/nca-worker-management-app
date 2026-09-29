import { useState, useEffect, useCallback, useMemo } from 'react'
import { endOfMonth, format, startOfMonth, subMonths } from 'date-fns'
import { getAbsenceReport } from '@/api/attendance'

/**
 * A department's attendance over a window.
 *
 * One control with three presets rather than two date pickers: the report answers "who missed
 * this month?" and "who keeps missing?" at different scales, and those are the same question
 * asked over a longer window. The month window itself is the `startOfMonth`/`endOfMonth` +
 * `yyyy-MM-dd` idiom `useSchedules` already uses, so the two pages bound their fetches the same way.
 *
 * In a rolling preset the arrows still step by one month — the window slides rather than
 * resizing, which is what "rolling" means.
 */
const MONTHS_BACK = { month: 1, quarter: 3, half: 6 }

export function useAttendanceReport(departmentId) {
    const [report, setReport] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [range, setRange] = useState('month')
    const [month, setMonth] = useState(() => startOfMonth(new Date()))

    const bounds = useMemo(() => {
        const to = endOfMonth(month)
        const from = startOfMonth(subMonths(month, MONTHS_BACK[range] - 1))
        return { from: format(from, 'yyyy-MM-dd'), to: format(to, 'yyyy-MM-dd') }
    }, [month, range])

    const fetchReport = useCallback(async () => {
        if (!departmentId) {
            setReport(null)
            setLoading(false)
            return
        }
        try {
            setLoading(true)
            setError(null)
            const response = await getAbsenceReport(departmentId, bounds)
            setReport(response.data)
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to load the attendance report')
        } finally {
            setLoading(false)
        }
    }, [departmentId, bounds])

    useEffect(() => {
        fetchReport()
    }, [fetchReport])

    return {
        report,
        loading,
        error,
        range,
        setRange,
        month,
        setMonth,
        bounds,
        refetch: fetchReport,
    }
}
