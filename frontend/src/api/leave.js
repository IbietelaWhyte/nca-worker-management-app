import apiClient from './client'

/**
 * Stretches a worker is away. Set by a head, not by the worker — leave is what suppresses the
 * availability prompt, so a worker who could set their own would be opting out of being asked.
 *
 * A worker marking individual dates off themselves is `api/availability.js`.
 */

/** Everyone currently away, for badging a roster without fetching each worker's history. */
export const getCurrentLeave = () => apiClient.get('/leave/current')

/** One worker's leave, past and future, soonest first. */
export const getWorkerLeave = workerId => apiClient.get(`/leave/workers/${workerId}`)

/**
 * Duties already on the rota inside a proposed leave period.
 *
 * Advisory: setting leave never edits the rota, so this is what tells the head what they will
 * need to reassign. Called before confirming, not after.
 */
export const getLeaveClashes = (workerId, startDate, endDate) =>
    apiClient.get(`/leave/workers/${workerId}/clashes`, {
        params: { start_date: startDate, end_date: endDate },
    })

/** Record that a worker is away. Both dates inclusive. */
export const createWorkerLeave = (workerId, data) =>
    apiClient.post(`/leave/workers/${workerId}`, data)

/** Remove a leave, putting the worker back in the rota for those dates. */
export const deleteWorkerLeave = leaveId => apiClient.delete(`/leave/${leaveId}`)
