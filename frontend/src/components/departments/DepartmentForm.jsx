import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert } from '@/components/ui/alert'

const emptyForm = {
    name: '',
    description: '',
    min_workers_per_slot: 1,
    max_workers_per_slot: 1,
}

export default function DepartmentForm({ initial = emptyForm, onSubmit, onCancel }) {
    const [form, setForm] = useState({
        name: initial.name ?? '',
        description: initial.description ?? '',
        // Held as strings so the inputs can be transiently empty while somebody retypes them;
        // parsed on submit. Sending "3" to a smallint column is what the single untyped field
        // this replaced used to do.
        min_workers_per_slot: String(initial.min_workers_per_slot ?? 1),
        max_workers_per_slot: String(initial.max_workers_per_slot ?? 1),
    })
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    const handleChange = e => {
        const { name, value } = e.target
        setForm(prev => ({ ...prev, [name]: value }))
    }

    const handleSubmit = async () => {
        if (!form.name.trim()) {
            setError('Department name is required')
            return
        }
        const min = Number.parseInt(form.min_workers_per_slot, 10)
        const max = Number.parseInt(form.max_workers_per_slot, 10)
        if (!Number.isInteger(min) || min < 1) {
            setError('The fewest workers must be at least 1')
            return
        }
        if (!Number.isInteger(max) || max < min) {
            setError('The most workers must be the same as the fewest, or more')
            return
        }
        setError(null)
        setLoading(true)
        try {
            await onSubmit({
                name: form.name.trim(),
                // Null rather than "": the column is nullable, and an empty string is a value.
                description: form.description.trim() || null,
                min_workers_per_slot: min,
                max_workers_per_slot: max,
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
                <Label htmlFor="name">Department name</Label>
                <Input
                    id="name"
                    name="name"
                    value={form.name}
                    onChange={handleChange}
                    placeholder="e.g. Ushers"
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
                {/* Two columns at every width, not stacked below sm: they are one setting
                    stated as a pair, and reading them apart invites setting only one. */}
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
                    Workers per service. The rota fills up to the most when enough people are free,
                    and only warns you below the fewest.
                </p>
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
