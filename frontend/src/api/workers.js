// src/api/workers.js
import apiClient from './client'

export const getWorkers = () => apiClient.get('/workers')

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
