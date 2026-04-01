import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert } from '@/components/ui/alert'

const emptyForm = {
    name: '',
    description: '',
    workers: '',
}

export default function DepartmentForm({ initial = emptyForm, onSubmit, onCancel }) {
    const [form, setForm] = useState({
        name: initial.name ?? '',
        description: initial.description ?? '',
        workers_per_slot: initial.workers_per_slot ?? '',
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
        setError(null)
        setLoading(true)
        try {
            await onSubmit(form)
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
                <Label htmlFor="workers_per_slot">Workers/Slot</Label>
                <Input
                    id="workers_per_slot"
                    name="workers_per_slot"
                    value={form.workers_per_slot}
                    onChange={handleChange}
                    placeholder="1"
                />
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
