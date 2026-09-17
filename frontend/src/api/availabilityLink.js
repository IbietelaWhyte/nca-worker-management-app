/**
 * Public API client for the token-authenticated availability page.
 * No auth token is attached — most workers have no Supabase account, so an SMS asking them to
 * set their availability has to reach them without one. The link itself is the credential.
 *
 * The page asks one question: which dates can you NOT serve. There is no "mark available" call
 * because an unmarked date already counts as available wherever the rota is built.
 */
import axios from 'axios'

const publicClient = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL,
})

/**
 * Fetch the worker's name, the dates they have marked themselves off for, and the cut-off.
 *
 * @param {string} token - The UUID token from the URL path parameter.
 * @returns {Promise<{
 *   worker_name: string,
 *   dates: Array<{ id: string, specific_date: string }>,
 *   editable_from: string,
 * }>}
 */
export async function getAvailabilityByLink(token) {
    const response = await publicClient.get(`/availability/link/${token}`)
    return response.data
}

/**
 * Mark one date as one the worker cannot serve.
 *
 * @param {string} token - The UUID token from the URL path parameter.
 * @param {string} specificDate - The date, as yyyy-MM-dd.
 * @returns {Promise<object>} The stored availability record.
 */
export async function markUnavailableByLink(token, specificDate) {
    const response = await publicClient.put(`/availability/link/${token}`, {
        specific_date: specificDate,
    })
    return response.data
}

/**
 * Take the mark back off one date, putting the worker back to available for it.
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
