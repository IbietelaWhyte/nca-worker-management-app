/**
 * Public API client for confirmation endpoints.
 * No auth token is attached — these endpoints are intentionally unauthenticated
 * so workers can confirm/decline without a Supabase account.
 */
import axios from 'axios'

const publicClient = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL,
})

/**
 * Fetch every upcoming duty the token's worker holds.
 * One link covers a whole month of dates, so this returns a list.
 *
 * @param {string} token - The UUID token from the URL path parameter.
 * @returns {Promise<{
 *   worker_name: string,
 *   expired: boolean,
 *   assignments: Array<{
 *     assignment_id: string,
 *     schedule_title: string,
 *     department_name: string,
 *     scheduled_date: string,
 *     start_time: string,
 *     end_time: string,
 *     status: string,
 *   }>,
 * }>}
 */
export async function getConfirmationDetails(token) {
    const response = await publicClient.get(`/confirm/${token}`)
    return response.data
}

/**
 * Confirm or decline one of the worker's duties.
 * The link stays usable afterwards, so the worker can answer their other dates.
 *
 * @param {string} token - The UUID token from the URL path parameter.
 * @param {string} assignmentId - Which duty is being answered.
 * @param {'confirmed' | 'declined'} action - The worker's response.
 * @returns {Promise<object>} Updated assignment response.
 */
export async function submitConfirmation(token, assignmentId, action) {
    const response = await publicClient.post(`/confirm/${token}`, null, {
        params: { assignment_id: assignmentId, action },
    })
    return response.data
}
