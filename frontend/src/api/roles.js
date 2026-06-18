import apiClient from './client'

export const getRolesByDepartment = departmentId =>
    apiClient.get(`/departments/${departmentId}/roles`)

export const getRole = roleId => apiClient.get(`/roles/${roleId}`)

export const createRole = data => apiClient.post('/roles', data)

export const updateRole = (roleId, data) => apiClient.patch(`/roles/${roleId}`, data)

export const deleteRole = roleId => apiClient.delete(`/roles/${roleId}`)

export const assignWorkerRole = (roleId, workerId) =>
    apiClient.post(`/roles/${roleId}/workers/${workerId}`)

export const unassignWorkerRole = (roleId, workerId) =>
    apiClient.delete(`/roles/${roleId}/workers/${workerId}`)
