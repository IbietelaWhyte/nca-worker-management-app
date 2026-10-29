import { useState, useEffect, useCallback } from 'react'
import {
    getSubteamsByDepartment,
    createSubteam,
    updateSubteam,
    deleteSubteam,
    setSubteamRoleRequirements,
} from '@/api/subteams'

export function useSubteams(departmentId) {
    const [subteams, setSubteams] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const fetchSubteams = useCallback(async () => {
        if (!departmentId) {
            setLoading(false)
            return
        }
        try {
            setLoading(true)
            setError(null)
            const response = await getSubteamsByDepartment(departmentId)
            setSubteams(response.data)
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to load subteams')
        } finally {
            setLoading(false)
        }
    }, [departmentId])

    useEffect(() => {
        fetchSubteams()
    }, [fetchSubteams])

    const addSubteam = async data => {
        const response = await createSubteam({ ...data, department_id: departmentId })
        setSubteams(prev => [...prev, response.data])
        return response.data
    }

    const editSubteam = async (subteamId, data) => {
        const response = await updateSubteam(subteamId, data)
        // A write does not return its embeds, so the PATCH response has no role_requirements:
        // keep the ones already loaded rather than blanking them.
        setSubteams(prev =>
            prev.map(s =>
                s.id === subteamId
                    ? { ...response.data, role_requirements: s.role_requirements }
                    : s
            )
        )
        return response.data
    }

    const setRoleRequirements = async (subteamId, requirements) => {
        const response = await setSubteamRoleRequirements(subteamId, requirements)
        setSubteams(prev =>
            prev.map(s => (s.id === subteamId ? { ...s, role_requirements: response.data } : s))
        )
        return response.data
    }

    const removeSubteam = async subteamId => {
        await deleteSubteam(subteamId)
        setSubteams(prev => prev.filter(s => s.id !== subteamId))
    }

    return {
        subteams,
        loading,
        error,
        refetch: fetchSubteams,
        addSubteam,
        editSubteam,
        setRoleRequirements,
        removeSubteam,
    }
}
