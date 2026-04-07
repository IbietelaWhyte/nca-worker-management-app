import apiClient from './client'

export const getSchedulesByDepartment = departmentId =>
    apiClient.get(`/schedules/departments/${departmentId}`)

export const getSchedule = scheduleId => apiClient.get(`/schedules/${scheduleId}`)

export const generateSchedule = data => apiClient.post('/schedules/generate', data)

export const deleteSchedule = scheduleId => apiClient.delete(`/schedules/${scheduleId}`)

export const getWorkerAssignments = workerId =>
    apiClient.get(`/schedules/workers/${workerId}/assignments`)

export const updateAssignmentStatus = (assignmentId, status_update) =>
    apiClient.patch(`/schedules/assignments/${assignmentId}/status`, null, {
        params: { status_update },
    })

export const triggerReminders = () => apiClient.post('/schedules/reminders/trigger')

export const triggerRemindersForSchedule = scheduleId =>
    apiClient.post(`/schedules/${scheduleId}/reminders/trigger`)
