import { useState, useEffect, useCallback } from 'react'
import { getRolesByDepartment, createRole, updateRole, deleteRole } from '@/api/roles'

export function useRoles(departmentId) {
    const [roles, setRoles] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const fetchRoles = useCallback(async () => {
        if (!departmentId) {
            setLoading(false)
            return
        }
        try {
            setLoading(true)
            setError(null)
            const response = await getRolesByDepartment(departmentId)
            setRoles(response.data)
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to load roles')
        } finally {
            setLoading(false)
        }
    }, [departmentId])

    useEffect(() => {
        fetchRoles()
    }, [fetchRoles])

    const addRole = async data => {
        const response = await createRole({ ...data, department_id: departmentId })
        setRoles(prev => [...prev, response.data])
        return response.data
    }

    const editRole = async (roleId, data) => {
        const response = await updateRole(roleId, data)
        setRoles(prev => prev.map(r => (r.id === roleId ? response.data : r)))
        return response.data
    }

    const removeRole = async roleId => {
        await deleteRole(roleId)
        setRoles(prev => prev.filter(r => r.id !== roleId))
    }

    return {
        roles,
        loading,
        error,
        refetch: fetchRoles,
        addRole,
        editRole,
        removeRole,
    }
}
