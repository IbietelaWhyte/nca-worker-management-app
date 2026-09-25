/**
 * Rendering special-service rules as sentences.
 *
 * React-free, like `rota.js`, `dashboard.js` and `staffing.js`. A rule is entered as a sentence
 * with two selects — "On the [first] [Sunday] of every month" — and read back as the same
 * sentence, so nobody has to learn what `week_of_month: -1` means.
 */

/** The last occurrence in the month, whichever it turns out to be. Mirrors the schema. */
export const LAST_WEEK_OF_MONTH = -1

export const WEEK_OPTIONS = [
    { value: 1, label: 'first' },
    { value: 2, label: 'second' },
    { value: 3, label: 'third' },
    { value: 4, label: 'fourth' },
    { value: 5, label: 'fifth' },
    { value: LAST_WEEK_OF_MONTH, label: 'last' },
]

export const DAY_OPTIONS = [
    { value: 'sunday', label: 'Sunday' },
    { value: 'monday', label: 'Monday' },
    { value: 'tuesday', label: 'Tuesday' },
    { value: 'wednesday', label: 'Wednesday' },
    { value: 'thursday', label: 'Thursday' },
    { value: 'friday', label: 'Friday' },
    { value: 'saturday', label: 'Saturday' },
]

const titleCase = word => (word ? word[0].toUpperCase() + word.slice(1) : word)

/**
 * One rule or date as a sentence a person reads.
 *
 * @param {{kind: string, day_of_week?: string, week_of_month?: number, service_date?: string}} service
 * @returns {string}
 */
export const describeSpecialService = service => {
    if (service.kind === 'one_off') {
        // Parsed as local midnight, not UTC: `new Date('2026-08-02')` is UTC and renders as
        // the 1st anywhere west of Greenwich.
        const parsed = new Date(`${service.service_date}T00:00:00`)
        return parsed.toLocaleDateString(undefined, {
            weekday: 'long',
            day: 'numeric',
            month: 'long',
            year: 'numeric',
        })
    }

    const week = WEEK_OPTIONS.find(w => w.value === service.week_of_month)?.label ?? ''
    return `Every ${week} ${titleCase(service.day_of_week ?? '')} of the month`
        .replace(/\s+/g, ' ')
        .trim()
}

/**
 * The note under a fifth-occurrence rule.
 *
 * Not a warning — a rule that fires eight months a year is a legitimate thing to want — but
 * somebody choosing "fifth" should know it will skip most months rather than wonder later.
 *
 * @param {number|null|undefined} weekOfMonth
 * @returns {string|null}
 */
export const weekCaveat = weekOfMonth =>
    weekOfMonth === 5 ? 'Most months have no fifth — this will simply not fire in those.' : null
