/**
 * Worker lists as spreadsheet rows, for the Workers page and a department's Members tab. Pure and
 * React-free, like attendance.js's toAbsenceCsv; lib/csv.js does the escaping.
 */

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
