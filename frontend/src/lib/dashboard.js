/**
 * Shapes the dashboard's model from the raw per-department schedule lists.
 *
 * Kept pure and free of React, like `rota.js`, because the fiddly parts are all data:
 *
 * - **There is no whole-church schedule endpoint.** The only list is per department, so the caller
 *   fans out one request each and hands the results here to be merged into one timeline.
 * - **The API returns schedules newest-first.** `get_by_department` orders by `scheduled_date`
 *   descending, which is backwards for "what's coming up" — everything here re-sorts ascending.
 * - **Attention items are derived, not fetched.** Nothing on the backend aggregates, so every
 *   signal below is computed from the same schedules already loaded for the timeline.
 */

import { differenceInCalendarDays, endOfMonth, format, parseISO } from 'date-fns'
import { summarizeStaffing } from '@/lib/staffing'

/** A date-only string from the API, parsed without the UTC shift a bare `new Date()` would add. */
const parseDate = value => parseISO(`${value}T00:00:00`)

/**
 * Merge each department's schedules into one ascending timeline.
 *
 * @param {Array<{department: object, schedules: Array<object>}>} byDepartment
 * @param {Date} today Reference point for `daysAway`; passed in rather than read, so this stays pure.
 * @returns {Array<{schedule: object, department: object, summary: object, daysAway: number}>}
 */
export const buildUpcoming = (byDepartment, today) =>
    byDepartment
        .flatMap(({ department, schedules }) =>
            (schedules ?? []).map(schedule => ({
                schedule,
                department,
                summary: summarizeStaffing(schedule),
                daysAway: differenceInCalendarDays(parseDate(schedule.scheduled_date), today),
            }))
        )
        // Two departments can meet on the same date, so break the tie by name to keep the order
        // stable across reloads rather than leaving it to flatMap's arrival order.
        .sort(
            (a, b) =>
                a.schedule.scheduled_date.localeCompare(b.schedule.scheduled_date) ||
                a.department.name.localeCompare(b.department.name)
        )

/**
 * The things worth acting on, most urgent first.
 *
 * Deliberately narrow: every item here is derivable from schedules already loaded. It used to
 * lead on who had declined and who had not replied; neither exists now that workers are told
 * their duties rather than asked about them. What is left is coverage — a department with
 * nothing on the rota — and setup gaps. The signal that replaces the old two is staffing against
 * the numbers a department asked for, which needs the minimum and maximum this app does not
 * store yet.
 *
 * @param {Array<object>} upcoming Output of `buildUpcoming`.
 * @param {Array<object>} departments Departments the viewer can see.
 * @param {Date} today
 * @param {{includeSetupGaps?: boolean}} options `includeSetupGaps` adds admin-only items.
 * @returns {Array<{id: string, severity: 'high'|'medium'|'low', title: string, detail: string, href: string}>}
 */
export const buildAttentionItems = (
    upcoming,
    departments,
    today,
    { includeSetupGaps = false } = {}
) => {
    const items = []

    // A department with nothing left this month. Checked against the month end rather than a
    // rolling window so it reads the way a rota is actually planned.
    //
    // Skipped entirely when nothing at all is coming up: the board's empty state already says so,
    // and for a head of department with one department this would just repeat it back to them.
    const monthEnd = endOfMonth(today)
    for (const department of upcoming.length === 0 ? [] : departments) {
        const remaining = upcoming.filter(
            e =>
                e.department.id === department.id &&
                parseDate(e.schedule.scheduled_date) <= monthEnd
        )
        if (remaining.length === 0) {
            items.push({
                id: `unplanned-${department.id}`,
                severity: 'medium',
                title: `${department.name} has nothing scheduled this month`,
                detail: `No services left in ${format(today, 'MMMM')}`,
                href: '/schedules',
            })
        }
    }

    if (includeSetupGaps) {
        for (const department of departments.filter(d => !d.hod_id)) {
            items.push({
                id: `nohod-${department.id}`,
                severity: 'low',
                title: `${department.name} has no head of department`,
                detail: 'Nobody can generate its rota',
                href: `/departments/${department.id}`,
            })
        }
    }

    const order = { high: 0, medium: 1, low: 2 }
    return items.sort((a, b) => order[a.severity] - order[b.severity])
}

/**
 * A worker's own upcoming duties: the next one, and the rest.
 *
 * The only filter is the date. A duty is a duty — there is no longer an answer that removes one
 * from the list, so anything still on the rota is still expected of them.
 *
 * @param {Array<object>} assignments From `getWorkerAssignments`, any date.
 * @param {Date} today
 * @returns {{next: object|null, later: Array<object>}}
 */
export const buildMyDuties = (assignments, today) => {
    const upcoming = (assignments ?? [])
        .filter(a => a.schedules && parseDate(a.schedules.scheduled_date) >= today)
        .sort((a, b) => a.schedules.scheduled_date.localeCompare(b.schedules.scheduled_date))

    return { next: upcoming[0] ?? null, later: upcoming.slice(1) }
}
