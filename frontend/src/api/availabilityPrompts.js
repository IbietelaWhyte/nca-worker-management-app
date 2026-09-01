import apiClient from './client'

/** List the availability prompts scheduled for a department. */
export const getAvailabilityPrompts = departmentId =>
    apiClient.get(`/departments/${departmentId}/availability-prompts`)

/**
 * Schedule a prompt.
 *
 * @param {string} departmentId
 * @param {{ mode: 'once' | 'monthly', send_on?: string, repeat_day?: number }} data
 */
export const createAvailabilityPrompt = (departmentId, data) =>
    apiClient.post(`/departments/${departmentId}/availability-prompts`, data)

/** Delete a scheduled prompt. */
export const deleteAvailabilityPrompt = (departmentId, promptId) =>
    apiClient.delete(`/departments/${departmentId}/availability-prompts/${promptId}`)

/** Text the department's workers now. Resolves to { sent, skipped_no_phone, failed }. */
export const sendAvailabilityPromptNow = departmentId =>
    apiClient.post(`/departments/${departmentId}/availability-prompts/send`)
