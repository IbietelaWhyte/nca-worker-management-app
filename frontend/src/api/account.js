// src/api/account.js — self-service account endpoints scoped to the current user.
import apiClient from './client'

export const getMyProfile = () => apiClient.get('/account/me')

export const updateMyProfile = data => apiClient.patch('/account/me', data)

export const changePassword = data => apiClient.post('/account/change-password', data)

export const deleteMyAccount = () => apiClient.delete('/account/me')
