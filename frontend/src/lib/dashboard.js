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

/**
 * Count an assignment list by status.
 *
 * Lives here rather than in a component because three places need it: the month calendar, the
 * schedules table, and the dashboard.
 *
 * @param {Array<{status: string}>} assignments
 * @returns {{confirmed: number, declined: number, pending: number, total: number}}
 */
export const summarizeAssignments = assignments => {
    const list = assignments ?? []
    const confirmed = list.filter(a => a.status === 'confirmed').length
    const declined = list.filter(a => a.status === 'declined').length
    return { confirmed, declined, pending: list.length - confirmed - declined, total: list.length }
}

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
                summary: summarizeAssignments(schedule.schedule_assignments),
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
 * Deliberately narrow: every item here is derivable from schedules already loaded. Availability
 * coverage is the obvious omission — `availability_prompts` records that a prompt was *sent* and
 * has no per-recipient rows, so "who hasn't replied" cannot be answered without a schema change.
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

    for (const entry of upcoming) {
        const { schedule, department, summary, daysAway } = entry
        const when = format(parseDate(schedule.scheduled_date), 'd MMMM')

        if (summary.declined > 0) {
            // Naming the one person who dropped out is the difference between a notification and
            // something the head of department can act on without opening the rota.
            const declined = (schedule.schedule_assignments ?? []).filter(
                a => a.status === 'declined'
            )
            const who =
                summary.declined === 1 && declined[0]?.workers
                    ? `${declined[0].workers.first_name} ${declined[0].workers.last_name} declined`
                    : `${summary.declined} people have declined`
            items.push({
                id: `declined-${schedule.id}`,
                severity: 'high',
                title: `${who} ${when}`,
                detail: `${department.name} is ${summary.declined === 1 ? 'one' : summary.declined} short`,
                href: `/schedules/${schedule.id}`,
            })
        }

        // Silent on a rota nobody has answered — the state that quietly becomes a Sunday morning
        // problem. Only worth raising once the date is close enough to act on.
        if (
            summary.total > 0 &&
            summary.confirmed === 0 &&
            summary.declined === 0 &&
            daysAway <= 14
        ) {
            items.push({
                id: `silent-${schedule.id}`,
                severity: 'high',
                title: `Nobody has replied for ${department.name} on ${when}`,
                detail: `All ${summary.total} still pending`,
                href: `/schedules/${schedule.id}`,
            })
        }
    }

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
 * Split a worker's own assignments into the ones they still owe an answer on and the rest.
 *
 * @param {Array<object>} assignments From `getWorkerAssignments`, any date, any status.
 * @param {Date} today
 * @returns {{next: object|null, awaitingReply: Array<object>, later: Array<object>}}
 */
export const buildMyDuties = (assignments, today) => {
    const upcoming = (assignments ?? [])
        .filter(a => a.schedules && parseDate(a.schedules.scheduled_date) >= today)
        .filter(a => a.status !== 'declined')
        .sort((a, b) => a.schedules.scheduled_date.localeCompare(b.schedules.scheduled_date))

    return {
        next: upcoming[0] ?? null,
        awaitingReply: upcoming.filter(a => a.status === 'pending'),
        later: upcoming.slice(1),
    }
}
