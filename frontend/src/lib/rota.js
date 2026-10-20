/**
 * Builds the printable rota model for one month — the shape the export image renders.
 *
 * Kept pure and free of React so the awkward parts stay in one readable place:
 *
 * - **A date can span several schedules.** A department-wide month writes one schedule per date
 *   holding every subteam's assignments, while a subteam-scoped month writes one schedule *per
 *   subteam* per date. Assignments are therefore merged by date before anything else.
 * - **Order is not given to us.** PostgREST applies no ORDER BY to embedded assignments, so names
 *   would shuffle between reloads unless sorted explicitly.
 * - **Rows are fixed for the whole month.** Every group gets a row on every date, blank where
 *   nobody is assigned, so the columns line up down the page.
 * - **Group order is the head's choice, with a default.** `order` lists group keys to put first;
 *   anything it does not name — no saved order, or a subteam created since — follows
 *   alphabetically with the Department group last. See `lib/rotaOrder.js` for where it is kept.
 */

import { format, parseISO } from 'date-fns'

// Assignments belonging to no subteam (a department-only schedule) collect under this label.
const DEPARTMENT_GROUP_LABEL = 'Department'
export const DEPARTMENT_GROUP_KEY = ''

const normalize = value => (value ?? '').trim().toLowerCase()

/**
 * Whether a department role is a "helper" job, rendered as its own highlighted row beneath its
 * subteam rather than merged into it. Matches the printed rota, where helpers sit under the
 * group they assist. The seeded Children's Ministry roles are literally "Teacher" and "Assistant".
 */
export const isHelperRole = roleName => {
    const name = normalize(roleName)
    return name.startsWith('helper') || name.startsWith('asst') || name === 'assistant'
}

const workerName = assignment => `${assignment.workers.first_name} ${assignment.workers.last_name}`

// Surnames first, matching how the rota has always been written up by hand.
const bySurname = (a, b) =>
    a.workers.last_name.localeCompare(b.workers.last_name) ||
    a.workers.first_name.localeCompare(b.workers.first_name)

const namesFor = assignments => assignments.slice().sort(bySurname).map(workerName).join(', ')

// The default: subteams alphabetically, with the catch-all department group last.
const alphabetical = (a, b) => {
    if (a.key === DEPARTMENT_GROUP_KEY) return 1
    if (b.key === DEPARTMENT_GROUP_KEY) return -1
    return a.label.localeCompare(b.label)
}

/**
 * Put groups in a saved order: the keys `order` names first, in that order, then everything else
 * by the default. Keys for groups that no longer exist (a deleted subteam) are simply skipped.
 *
 * @param {Array} groups - [{ key, label, ... }]
 * @param {Array<string>} order - Group keys to lead with.
 * @returns {Array} The same groups, ordered.
 */
export function orderGroups(groups, order = []) {
    const byKey = new Map(groups.map(group => [group.key, group]))
    const leading = order.filter(key => byKey.has(key)).map(key => byKey.get(key))
    const named = new Set(leading.map(group => group.key))
    const rest = groups.filter(group => !named.has(group.key)).sort(alphabetical)
    return [...leading, ...rest]
}

// Merge the month's schedules by date: one list of assignments, and any special-service name.
const byDate = schedules => {
    const assignmentsByDate = new Map()
    const specialByDate = new Map()
    for (const schedule of schedules ?? []) {
        const forDate = assignmentsByDate.get(schedule.scheduled_date) ?? []
        // A worker with no embedded record can't be named, so it can't be printed.
        forDate.push(...(schedule.schedule_assignments ?? []).filter(a => a.workers))
        assignmentsByDate.set(schedule.scheduled_date, forDate)
        if (schedule.special_service_name) {
            specialByDate.set(schedule.scheduled_date, schedule.special_service_name)
        }
    }
    return { assignmentsByDate, specialByDate }
}

const discoverGroups = (assignmentsByDate, subteams) => {
    const groups = new Map()
    const ensureGroup = (key, label) => {
        if (!groups.has(key)) groups.set(key, { key, label, helperRoles: new Map() })
        return groups.get(key)
    }

    // Seed from the department's own subteams so a group with nobody on it all month still shows.
    for (const subteam of subteams ?? []) {
        ensureGroup(subteam.id, subteam.name)
    }

    // Then walk the month once to discover which helper roles each group actually uses.
    for (const assignments of assignmentsByDate.values()) {
        for (const assignment of assignments) {
            const group = ensureGroup(
                assignment.subteam_id ?? DEPARTMENT_GROUP_KEY,
                assignment.subteams?.name ?? DEPARTMENT_GROUP_LABEL
            )
            const roleName = assignment.department_roles?.name
            if (isHelperRole(roleName)) {
                group.helperRoles.set(assignment.department_role_id, roleName)
            }
        }
    }
    return [...groups.values()]
}

/**
 * The groups a month's rota will show, in the order it will show them.
 *
 * What the order dialog lists, so it offers exactly the rows the image will have.
 *
 * @param {Array} schedules - ScheduleResponse[] for the month, assignments embedded.
 * @param {Array} subteams - The department's subteams, so unstaffed groups still appear.
 * @param {Array<string>} order - Saved group keys to lead with.
 * @returns {Array} [{ key, label, helperRoles }]
 */
export function rotaGroups(schedules, subteams, order = []) {
    return orderGroups(discoverGroups(byDate(schedules).assignmentsByDate, subteams), order)
}

/**
 * Group a month's schedules into one block of rows per date.
 *
 * @param {Array} schedules - ScheduleResponse[] for the month, assignments embedded.
 * @param {Array} subteams - The department's subteams, so unstaffed groups still get a row.
 * @param {Array<string>} order - Saved group keys to lead with; see `orderGroups`.
 * @returns {Array} [{ date, label, specialName, rows: [{ key, label, names, indented, highlighted }] }]
 */
export function buildRota(schedules, subteams, order = []) {
    const { assignmentsByDate, specialByDate } = byDate(schedules)
    const ordered = orderGroups(discoverGroups(assignmentsByDate, subteams), order)

    return [...assignmentsByDate.keys()].sort().map(date => {
        const assignments = assignmentsByDate.get(date)
        const rows = []

        for (const group of ordered) {
            const mine = assignments.filter(
                a => (a.subteam_id ?? DEPARTMENT_GROUP_KEY) === group.key
            )
            // Everyone who isn't a helper heads the group row; helpers get their own rows
            // below, so a subteam reads as "these people, assisted by these people".
            rows.push({
                key: `${group.key}:main`,
                label: group.label,
                names: namesFor(mine.filter(a => !isHelperRole(a.department_roles?.name))),
                indented: false,
                highlighted: false,
            })
            for (const [roleId, roleName] of group.helperRoles) {
                rows.push({
                    key: `${group.key}:${roleId}`,
                    label: roleName,
                    names: namesFor(mine.filter(a => a.department_role_id === roleId)),
                    indented: true,
                    highlighted: true,
                })
            }
        }

        return {
            date,
            label: format(parseISO(date), 'dd-MMM-yy'),
            // Read off the schedule's own snapshot, so an exported rota keeps naming the
            // service after the rule behind it is renamed or deleted.
            specialName: specialByDate.get(date) ?? null,
            rows,
        }
    })
}
