import apiClient from './client'

export const getWorkerAvailability = workerId => apiClient.get(`/availability/workers/${workerId}`)

export const setAvailability = data => apiClient.post('/availability', data)

export const bulkSetAvailability = (workerId, records) =>
    apiClient.post(`/availability/workers/${workerId}/bulk`, records)

export const updateAvailability = (id, data) => apiClient.patch(`/availability/${id}`, data)

export const deleteAvailability = id => apiClient.delete(`/availability/${id}`)

export const clearWorkerAvailability = workerId =>
    apiClient.delete(`/availability/workers/${workerId}`)

export const getWorkerAvailabilityByDay = (workerId, dayOfWeek) =>
    apiClient.get(`/availability/workers/${workerId}/day/${dayOfWeek}`)

export const getAvailableWorkersOnDay = dayOfWeek => apiClient.get(`/availability/day/${dayOfWeek}`)
