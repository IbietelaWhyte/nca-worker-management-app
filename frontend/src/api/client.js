import axios from 'axios'
import { supabase } from '../lib/supabaseClient'

const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL,
})

// Strip sensitive fields before logging request bodies (e.g. registration passwords).
const redact = data => {
    if (!data || typeof data !== 'object') return data
    const SENSITIVE = ['password', 'access_token', 'refresh_token', 'token']
    const clone = { ...data }
    for (const key of SENSITIVE) {
        if (key in clone) clone[key] = '[redacted]'
    }
    return clone
}

apiClient.interceptors.request.use(
    async config => {
        const {
            data: { session },
        } = await supabase.auth.getSession()

        if (session?.access_token) {
            config.headers.Authorization = `Bearer ${session.access_token}`
        }

        // Log API request (dev only — avoids leaking PII/tokens in production builds)
        if (import.meta.env.DEV) {
            console.log('🔵 API Request:', {
                method: config.method?.toUpperCase(),
                url: config.url,
                baseURL: config.baseURL,
                data: redact(config.data),
                params: config.params,
            })
        }

        return config
    },
    error => {
        if (import.meta.env.DEV) {
            console.error('❌ API Request Error:', error)
        }
        return Promise.reject(error)
    }
)

apiClient.interceptors.response.use(
    response => {
        // Log successful API response (dev only)
        if (import.meta.env.DEV) {
            console.log('✅ API Response:', {
                status: response.status,
                method: response.config.method?.toUpperCase(),
                url: response.config.url,
                data: response.data,
            })
        }
        return response
    },
    error => {
        // Log API error response (dev only)
        if (import.meta.env.DEV) {
            console.error('❌ API Error:', {
                status: error.response?.status,
                method: error.config?.method?.toUpperCase(),
                url: error.config?.url,
                message: error.message,
                data: error.response?.data,
            })
        }
        return Promise.reject(error)
    }
)

export default apiClient
