import { format } from 'date-fns'
import apiClient from './client'

/**
 * The month a date falls in, as the API spells it: "2026-11-01".
 *
 * A string rather than a Date so it can sit in a hook's dependency list — a Date is a new
 * object every render even when it names the same month.
 */
export const monthKey = date => format(date, 'yyyy-MM-01')

export const getMonthlyLeads = (departmentId, month) =>
    apiClient.get(`/departments/${departmentId}/monthly-leads`, { params: { month } })

// The complete set for the month; an empty list clears it.
export const setMonthlyLeads = (departmentId, month, workerIds) =>
    apiClient.put(`/departments/${departmentId}/monthly-leads`, { month, worker_ids: workerIds })
