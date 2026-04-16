import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { registerUser } from '@/api/authentication'
import { useDepartments } from '@/hooks/useDepartments'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert } from '@/components/ui/alert'
import { Checkbox } from '@/components/ui/checkbox'
import {
    Select,
    SelectContent,
    SelectGroup,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { ArrowLeft, UserPlus } from 'lucide-react'

const emptyForm = {
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    password: '',
    role: 'worker',
    department_ids: [],
}

export default function RegisterUser() {
    const navigate = useNavigate()
    const { departments, loading: loadingDepartments } = useDepartments()
    const [form, setForm] = useState(emptyForm)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const [success, setSuccess] = useState(false)

    const handleChange = e => {
        const { name, value } = e.target
        setForm(prev => ({ ...prev, [name]: value }))
    }

    const handleRoleChange = value => {
        setForm(prev => ({ ...prev, role: value }))
    }

    const handleDepartmentToggle = departmentId => {
        setForm(prev => ({
            ...prev,
            department_ids: prev.department_ids.includes(departmentId)
                ? prev.department_ids.filter(id => id !== departmentId)
                : [...prev.department_ids, departmentId],
        }))
    }

    const handleSubmit = async e => {
        e.preventDefault()
        setError(null)
        setSuccess(false)

        // Validate password
        if (form.password.length < 6) {
            setError('Password must be at least 6 characters')
            return
        }

        setLoading(true)
        try {
            await registerUser(form)
            setSuccess(true)
            setTimeout(() => navigate('/workers'), 1500)
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to register user')
        } finally {
            setLoading(false)
        }
    }

    const handleCancel = () => {
        navigate('/workers')
    }

    return (
        <div className="max-w-2xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Button variant="ghost" size="sm" onClick={handleCancel}>
                    <ArrowLeft size={16} className="mr-2" />
                    Back to Workers
                </Button>
            </div>

            <div>
                <h2 className="text-2xl font-bold">Register New User</h2>
                <p className="text-muted-foreground text-sm mt-1">
                    Create a new user account with authentication credentials
                </p>
            </div>

            {/* Success message */}
            {success && (
                <Alert className="bg-green-50 border-green-200">
                    <p className="text-sm text-green-800">
                        User registered successfully! Redirecting...
                    </p>
                </Alert>
            )}

            {/* Error message */}
            {error && (
                <Alert variant="destructive">
                    <p className="text-sm">{error}</p>
                </Alert>
            )}

            {/* Registration form */}
            <form onSubmit={handleSubmit} className="border rounded-lg p-6 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                        <Label htmlFor="first_name">
                            First name <span className="text-destructive">*</span>
                        </Label>
                        <Input
                            id="first_name"
                            name="first_name"
                            value={form.first_name}
                            onChange={handleChange}
                            placeholder="Jane"
                            required
                        />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="last_name">
                            Last name <span className="text-destructive">*</span>
                        </Label>
                        <Input
                            id="last_name"
                            name="last_name"
                            value={form.last_name}
                            onChange={handleChange}
                            placeholder="Smith"
                            required
                        />
                    </div>
                </div>

                <div className="space-y-2">
                    <Label htmlFor="email">
                        Email <span className="text-destructive">*</span>
                    </Label>
                    <Input
                        id="email"
                        name="email"
                        type="email"
                        value={form.email}
                        onChange={handleChange}
                        placeholder="jane@example.com"
                        required
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

                <div className="space-y-2">
                    <Label htmlFor="password">
                        Password <span className="text-destructive">*</span>
                    </Label>
                    <Input
                        id="password"
                        name="password"
                        type="password"
                        value={form.password}
                        onChange={handleChange}
                        placeholder="••••••••"
                        required
                    />
                    <p className="text-xs text-muted-foreground">
                        Password must be at least 6 characters
                    </p>
                </div>

                <div className="space-y-2">
                    <Label htmlFor="role">
                        Role <span className="text-destructive">*</span>
                    </Label>
                    <Select value={form.role} onValueChange={handleRoleChange}>
                        <SelectTrigger id="role" className="w-full">
                            <SelectValue placeholder="Select a role" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectGroup>
                                <SelectItem value="worker">Worker</SelectItem>
                                <SelectItem value="hod">Head of Department (HOD)</SelectItem>
                                <SelectItem value="admin">Administrator</SelectItem>
                            </SelectGroup>
                        </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                        Determines the user&apos;s access level in the system
                    </p>
                </div>

                <div className="space-y-2">
                    <Label>Departments</Label>
                    {loadingDepartments ? (
                        <p className="text-sm text-muted-foreground">Loading departments...</p>
                    ) : departments.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No departments available</p>
                    ) : (
                        <div className="border rounded-md p-4 space-y-3 max-h-48 overflow-y-auto">
                            {departments.map(dept => (
                                <div key={dept.id} className="flex items-center space-x-2">
                                    <Checkbox
                                        id={`dept-${dept.id}`}
                                        checked={form.department_ids.includes(dept.id)}
                                        onCheckedChange={() => handleDepartmentToggle(dept.id)}
                                    />
                                    <Label
                                        htmlFor={`dept-${dept.id}`}
                                        className="text-sm font-normal cursor-pointer"
                                    >
                                        {dept.name}
                                    </Label>
                                </div>
                            ))}
                        </div>
                    )}
                    <p className="text-xs text-muted-foreground">
                        Select one or more departments for this user
                    </p>
                </div>

                <div className="flex justify-end gap-2 pt-4 border-t">
                    <Button
                        type="button"
                        variant="outline"
                        onClick={handleCancel}
                        disabled={loading}
                    >
                        Cancel
                    </Button>
                    <Button type="submit" disabled={loading}>
                        <UserPlus size={16} className="mr-2" />
                        {loading ? 'Registering...' : 'Register User'}
                    </Button>
                </div>
            </form>
        </div>
    )
}
