import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert } from '@/components/ui/alert'
import { formatSlotRange } from '@/lib/staffing'

const emptyForm = {
    name: '',
    description: '',
    min_workers_per_slot: null,
    max_workers_per_slot: null,
}

/**
 * @param {object} props
 * @param {object} [props.initial] The subteam being edited, or the empty form.
 * @param {{min: number, max: number}} [props.departmentDefaults] The department's own band, shown
 *   when this subteam inherits and used to pre-fill the inputs when somebody stops inheriting —
 *   so raising only the ceiling is one keystroke rather than two guesses.
 */
export default function SubteamForm({
    initial = emptyForm,
    departmentDefaults,
    onSubmit,
    onCancel,
}) {
    // One toggle for the pair, not two independently-clearable fields. A subteam inheriting a
    // floor of 3 while overriding its ceiling to 2 is a contradiction assembled from two rows,
    // which is why the schema forbids a half-set band outright.
    const [inherit, setInherit] = useState(initial.min_workers_per_slot == null)
    const [form, setForm] = useState({
        name: initial.name ?? '',
        description: initial.description ?? '',
        min_workers_per_slot: String(initial.min_workers_per_slot ?? departmentDefaults?.min ?? 1),
        max_workers_per_slot: String(initial.max_workers_per_slot ?? departmentDefaults?.max ?? 1),
    })
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    const handleChange = e => {
        const { name, value } = e.target
        setForm(prev => ({ ...prev, [name]: value }))
    }

    const handleSubmit = async () => {
        if (!form.name.trim()) {
            setError('Subteam name is required')
            return
        }
        const min = Number.parseInt(form.min_workers_per_slot, 10)
        const max = Number.parseInt(form.max_workers_per_slot, 10)
        if (!inherit) {
            if (!Number.isInteger(min) || min < 1) {
                setError('The fewest workers must be at least 1')
                return
            }
            if (!Number.isInteger(max) || max < min) {
                setError('The most workers must be the same as the fewest, or more')
                return
            }
        }
        setError(null)
        setLoading(true)
        try {
            await onSubmit({
                name: form.name.trim(),
                description: form.description.trim() || null,
                min_workers_per_slot: inherit ? null : min,
                max_workers_per_slot: inherit ? null : max,
            })
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Something went wrong')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="space-y-4">
            {error && (
                <Alert variant="destructive">
                    <p className="text-sm">{error}</p>
                </Alert>
            )}

            <div className="space-y-2">
                <Label htmlFor="name">Subteam name</Label>
                <Input
                    id="name"
                    name="name"
                    value={form.name}
                    onChange={handleChange}
                    placeholder="e.g. Toddlers"
                />
            </div>

            <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Input
                    id="description"
                    name="description"
                    value={form.description}
                    onChange={handleChange}
                    placeholder="Optional description"
                />
            </div>

            <div className="space-y-2">
                <Label className="flex cursor-pointer items-center gap-2 font-normal">
                    <Checkbox checked={inherit} onCheckedChange={setInherit} />
                    Use the department&apos;s numbers
                </Label>

                {/* Hidden rather than disabled when inheriting: a greyed-out number this subteam
                    is not actually using is exactly the confusion the old "leave blank" placeholder
                    was trying to talk its way out of. */}
                {inherit ? (
                    <p className="text-xs text-muted-foreground">
                        {departmentDefaults?.min != null
                            ? `Currently ${formatSlotRange(departmentDefaults.min, departmentDefaults.max)} workers per service.`
                            : 'This subteam follows the department.'}
                    </p>
                ) : (
                    <>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="min_workers_per_slot">Fewest</Label>
                                <Input
                                    id="min_workers_per_slot"
                                    name="min_workers_per_slot"
                                    type="number"
                                    inputMode="numeric"
                                    min="1"
                                    value={form.min_workers_per_slot}
                                    onChange={handleChange}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="max_workers_per_slot">Most</Label>
                                <Input
                                    id="max_workers_per_slot"
                                    name="max_workers_per_slot"
                                    type="number"
                                    inputMode="numeric"
                                    min="1"
                                    value={form.max_workers_per_slot}
                                    onChange={handleChange}
                                />
                            </div>
                        </div>
                        <p className="text-xs text-muted-foreground">
                            Used for this subteam instead of the department&apos;s numbers.
                        </p>
                    </>
                )}
            </div>

            <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={onCancel} disabled={loading}>
                    Cancel
                </Button>
                <Button onClick={handleSubmit} disabled={loading}>
                    {loading ? 'Saving...' : 'Save'}
                </Button>
            </div>
        </div>
    )
}
