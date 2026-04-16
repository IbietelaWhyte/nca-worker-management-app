import { useState, useEffect, useCallback } from 'react'
import { getWorker, updateWorker } from '@/api/workers'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Alert } from '@/components/ui/alert'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'

const AVAILABLE_ROLES = [
    { value: 'worker', label: 'Worker', description: 'Standard worker access' },
    { value: 'hod', label: 'Head of Department', description: 'Can manage their departments' },
    { value: 'admin', label: 'Administrator', description: 'Full system access' },
]

export default function RoleEditor({ workerId, workerName, onClose, onSuccess }) {
    const [roles, setRoles] = useState([])
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState(null)

    const loadRoles = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            const response = await getWorker(workerId)
            setRoles(response.data.roles || [])
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to load roles')
        } finally {
            setLoading(false)
        }
    }, [workerId])

    useEffect(() => {
        loadRoles()
    }, [loadRoles])

    const handleRoleToggle = roleValue => {
        setRoles(prev => {
            if (prev.includes(roleValue)) {
                // Don't allow removing the last role
                if (prev.length === 1) {
                    setError('Worker must have at least one role')
                    return prev
                }
                return prev.filter(r => r !== roleValue)
            } else {
                setError(null)
                return [...prev, roleValue]
            }
        })
    }

    const handleSave = async () => {
        if (roles.length === 0) {
            setError('Worker must have at least one role')
            return
        }

        setSaving(true)
        setError(null)
        try {
            await updateWorker(workerId, { roles })
            onSuccess?.()
            onClose()
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to update roles')
        } finally {
            setSaving(false)
        }
    }

    if (loading) {
        return (
            <div className="space-y-4">
                <p className="text-sm text-muted-foreground">Loading roles...</p>
            </div>
        )
    }

    return (
        <div className="space-y-4">
            {error && (
                <Alert variant="destructive">
                    <p className="text-sm">{error}</p>
                </Alert>
            )}

            <div>
                <Label className="text-base">Manage roles for {workerName}</Label>
                <p className="text-xs text-muted-foreground mt-1">
                    Select one or more roles. Workers can have multiple roles.
                </p>
            </div>

            <div className="space-y-3">
                {AVAILABLE_ROLES.map(role => (
                    <div
                        key={role.value}
                        className="flex items-start space-x-3 rounded-lg border p-3 hover:bg-accent/50 transition-colors"
                    >
                        <Checkbox
                            id={`role-${role.value}`}
                            checked={roles.includes(role.value)}
                            onCheckedChange={() => handleRoleToggle(role.value)}
                            disabled={saving}
                        />
                        <div className="flex-1 space-y-1">
                            <Label
                                htmlFor={`role-${role.value}`}
                                className="font-medium cursor-pointer"
                            >
                                {role.label}
                                {roles.includes(role.value) && (
                                    <Badge variant="secondary" className="ml-2 text-xs">
                                        Active
                                    </Badge>
                                )}
                            </Label>
                            <p className="text-xs text-muted-foreground">{role.description}</p>
                        </div>
                    </div>
                ))}
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t">
                <Button variant="outline" onClick={onClose} disabled={saving}>
                    Cancel
                </Button>
                <Button onClick={handleSave} disabled={saving}>
                    {saving ? 'Saving...' : 'Save Roles'}
                </Button>
            </div>
        </div>
    )
}
