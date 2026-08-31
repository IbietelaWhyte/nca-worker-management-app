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
 */

import { format, parseISO } from 'date-fns'

// Assignments belonging to no subteam (a department-only schedule) collect under this label.
const DEPARTMENT_GROUP_LABEL = 'Department'
const DEPARTMENT_GROUP_KEY = ''

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

/**
 * Group a month's schedules into one block of rows per date.
 *
 * @param {Array} schedules - ScheduleResponse[] for the month, assignments embedded.
 * @param {Array} subteams - The department's subteams, so unstaffed groups still get a row.
 * @returns {Array} [{ date, label, rows: [{ key, label, names, indented, highlighted }] }]
 */
export function buildRota(schedules, subteams) {
    const assignmentsByDate = new Map()
    for (const schedule of schedules ?? []) {
        const forDate = assignmentsByDate.get(schedule.scheduled_date) ?? []
        // A worker with no embedded record can't be named, so it can't be printed.
        forDate.push(...(schedule.schedule_assignments ?? []).filter(a => a.workers))
        assignmentsByDate.set(schedule.scheduled_date, forDate)
    }

    const groups = new Map()
    const ensureGroup = (key, label) => {
        if (!groups.has(key)) groups.set(key, { key, label, helperRoles: new Map() })
        return groups.get(key)
    }

    // Seed from the department's own subteams so a group with nobody on it all month still shows.
    for (const subteam of [...(subteams ?? [])].sort((a, b) => a.name.localeCompare(b.name))) {
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

    // Subteams alphabetically, with the catch-all department group last.
    const ordered = [...groups.values()].sort((a, b) => {
        if (a.key === DEPARTMENT_GROUP_KEY) return 1
        if (b.key === DEPARTMENT_GROUP_KEY) return -1
        return a.label.localeCompare(b.label)
    })

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

        return { date, label: format(parseISO(date), 'dd-MMM-yy'), rows }
    })
}
