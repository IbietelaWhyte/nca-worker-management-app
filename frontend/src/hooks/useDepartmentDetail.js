import { useState, useEffect, useCallback } from 'react'
import {
  getDepartmentWithWorkers,
  assignWorkerToDepartment,
  unassignWorkerFromDepartment,
  setHod,
  getDepartmentWithSubteams,
} from '@/api/departments'

export function useDepartmentDetail(departmentId) {
  const [department, setDepartment] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchDepartment = useCallback(async () => {
    if (!departmentId) return
    try {
      setLoading(true)
      setError(null)
      const response = await getDepartmentWithWorkers(departmentId)
      setDepartment(response.data)
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Failed to load department')
    } finally {
      setLoading(false)
    }
  }, [departmentId])

  useEffect(() => {
    fetchDepartment()
  }, [fetchDepartment])

  const addMember = async (workerId) => {
    await assignWorkerToDepartment(departmentId, workerId)
    await fetchDepartment()
  }

  const removeMember = async (workerId) => {
    await unassignWorkerFromDepartment(departmentId, workerId)
    setDepartment(prev => ({
      ...prev,
      workers: prev.workers.filter(w => w.id !== workerId),
    }))
  }

  const assignHod = async (workerId) => {
    const response = await setHod(departmentId, workerId)
    setDepartment(response.data)
  }

  const getSubteams = async () => {
    const response = await getDepartmentWithSubteams(departmentId)
    return response.data
  }

  return {
    department,
    loading,
    error,
    refetch: fetchDepartment,
    addMember,
    removeMember,
    assignHod,
    getSubteams,
  }
}