import apiClient from './client'

// `range` is an optional { from, to } pair of yyyy-MM-dd strings; omitting it returns
// every schedule the department has.
export const getSchedulesByDepartment = (departmentId, range) =>
    apiClient.get(`/schedules/departments/${departmentId}`, {
        params: range?.from && range?.to ? { from: range.from, to: range.to } : {},
    })

export const getSchedule = scheduleId => apiClient.get(`/schedules/${scheduleId}`)

export const generateSchedule = data => apiClient.post('/schedules/generate', data)

// Plans a whole month without saving anything — the HOD reviews the result first.
export const previewMonthlySchedule = data =>
    apiClient.post('/schedules/generate-month/preview', data)

// Saves the month the HOD approved, using the exact per-date worker selection.
export const generateMonthlySchedule = data => apiClient.post('/schedules/generate-month', data)

export const deleteSchedule = scheduleId => apiClient.delete(`/schedules/${scheduleId}`)

export const getWorkerAssignments = workerId =>
    apiClient.get(`/schedules/workers/${workerId}/assignments`)

export const updateAssignmentStatus = (assignmentId, status_update) =>
    apiClient.patch(`/schedules/assignments/${assignmentId}/status`, null, {
        params: { status_update },
    })

export const setAssignmentRole = (assignmentId, departmentRoleId) =>
    apiClient.patch(`/schedules/assignments/${assignmentId}/role`, null, {
        // Omit the param to clear the role (backend treats absent as None).
        params: departmentRoleId ? { department_role_id: departmentRoleId } : {},
    })

export const triggerReminders = () => apiClient.post('/schedules/reminders/trigger')

export const triggerRemindersForSchedule = scheduleId =>
    apiClient.post(`/schedules/${scheduleId}/reminders/trigger`)
