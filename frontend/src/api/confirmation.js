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
 * Fetch the assignment details for a confirmation token.
 * Called on page load before the worker takes any action.
 *
 * @param {string} token - The UUID token from the URL path parameter.
 * @returns {Promise<{
 *   worker_name: string,
 *   schedule_title: string,
 *   scheduled_date: string,
 *   start_time: string,
 *   end_time: string,
 *   current_status: string,
 *   already_used: boolean,
 *   expired: boolean,
 * }>}
 */
export async function getConfirmationDetails(token) {
    const response = await publicClient.get(`/api/v1/confirm/${token}`)
    return response.data
}

/**
 * Submit a confirmation or declination for an assignment.
 *
 * @param {string} token - The UUID token from the URL path parameter.
 * @param {'confirmed' | 'declined'} action - The worker's response.
 * @returns {Promise<object>} Updated assignment response.
 */
export async function submitConfirmation(token, action) {
    const response = await publicClient.post(`/api/v1/confirm/${token}`, null, {
        params: { action },
    })
    return response.data
}
