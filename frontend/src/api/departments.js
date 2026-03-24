// src/api/department.js
import apiClient from './client'

export const getDepartments = () => 
    apiClient.get('/departments')

export const getDepartment = (id) =>
    apiClient.get(`/departments/${id}`)

export const createDepartment = (data) => 
    apiClient.post('/departments', data)

export const updateDepartment = (id, data) =>
    apiClient.patch(`/departments/${id}`, data)

export const deleteDepartment = (id) =>
    apiClient.delete(`/departments/${id}`)

export const getDepartmentWithWorkers = (id) =>
    apiClient.get(`/departments/${id}/workers`)

export const assignWorkerToDepartment = (departmentId, workerId) =>
    apiClient.post(`/departments/${departmentId}/workers/${workerId}`)

export const unassignWorkerFromDepartment = (departmentId, workerId) =>
    apiClient.delete(`/departments/${departmentId}/workers/${workerId}`)

export const setHod = (departmentId, workerId) =>
    apiClient.patch(`/departments/${departmentId}/hod/${workerId}`)

export const getDepartmentWithSubteams = (departmentId) =>
    apiClient.get(`/departments/${departmentId}/subteams`)