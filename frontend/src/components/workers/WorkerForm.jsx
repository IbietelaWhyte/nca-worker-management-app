import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert } from '@/components/ui/alert'

const emptyForm = {
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
}

export default function WorkerForm({ initial = emptyForm, onSubmit, onCancel }) {
    const [form, setForm] = useState(initial)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    const handleChange = e => {
        const { name, value } = e.target
        setForm(prev => ({ ...prev, [name]: value }))
    }

    const handleSubmit = async () => {
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

            <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                    <Label htmlFor="first_name">First name</Label>
                    <Input
                        id="first_name"
                        name="first_name"
                        value={form.first_name}
                        onChange={handleChange}
                        placeholder="Jane"
                    />
                </div>
                <div className="space-y-2">
                    <Label htmlFor="last_name">Last name</Label>
                    <Input
                        id="last_name"
                        name="last_name"
                        value={form.last_name}
                        onChange={handleChange}
                        placeholder="Smith"
                    />
                </div>
            </div>

            <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                    id="email"
                    name="email"
                    type="email"
                    value={form.email}
                    onChange={handleChange}
                    placeholder="jane@example.com"
                />
            </div>

            <div className="space-y-2">
                <Label htmlFor="phone">Phone</Label>
                <Input
                    id="phone"
                    name="phone"
                    type="tel"
                    value={form.phone}
                    onChange={handleChange}
                    placeholder="+1 (555) 000-0000"
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
