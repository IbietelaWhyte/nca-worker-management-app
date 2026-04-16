// src/api/authentication.js
import apiClient from './client'

/**
 * Register a new user with authentication credentials
 * Creates both auth account and worker profile
 * Admin only
 */
export const registerUser = data => apiClient.post('/authentication/register', data)
