import { useState, useEffect, useCallback } from 'react'
import {
    getDepartments,
    createDepartment,
    updateDepartment,
    deleteDepartment,
} from '@/api/departments'

export function useDepartments() {
    const [departments, setDepartments] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const fetchDepartments = useCallback(async () => {
        try {
            setLoading(true)
            setError(null)
            const response = await getDepartments()
            setDepartments(response.data)
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to load departments')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        fetchDepartments()
    }, [fetchDepartments])

    const addDepartment = async data => {
        const response = await createDepartment(data)
        setDepartments(prev => [...prev, response.data])
        return response.data
    }

    const editDepartment = async (id, data) => {
        const response = await updateDepartment(id, data)
        setDepartments(prev => prev.map(d => (d.id === id ? response.data : d)))
        return response.data
    }

    const removeDepartment = async id => {
        await deleteDepartment(id)
        setDepartments(prev => prev.filter(d => d.id !== id))
    }

    return {
        departments,
        loading,
        error,
        refetch: fetchDepartments,
        addDepartment,
        editDepartment,
        removeDepartment,
    }
}
