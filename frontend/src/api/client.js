import axios from 'axios'
import { supabase } from '../lib/supabaseClient'

const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL,
})

apiClient.interceptors.request.use(
    async config => {
        const {
            data: { session },
        } = await supabase.auth.getSession()

        if (session?.access_token) {
            config.headers.Authorization = `Bearer ${session.access_token}`
        }

        // Log API request
        console.log('🔵 API Request:', {
            method: config.method?.toUpperCase(),
            url: config.url,
            baseURL: config.baseURL,
            data: config.data,
            params: config.params,
        })

        return config
    },
    error => {
        console.error('❌ API Request Error:', error)
        return Promise.reject(error)
    }
)

apiClient.interceptors.response.use(
    response => {
        // Log successful API response
        console.log('✅ API Response:', {
            status: response.status,
            method: response.config.method?.toUpperCase(),
            url: response.config.url,
            data: response.data,
        })
        return response
    },
    error => {
        // Log API error response
        console.error('❌ API Error:', {
            status: error.response?.status,
            method: error.config?.method?.toUpperCase(),
            url: error.config?.url,
            message: error.message,
            data: error.response?.data,
        })
        return Promise.reject(error)
    }
)

export default apiClient
