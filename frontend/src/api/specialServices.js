import apiClient from './client'

// Church-wide configuration: recurring rules ("the first Sunday of every month") and named
// one-off dates. Readable by anyone signed in — the month preview badges these — but only
// admins may write them, because the rules are not scoped to a department.
export const getSpecialServices = (activeOnly = false) =>
    apiClient.get('/special-services', { params: activeOnly ? { active_only: true } : {} })

// Resolves the rules into real dates in a window. `from`/`to` are yyyy-MM-dd strings.
export const getSpecialDates = (from, to) =>
    apiClient.get('/special-services/dates', { params: { from, to } })

export const createSpecialService = data => apiClient.post('/special-services', data)

export const updateSpecialService = (id, data) => apiClient.patch(`/special-services/${id}`, data)

export const deleteSpecialService = id => apiClient.delete(`/special-services/${id}`)
