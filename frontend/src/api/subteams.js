import apiClient from './client'

export const getSubteamsByDepartment = departmentId =>
    apiClient.get(`/departments/${departmentId}/subteams`)

export const getSubteam = subteamId => apiClient.get(`/subteams/${subteamId}`)

export const getSubteamWithWorkers = subteamId => apiClient.get(`/subteams/${subteamId}/workers`)

export const createSubteam = data => apiClient.post('/subteams', data)

export const updateSubteam = (subteamId, data) => apiClient.patch(`/subteams/${subteamId}`, data)

/**
 * Replace the minimum count of each department role on this subteam's generated rotas.
 * `requirements` is [{ department_role_id, min_count }]; an empty list clears them.
 */
export const setSubteamRoleRequirements = (subteamId, requirements) =>
    apiClient.put(`/subteams/${subteamId}/role-requirements`, { requirements })

export const deleteSubteam = subteamId => apiClient.delete(`/subteams/${subteamId}`)

export const assignWorkersToSubteam = (subteamId, workerIds) =>
    apiClient.post(`/subteams/${subteamId}/workers`, { worker_ids: workerIds })

export const unassignWorkerFromSubteam = (subteamId, workerId) =>
    apiClient.delete(`/subteams/${subteamId}/workers/${workerId}`)
