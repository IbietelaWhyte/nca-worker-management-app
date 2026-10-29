/**
 * Draft rotas grouped for the Drafts tab. Pure and React-free, like lib/rota.js.
 */
import { format, parseISO } from 'date-fns'

/** Distinct people across some rotas: finalizing texts each of them once. */
export const countPeople = schedules =>
    new Set(schedules.flatMap(s => (s.schedule_assignments ?? []).map(a => a.worker_id))).size

/**
 * Drafts by calendar month, soonest month first and soonest date first within it.
 *
 * @param {object[]} schedules Draft schedules, in any order.
 * @returns {{key: string, year: number, month: number, label: string, schedules: object[], people: number}[]}
 */
export const groupByMonth = schedules => {
    const months = new Map()
    for (const schedule of schedules) {
        const key = schedule.scheduled_date.slice(0, 7)
        if (!months.has(key)) months.set(key, [])
        months.get(key).push(schedule)
    }
    return [...months.entries()]
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([key, items]) => {
            const sorted = [...items].sort(
                (a, b) =>
                    a.scheduled_date.localeCompare(b.scheduled_date) ||
                    a.start_time.localeCompare(b.start_time)
            )
            const [year, month] = key.split('-').map(Number)
            return {
                key,
                year,
                month,
                // Parsed from local date parts: a bare yyyy-MM-dd is read as UTC and can land in
                // the previous month west of Greenwich.
                label: format(parseISO(`${key}-01T00:00:00`), 'MMMM yyyy'),
                schedules: sorted,
                people: countPeople(sorted),
            }
        })
}
