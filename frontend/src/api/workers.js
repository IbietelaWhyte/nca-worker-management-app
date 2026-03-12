// src/api/workers.js
import apiClient from './client'

export const getWorkers = () => 
    apiClient.get('/workers')

export const getWorker = (id) =>
    apiClient.get(`/workers/${id}`)

export const createWorker = (data) => 
    apiClient.post('/workers', data)

export const updateWorker = (id, data) =>
    apiClient.put(`/workers/${id}`, data)

export const deactivateWorker = (id) =>
    apiClient.delete(`/workers/${id}`)

export const getWorkerDepartments = (id) =>
    apiClient.get(`/workers/${id}/departments`)