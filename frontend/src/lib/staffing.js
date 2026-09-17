/**
 * How well a generated schedule is staffed.
 *
 * Kept pure and free of React, like `rota.js` and `dashboard.js`. It lives in its own module
 * rather than in `dashboard.js` because the month grid and the schedules table read it too, and
 * importing "dashboard" from a table was always a small lie about where the helper belonged.
 *
 * It takes the **schedule**, not its assignment list, because the target it will shortly be
 * measured against (the department's smallest and largest number of workers per service) is
 * resolved at generation time and stored on the schedule row — not derivable from the
 * assignments. Every call site already has the schedule in hand.
 */

/**
 * Count the workers on a schedule.
 *
 * @param {{schedule_assignments?: Array<object>}} schedule
 * @returns {{assigned: number}}
 */
export const summarizeStaffing = schedule => ({
    assigned: (schedule.schedule_assignments ?? []).length,
})
