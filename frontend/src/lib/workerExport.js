/**
 * Worker lists as spreadsheet rows, for the Workers page and a department's Members tab, and one
 * worker's schedule history. Pure and React-free, like attendance.js's toAbsenceCsv; lib/csv.js
 * does the escaping.
 */
import { ABSENT, EXCUSED, LATE, NOT_RECORDED, PRESENT, attendanceState } from '@/lib/attendance'

const ROLE_LABELS = { admin: 'Admin', hod: 'HOD', assistant_hod: 'Assistant HOD', worker: 'Worker' }

const roleNames = roles => (roles ?? []).map(role => ROLE_LABELS[role] ?? role).join('; ')

/**
 * Phones are stored as E.164 ("+14165550101"). Written as-is, the leading "+" is a formula
 * character, so csv.js prefixes an apostrophe that a spreadsheet opening the file shows
 * literally, on every row. A North American number is written "(416) 555-0101" instead: it is
 * how people read it on a printed list, a spreadsheet keeps it as text, and the CSV import's
 * normalize_phone reads it straight back. Anything else is left for csv.js to defuse.
 */
const phoneForSheet = phone => {
    if (!phone) return ''
    const nanp = /^\+1(\d{3})(\d{3})(\d{4})$/.exec(phone)
    return nanp ? `(${nanp[1]}) ${nanp[2]}-${nanp[3]}` : phone
}

const leaveText = leave => {
    if (!leave) return ''
    return leave.end_date ? `On leave to ${leave.end_date}` : 'On leave'
}

/**
 * The Workers page: everyone matching the current search and filters.
 *
 * @param {object[]} workers - WorkerResponse rows.
 * @param {Record<string, object>} leaveByWorker - worker id -> the leave they are on today.
 */
export const toWorkerCsv = (workers, leaveByWorker = {}) => ({
    headers: ['First name', 'Last name', 'Email', 'Phone', 'App roles', 'Status', 'Leave'],
    rows: workers.map(worker => [
        worker.first_name,
        worker.last_name,
        worker.email,
        phoneForSheet(worker.phone),
        roleNames(worker.roles),
        worker.is_active ? 'Active' : 'Inactive',
        leaveText(leaveByWorker[worker.id]),
    ]),
})

/**
 * A department's members, with the role and subteam each holds in *this* department — both are
 * facts about the membership, not the person, so they only make sense in this export.
 *
 * @param {object} department - DepartmentWithWorkersResponse.
 * @param {object[]} members - The members to export, in display order.
 */
export const toMemberCsv = (department, members) => ({
    headers: ['First name', 'Last name', 'Email', 'Phone', 'Role', 'Subteam', 'Head of department'],
    rows: members.map(worker => [
        worker.first_name,
        worker.last_name,
        worker.email,
        phoneForSheet(worker.phone),
        worker.department_role?.name ?? '',
        worker.subteam?.name ?? '',
        worker.id === department.hod_id ? 'Yes' : '',
    ]),
})

const ATTENDANCE_LABELS = {
    [PRESENT]: 'Present',
    [LATE]: 'Late',
    [ABSENT]: 'Absent',
    [EXCUSED]: 'Excused',
    [NOT_RECORDED]: 'Not recorded',
}

/**
 * One worker's duties for the history dialog: the year's dates newest first, plus the two facts a
 * head checks for fairness - how many this year, and when they last served.
 *
 * @param {object[]} assignments From GET /schedules/workers/{id}/assignments (finalized only).
 * @param {number} year The calendar year to summarise.
 * @param {string} today yyyy-MM-dd, so "last served" never counts a date still to come.
 */
export const summarizeHistory = (assignments, year, today) => {
    const dated = assignments.filter(a => a.schedules?.scheduled_date)
    const inYear = dated
        .filter(a => a.schedules.scheduled_date.startsWith(`${year}-`))
        .sort((a, b) => b.schedules.scheduled_date.localeCompare(a.schedules.scheduled_date))
    const past = dated.map(a => a.schedules.scheduled_date).filter(d => d <= today)
    const upcoming = dated.map(a => a.schedules.scheduled_date).filter(d => d > today)
    return {
        rows: inYear,
        count: inYear.length,
        lastServed: past.length ? past.sort().at(-1) : null,
        next: upcoming.length ? upcoming.sort()[0] : null,
        years: [...new Set(dated.map(a => Number(a.schedules.scheduled_date.slice(0, 4))))],
    }
}

/** A worker's duties as spreadsheet rows. Attendance says "Upcoming" for a date not yet reached. */
export const toHistoryCsv = (rows, today) => ({
    headers: ['Date', 'Start', 'Department', 'Rota', 'Role', 'Special service', 'Attendance'],
    rows: rows.map(a => [
        a.schedules.scheduled_date,
        a.schedules.start_time?.slice(0, 5) ?? '',
        a.schedules.departments?.name ?? '',
        a.schedules.title,
        a.department_roles?.name ?? '',
        a.schedules.special_service_name ?? '',
        a.schedules.scheduled_date > today
            ? 'Upcoming'
            : (ATTENDANCE_LABELS[attendanceState(a)] ?? ''),
    ]),
})
