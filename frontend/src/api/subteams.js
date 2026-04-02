import apiClient from './client'

export const getSubteamsByDepartment = departmentId =>
    apiClient.get(`/departments/${departmentId}/subteams`)

export const getSubteam = subteamId => apiClient.get(`/subteams/${subteamId}`)

export const getSubteamWithWorkers = subteamId => apiClient.get(`/subteams/${subteamId}/workers`)

export const createSubteam = data => apiClient.post('/subteams', data)

export const updateSubteam = (subteamId, data) => apiClient.patch(`/subteams/${subteamId}`, data)

export const deleteSubteam = subteamId => apiClient.delete(`/subteams/${subteamId}`)

export const assignWorkerToSubteam = (subteamId, workerId) =>
    apiClient.post(`/subteams/${subteamId}/workers/${workerId}`)

export const unassignWorkerFromSubteam = (subteamId, workerId) =>
    apiClient.delete(`/subteams/${subteamId}/workers/${workerId}`)
