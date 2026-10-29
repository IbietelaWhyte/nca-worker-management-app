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
 * @param {{id: string, name: string}[]} [props.roles] The department's roles, each of which can be
 *   given a minimum count on this subteam's rotas.
 * @param {(subteam: object, requirements: {department_role_id: string, min_count: number}[]) => Promise} props.onSubmit
 *   Called with the subteam fields and the complete set of role requirements (empty clears them).
 */
export default function SubteamForm({
    initial = emptyForm,
    departmentDefaults,
    roles = [],
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
    // role id -> count as typed. Blank and 0 both mean "no requirement", which is stored as no row.
    const [roleCounts, setRoleCounts] = useState(() =>
        Object.fromEntries(
            (initial.role_requirements ?? []).map(r => [r.department_role_id, String(r.min_count)])
        )
    )
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    const requirements = roles
        .map(role => ({
            department_role_id: role.id,
            min_count: Number.parseInt(roleCounts[role.id] ?? '', 10) || 0,
        }))
        .filter(r => r.min_count > 0)
    const requiredTotal = requirements.reduce((sum, r) => sum + r.min_count, 0)
    // The planner never passes the maximum, so a larger total could never be met. The server
    // refuses it too; checking here says so before the head presses Save.
    const ceiling = inherit
        ? departmentDefaults?.max
        : Number.parseInt(form.max_workers_per_slot, 10)
    const overCeiling = Number.isInteger(ceiling) && requiredTotal > ceiling

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
        if (overCeiling) {
            setError(
                `The roles add up to ${requiredTotal}, but this subteam takes at most ${ceiling}`
            )
            return
        }
        setError(null)
        setLoading(true)
        try {
            await onSubmit(
                {
                    name: form.name.trim(),
                    description: form.description.trim() || null,
                    min_workers_per_slot: inherit ? null : min,
                    max_workers_per_slot: inherit ? null : max,
                },
                requirements
            )
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

            {roles.length > 0 && (
                <div className="space-y-2">
                    <Label>Roles needed on each rota</Label>
                    <p className="text-xs text-muted-foreground">
                        The least of each role a rota for this subteam must have. They are picked
                        first, by turn; any places left go to whoever is next, whatever their role.
                        Leave at 0 for no requirement.
                    </p>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                        {roles.map(role => (
                            <div key={role.id} className="flex items-center justify-between gap-3">
                                <Label htmlFor={`role-count-${role.id}`} className="font-normal">
                                    {role.name}
                                </Label>
                                <Input
                                    id={`role-count-${role.id}`}
                                    type="number"
                                    inputMode="numeric"
                                    min="0"
                                    className="w-20"
                                    value={roleCounts[role.id] ?? '0'}
                                    onChange={e =>
                                        setRoleCounts(prev => ({
                                            ...prev,
                                            [role.id]: e.target.value,
                                        }))
                                    }
                                />
                            </div>
                        ))}
                    </div>
                    {requiredTotal > 0 && (
                        <p
                            className={`text-xs ${overCeiling ? 'text-destructive' : 'text-muted-foreground'}`}
                        >
                            {Number.isInteger(ceiling)
                                ? `${requiredTotal} required, of at most ${ceiling} per service.`
                                : `${requiredTotal} required per service.`}
                        </p>
                    )}
                </div>
            )}

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
