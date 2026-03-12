import { Routes, Route } from 'react-router-dom'
import { AuthProvider } from '@/context/AuthContext'
import ProtectedRoute from '@/components/ProtectedRoute'
import AppLayout from '@/components/layout/AppLayout'
import LoginPage from '@/pages/LoginPage'
import DashboardPage from '@/pages/DashboardPage'
import WorkersPage from '@/pages/WorkersPage'
import DepartmentsPage from '@/pages/DepartmentsPage'
import SchedulesPage from '@/pages/SchedulesPage'

function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* Public route — no layout, no auth required */}
        <Route path="/login" element={<LoginPage />} />

        {/* Protected routes — require auth, render inside AppLayout */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AppLayout>
                <DashboardPage />
              </AppLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/workers"
          element={
            <ProtectedRoute>
              <AppLayout>
                <WorkersPage />
              </AppLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/departments"
          element={
            <ProtectedRoute>
              <AppLayout>
                <DepartmentsPage />
              </AppLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/schedules"
          element={
            <ProtectedRoute>
              <AppLayout>
                <SchedulesPage />
              </AppLayout>
            </ProtectedRoute>
          }
        />
      </Routes>
    </AuthProvider>
  )
}

export default App