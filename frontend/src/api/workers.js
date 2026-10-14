// src/api/workers.js
import apiClient from './client'

// params (all optional): search, department_id, role, status, limit, offset. The body is always a
// plain array; the total across pages is in the X-Total-Count header.
export const getWorkers = params => apiClient.get('/workers', { params })

export const getWorker = id => apiClient.get(`/workers/${id}`)

export const createWorker = data => apiClient.post('/workers', data)

export const updateWorker = (id, data) => apiClient.patch(`/workers/${id}`, data)

export const deactivateWorker = id => apiClient.delete(`/workers/${id}`)

// Permanent, irreversible removal of the profile — distinct from the soft deactivate above.
export const deleteWorkerPermanently = id => apiClient.delete(`/workers/${id}/permanent`)

export const createWorkerAccount = (id, data) => apiClient.post(`/workers/${id}/account`, data)

export const getWorkerDepartments = id => apiClient.get(`/workers/${id}/departments`)

export const getWorkerAssistantHodDepartments = id =>
    apiClient.get(`/workers/${id}/assistant-hod-departments`)
