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

export const setAssignmentRole = (assignmentId, departmentRoleId) =>
    apiClient.patch(`/schedules/assignments/${assignmentId}/role`, null, {
        // Omit the param to clear the role (backend treats absent as None).
        params: departmentRoleId ? { department_role_id: departmentRoleId } : {},
    })

// Who may still be added to a rota, each with the subteam they would land in. Resolved
// server-side rather than filtered here: a department-only rota excludes everybody who is in
// a subteam, and working that out in JS would be a second copy of the scope rules.
export const getAssignableWorkers = scheduleId =>
    apiClient.get(`/schedules/${scheduleId}/assignable-workers`)

// Editing a generated rota. All three return { schedule, warnings }: the whole re-read
// schedule, so the caller replaces its copy wholesale and the embeds come for free, plus
// anything that did not stop the edit but the head should know about.
export const addAssignment = (scheduleId, workerId) =>
    apiClient.post(`/schedules/${scheduleId}/assignments`, { worker_id: workerId })

export const replaceAssignmentWorker = (assignmentId, workerId) =>
    apiClient.patch(`/schedules/assignments/${assignmentId}/worker`, { worker_id: workerId })

export const removeAssignment = assignmentId =>
    apiClient.delete(`/schedules/assignments/${assignmentId}`)

export const triggerReminders = () => apiClient.post('/schedules/reminders/trigger')

export const triggerRemindersForSchedule = scheduleId =>
    apiClient.post(`/schedules/${scheduleId}/reminders/trigger`)
