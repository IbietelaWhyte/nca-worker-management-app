/**
 * Reading an attendance record, and turning a month of them into something exportable.
 *
 * Pure and React-free, like rota.js, dashboard.js and staffing.js. The three-state rule this
 * encodes is the whole feature, so it lives in one place rather than in each component:
 *
 *   neither timestamp -> not recorded   (a duty nobody took a register for)
 *   checked in        -> present, or late if the backend stamped it so
 *   marked absent     -> absent, or excused
 *
 * **Not recorded is never an absence.** It is the thing the whole design exists to keep
 * separate, and anything here that folds the two together is a bug.
 */

import { format, parseISO } from 'date-fns'

export const NOT_RECORDED = 'not_recorded'
export const PRESENT = 'present'
export const LATE = 'late'
export const ABSENT = 'absent'
export const EXCUSED = 'excused'

/** What one assignment row says happened. Mirrors `rules.state_of` on the backend. */
export const attendanceState = assignment => {
    if (!assignment) return NOT_RECORDED
    if (assignment.checked_in_at) return assignment.is_late ? LATE : PRESENT
    if (assignment.marked_absent_at) return assignment.excused ? EXCUSED : ABSENT
    return NOT_RECORDED
}

export const isHere = assignment => Boolean(assignment?.checked_in_at)

/** The tally the operator watches while taking the register. */
export const tally = (assignments = []) => {
    const counts = {
        assigned: assignments.length,
        present: 0,
        late: 0,
        absent: 0,
        excused: 0,
        notRecorded: 0,
    }
    for (const assignment of assignments) {
        const state = attendanceState(assignment)
        if (state === PRESENT || state === LATE) counts.present += 1
        if (state === LATE) counts.late += 1
        if (state === ABSENT) counts.absent += 1
        if (state === EXCUSED) counts.excused += 1
        if (state === NOT_RECORDED) counts.notRecorded += 1
    }
    return counts
}

/**
 * Whether a row is worth a head's attention.
 *
 * Two rules, because `3 of 12` and `2 of 3` each deserve a conversation and neither catches the
 * other: the absolute count finds the steady drifter, the rate finds someone who has only served
 * twice and missed both. The rate arm needs at least two recorded duties, so one missed Sunday
 * on somebody's first turn is not a flag.
 */
export const isRepeatAbsentee = (row, threshold) =>
    row.absences >= threshold || (row.duties >= 2 && row.absences / row.duties >= 0.5)

/** Share of recorded duties missed unexcused, 0-1. Zero when nothing was recorded. */
export const absenceRate = row => (row.duties ? row.absences / row.duties : 0)

export const workerName = row =>
    row.worker ? `${row.worker.first_name} ${row.worker.last_name}` : 'Unknown worker'

const readable = iso => format(parseISO(iso), 'd MMM yyyy')

/**
 * The report as a spreadsheet.
 *
 * `Not recorded` is its own column and `Absence rate` deliberately excludes it from the
 * denominator: dividing by rostered duties would flatter a department that never takes the
 * register, which is the wrong incentive to bake into the one number people will quote.
 */
export const toAbsenceCsv = report => ({
    headers: [
        'Worker',
        'Email',
        'Recorded duties',
        'Present',
        'Late',
        'Absent',
        'Excused',
        'Not recorded',
        'Absence rate',
        'Last absence',
        'Absent dates',
        'Late dates',
    ],
    rows: report.rows.map(row => [
        workerName(row),
        row.worker?.email ?? '',
        row.duties,
        row.present,
        row.late,
        row.absences,
        row.excused,
        row.not_recorded,
        `${Math.round(absenceRate(row) * 100)}%`,
        row.last_absent_on ? readable(row.last_absent_on) : '',
        (row.absent_dates ?? []).map(readable).join('; '),
        (row.late_dates ?? []).map(readable).join('; '),
    ]),
})
