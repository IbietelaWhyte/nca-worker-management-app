/**
 * How well a generated schedule is staffed.
 *
 * Kept pure and free of React, like `rota.js` and `dashboard.js`. It lives in its own module
 * rather than in `dashboard.js` because the month grid and the schedules table read it too, and
 * importing "dashboard" from a table was always a small lie about where the helper belonged.
 *
 * It takes the **schedule**, not its assignment list, because the target it is measured against
 * is resolved at generation and stored on the schedule row — not derivable from the assignments,
 * and deliberately frozen so a March rota keeps reading correctly after the department's numbers
 * change in June. Every call site already has the schedule in hand.
 */

/**
 * Count a schedule's workers against the band it was generated for.
 *
 * The `?? assigned` fallbacks matter: schedules created before the band existed have no
 * minimum or maximum, and they should read as "fine" rather than "0 needed".
 *
 * @param {{schedule_assignments?: Array<object>, min_workers?: number|null, max_workers?: number|null}} schedule
 * @returns {{assigned: number, min: number, max: number, short: number, understaffed: boolean, full: boolean}}
 */
export const summarizeStaffing = schedule => {
    const assigned = (schedule.schedule_assignments ?? []).length
    const min = schedule.min_workers ?? assigned
    const max = schedule.max_workers ?? assigned
    return {
        assigned,
        min,
        max,
        short: Math.max(min - assigned, 0),
        understaffed: assigned < min,
        full: assigned >= max,
    }
}

/**
 * A band as a person reads it: "3" when both ends agree, "3–5" otherwise.
 *
 * En dash, matching the time ranges elsewhere in the app. Anything that reaches a rendered
 * JPEG or an SMS uses a plain hyphen instead — see RotaExportDialog and SMSService.
 *
 * @param {number|null|undefined} min
 * @param {number|null|undefined} max
 * @returns {string}
 */
export const formatSlotRange = (min, max) => {
    if (min == null || max == null) return '—'
    return min === max ? `${min}` : `${min}–${max}`
}

/**
 * A subteam's own band, or the department's when it inherits.
 *
 * Both bounds or neither — the schema enforces it — so one null check settles the pair. Mirrors
 * `staffing_band` in the subteam service, which is what actually decides the rota.
 *
 * @param {{min_workers_per_slot?: number|null, max_workers_per_slot?: number|null}|null|undefined} subteam
 * @param {{min_workers_per_slot?: number, max_workers_per_slot?: number}|null|undefined} department
 * @returns {{min: number|null, max: number|null}}
 */
export const resolveSlotRange = (subteam, department) =>
    subteam?.min_workers_per_slot == null
        ? {
              min: department?.min_workers_per_slot ?? null,
              max: department?.max_workers_per_slot ?? null,
          }
        : { min: subteam.min_workers_per_slot, max: subteam.max_workers_per_slot }

/**
 * A subteam's role requirements as a phrase: "Needs 1 Teacher, 2 Helper". Null when there are
 * none, or none whose role still exists. Role names are used as written, so no plural is added.
 *
 * @param {{department_role_id: string, min_count: number}[]|undefined} requirements
 * @param {{id: string, name: string}[]} roles The department's roles.
 * @returns {string|null}
 */
export const describeRoleRequirements = (requirements, roles) => {
    const names = Object.fromEntries(roles.map(role => [role.id, role.name]))
    const parts = (requirements ?? [])
        .filter(r => names[r.department_role_id])
        .map(r => `${r.min_count} ${names[r.department_role_id]}`)
    return parts.length ? `Needs ${parts.join(', ')}` : null
}
