import apiClient from './client'

/**
 * Who turned up. Recorded by whoever ran the service, never by the worker it is about — there is
 * no self-service path here by design, and the backend refuses one from a worker's token whatever
 * this module does.
 *
 * Every write returns `{ schedule, counts, warnings }`: the whole re-read rota, so the caller
 * replaces its copy wholesale and the embeds come for free, plus the tally the attendance screen
 * renders and anything the operator should know about what just happened.
 */

export const checkIn = assignmentId =>
    apiClient.post(`/attendance/assignments/${assignmentId}/check-in`)

export const undoCheckIn = assignmentId =>
    apiClient.delete(`/attendance/assignments/${assignmentId}/check-in`)

export const setExcused = (assignmentId, excused) =>
    apiClient.patch(`/attendance/assignments/${assignmentId}/excused`, { excused })

// Closing stamps everyone untapped absent, so it is the one call here that writes about people
// nobody touched. The dialog in front of it names them.
export const closeAttendance = scheduleId =>
    apiClient.post(`/attendance/schedules/${scheduleId}/close`)

export const reopenAttendance = scheduleId =>
    apiClient.post(`/attendance/schedules/${scheduleId}/reopen`)

// `range` is a { from, to } pair of yyyy-MM-dd strings, matching getSchedulesByDepartment.
export const getAbsenceReport = (departmentId, range) =>
    apiClient.get(`/attendance/departments/${departmentId}/report`, {
        params: { from: range.from, to: range.to },
    })
