/**
 * Public API client for the token-authenticated availability page.
 * No auth token is attached — most workers have no Supabase account, so an SMS asking them to
 * set their availability has to reach them without one. The link itself is the credential.
 */
import axios from 'axios'

const publicClient = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL,
})

/**
 * Fetch the worker's name and the dates they have already set.
 *
 * @param {string} token - The UUID token from the URL path parameter.
 * @returns {Promise<{
 *   worker_name: string,
 *   dates: Array<{ id: string, specific_date: string, is_available: boolean }>,
 * }>}
 */
export async function getAvailabilityByLink(token) {
    const response = await publicClient.get(`/availability/link/${token}`)
    return response.data
}

/**
 * Mark one date available or unavailable.
 *
 * @param {string} token - The UUID token from the URL path parameter.
 * @param {string} specificDate - The date, as yyyy-MM-dd.
 * @param {boolean} isAvailable - Whether the worker can serve that day.
 * @returns {Promise<object>} The stored availability record.
 */
export async function setAvailabilityByLink(token, specificDate, isAvailable) {
    const response = await publicClient.put(`/availability/link/${token}`, {
        specific_date: specificDate,
        is_available: isAvailable,
    })
    return response.data
}

/**
 * Remove the worker's override for one date, falling back to their recurring pattern.
 *
 * @param {string} token - The UUID token from the URL path parameter.
 * @param {string} specificDate - The date, as yyyy-MM-dd.
 * @returns {Promise<void>}
 */
export async function clearAvailabilityByLink(token, specificDate) {
    await publicClient.delete(`/availability/link/${token}`, {
        params: { specific_date: specificDate },
    })
}
