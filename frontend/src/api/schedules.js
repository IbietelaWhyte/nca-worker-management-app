import apiClient from './client'

export const getSchedulesByDepartment = departmentId =>
    apiClient.get(`/schedules/departments/${departmentId}`)

export const getSchedule = scheduleId => apiClient.get(`/schedules/${scheduleId}`)

export const generateSchedule = data => apiClient.post('/schedules/generate', data)

export const deleteSchedule = scheduleId => apiClient.delete(`/schedules/${scheduleId}`)

export const getWorkerAssignments = workerId =>
    apiClient.get(`/schedules/workers/${workerId}/assignments`)

export const updateAssignmentStatus = (assignmentId, status) =>
    apiClient.patch(`/schedules/assignments/${assignmentId}/status`, status)

export const triggerReminders = () => apiClient.post('/schedules/reminders/trigger')
