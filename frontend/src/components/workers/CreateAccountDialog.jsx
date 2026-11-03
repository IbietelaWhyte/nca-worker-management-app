import { useState, useEffect } from 'react'
import { createWorkerAccount, getWorkerDepartments } from '@/api/workers'
import { useDepartments } from '@/hooks/useDepartments'
import { Button } from '@/components/ui/button'
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

export default function CreateAccountDialog({ workerId, workerName, onClose, onSuccess }) {
    const { departments, loading: loadingDepartments } = useDepartments()
    const [role, setRole] = useState('worker')
    // Departments the worker will manage as assistant HOD. Pre-filled with the departments they
    // already belong to, since that is the common case (manage the team you're part of).
    const [assistantHodDepartments, setAssistantHodDepartments] = useState([])
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState(null)

    useEffect(() => {
        let cancelled = false
        getWorkerDepartments(workerId)
            .then(response => {
                if (!cancelled) setAssistantHodDepartments(response.data.map(dept => dept.id))
            })
            .catch(() => {
                // Pre-fill is a convenience; ignore failures and start with an empty selection.
            })
        return () => {
            cancelled = true
        }
    }, [workerId])

    const handleDepartmentToggle = departmentId => {
        setAssistantHodDepartments(prev =>
            prev.includes(departmentId)
                ? prev.filter(id => id !== departmentId)
                : [...prev, departmentId]
        )
    }

    const handleSave = async e => {
        e.preventDefault()
        setError(null)
        setSaving(true)
        try {
            const payload = { role }
            if (role === 'assistant_hod') {
                payload.assistant_hod_departments = assistantHodDepartments
            }
            await createWorkerAccount(workerId, payload)
            onSuccess?.()
            onClose()
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to send the invite')
        } finally {
            setSaving(false)
        }
    }

    return (
        <form onSubmit={handleSave} className="space-y-4">
            {error && (
                <Alert variant="destructive">
                    <p className="text-sm">{error}</p>
                </Alert>
            )}

            <div>
                <Label className="text-base">Invite {workerName} to sign in</Label>
                <p className="text-xs text-muted-foreground mt-1">
                    They will get an email at their address on file with a link to choose their own
                    password. The link lasts 24 hours; you can resend it from the worker&apos;s
                    menu.
                </p>
            </div>

            <div className="space-y-2">
                <Label htmlFor="account-role">
                    Role <span className="text-destructive">*</span>
                </Label>
                <Select value={role} onValueChange={setRole} disabled={saving}>
                    <SelectTrigger id="account-role" className="w-full">
                        <SelectValue placeholder="Select a role" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectGroup>
                            <SelectItem value="worker">Worker</SelectItem>
                            <SelectItem value="hod">Head of Department (HOD)</SelectItem>
                            <SelectItem value="assistant_hod">
                                Assistant Head of Department
                            </SelectItem>
                            <SelectItem value="admin">Administrator</SelectItem>
                        </SelectGroup>
                    </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                    Determines the user&apos;s access level in the system
                </p>
            </div>

            {role === 'assistant_hod' && (
                <div className="space-y-2">
                    <Label>Departments to manage</Label>
                    {loadingDepartments ? (
                        <p className="text-sm text-muted-foreground">Loading departments...</p>
                    ) : departments.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No departments available</p>
                    ) : (
                        <div className="border rounded-md p-4 space-y-3 max-h-48 overflow-y-auto">
                            {departments.map(dept => (
                                <div key={dept.id} className="flex items-center space-x-2">
                                    <Checkbox
                                        id={`account-dept-${dept.id}`}
                                        checked={assistantHodDepartments.includes(dept.id)}
                                        onCheckedChange={() => handleDepartmentToggle(dept.id)}
                                        disabled={saving}
                                    />
                                    <Label
                                        htmlFor={`account-dept-${dept.id}`}
                                        className="text-sm font-normal cursor-pointer"
                                    >
                                        {dept.name}
                                    </Label>
                                </div>
                            ))}
                        </div>
                    )}
                    <p className="text-xs text-muted-foreground">
                        Assistant HODs can only manage the departments selected here.
                    </p>
                </div>
            )}

            <div className="flex justify-end gap-2 pt-2 border-t">
                <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
                    Cancel
                </Button>
                <Button type="submit" disabled={saving}>
                    {saving ? 'Sending...' : 'Send invite'}
                </Button>
            </div>
        </form>
    )
}
