import { useState } from 'react'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

/**
 * How many lead times the form will accept. One under the schema's five, so the cap a person
 * meets is this message rather than a 422 from Postgres. The number itself is a guard on
 * somebody's phone bill: each extra rung texts the whole department again.
 */
const MAX_LEAD_TIMES = 4

/** A year out is a typo, not a plan. Mirrors chk_reminder_days on schedules. */
const MAX_DAYS = 365

/**
 * One lead time as a person reads it. Zero is the case worth spelling out — "0 days before"
 * parses as a mistake, and the reminder genuinely does go out on the morning of the service.
 *
 * @param {number} days
 * @returns {string}
 */
export const describeLeadTime = days => {
    if (days === 0) return 'On the day'
    if (days === 1) return '1 day before'
    return `${days} days before`
}

/**
 * The reminder ladder for a schedule: a set of lead times in days, entered one at a time.
 *
 * Shared by the single-date and whole-month generators, which had the same number input twice.
 * A schedule's reminders are set here and nowhere else — generation is the only place they can
 * be chosen — so this is the one control that decides how often a rota texts people.
 *
 * Empty is a valid answer and deliberately reachable: a team that works off the printed rota
 * should be able to turn reminders off, and the "you have been scheduled" notice goes out
 * regardless. The field says so rather than leaving the box looking broken.
 *
 * @param {object} props
 * @param {string} props.id - Base id; the number input gets it, the label points at it.
 * @param {number[]} props.value - Current lead times, furthest out first.
 * @param {(next: number[]) => void} props.onChange - Called with the new ladder.
 */
export default function ReminderLeadTimesField({ id = 'reminder-lead-times', value, onChange }) {
    const [draft, setDraft] = useState('')
    const [error, setError] = useState(null)

    const atCapacity = value.length >= MAX_LEAD_TIMES

    const add = () => {
        const days = Number.parseInt(draft, 10)
        if (draft.trim() === '' || Number.isNaN(days)) return setError('Enter a number of days')
        if (days < 0) return setError('A reminder cannot be sent after the service')
        if (days > MAX_DAYS) return setError(`Reminders can go out at most ${MAX_DAYS} days ahead`)
        if (value.includes(days))
            return setError(`There is already a reminder ${describeLeadTime(days).toLowerCase()}`)
        if (atCapacity) return setError(`At most ${MAX_LEAD_TIMES} reminders per schedule`)

        setError(null)
        setDraft('')
        // Furthest out first, matching the order they will fire and the order the server
        // normalizes to — so the chips do not reshuffle the moment the schedule is saved.
        onChange([...value, days].sort((a, b) => b - a))
    }

    const remove = days => {
        setError(null)
        onChange(value.filter(d => d !== days))
    }

    return (
        <div className="space-y-2">
            <Label htmlFor={id}>Reminders</Label>

            {value.length > 0 && (
                <ul className="flex flex-wrap gap-2">
                    {value.map(days => (
                        <li key={days}>
                            <span className="inline-flex items-center gap-1 rounded-full bg-secondary py-1 pl-3 pr-1 text-xs font-medium text-secondary-foreground">
                                {describeLeadTime(days)}
                                <button
                                    type="button"
                                    onClick={() => remove(days)}
                                    aria-label={`Remove the reminder ${describeLeadTime(days).toLowerCase()}`}
                                    className="rounded-full p-1 hover:bg-background/60"
                                >
                                    <X size={12} />
                                </button>
                            </span>
                        </li>
                    ))}
                </ul>
            )}

            <div className="flex items-center gap-2">
                <Input
                    id={id}
                    type="number"
                    min="0"
                    max={MAX_DAYS}
                    inputMode="numeric"
                    value={draft}
                    disabled={atCapacity}
                    onChange={e => {
                        setDraft(e.target.value)
                        setError(null)
                    }}
                    // Load-bearing: both parents wrap this in a <form> whose submit generates a
                    // rota. Without it, pressing Enter to add a lead time generates the schedule.
                    onKeyDown={e => {
                        if (e.key !== 'Enter') return
                        e.preventDefault()
                        add()
                    }}
                    placeholder="Days before"
                    className="w-32"
                />
                <Button type="button" variant="outline" onClick={add} disabled={atCapacity}>
                    Add
                </Button>
            </div>

            {error && <p className="text-xs text-destructive">{error}</p>}

            <p className="text-xs text-muted-foreground">
                {value.length === 0
                    ? 'No reminders. Workers are still told once, when the rota is generated.'
                    : atCapacity
                      ? `That is the most reminders a schedule can send (${MAX_LEAD_TIMES}).`
                      : 'Each worker gets one text per day a reminder falls due, however many duties it covers.'}
            </p>
        </div>
    )
}
