// src/api/feedback.js — in-app bug reports and ideas, filed as issues by the backend.
import apiClient from './client'

export const getFeedbackConfig = () => apiClient.get('/feedback/config')

export const submitFeedback = data => apiClient.post('/feedback', data)

/**
 * The context a reporter could never supply accurately: which browser, how big the window, which
 * build. Collected at submit time rather than on mount so a resized window reports its real size.
 *
 * @returns {{user_agent: string, viewport: string, app_version: string}}
 */
export function browserContext() {
    return {
        // Capped to the backend's limit — a rejected report over a long UA string would be a
        // baffling failure for the person who just typed out their problem.
        user_agent: navigator.userAgent.slice(0, 300),
        viewport: `${window.innerWidth}x${window.innerHeight}`,
        app_version: import.meta.env.VITE_APP_VERSION ?? 'unknown',
    }
}
