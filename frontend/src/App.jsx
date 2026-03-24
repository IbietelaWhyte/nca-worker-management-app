import { Routes, Route } from 'react-router-dom'
import { AuthProvider } from '@/context/AuthContext'
import ProtectedRoute from '@/components/ProtectedRoute'
import AppLayout from '@/components/layout/AppLayout'
import LoginPage from '@/pages/LoginPage'
import DashboardPage from '@/pages/DashboardPage'
import WorkersPage from '@/pages/WorkersPage'
import DepartmentsPage from '@/pages/DepartmentsPage'
import DepartmentDetailPage from '@/pages/DepartmentDetailPage'
import SchedulesPage from '@/pages/SchedulesPage'

const ProtectedLayout = ({ children }) => (
  <ProtectedRoute>
    <AppLayout>{children}</AppLayout>
  </ProtectedRoute>
)

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<ProtectedLayout><DashboardPage /></ProtectedLayout>} />
        <Route path="/workers" element={<ProtectedLayout><WorkersPage /></ProtectedLayout>} />
        <Route path="/departments" element={<ProtectedLayout><DepartmentsPage /></ProtectedLayout>} />
        <Route path="/departments/:id" element={<ProtectedLayout><DepartmentDetailPage /></ProtectedLayout>} />
        <Route path="/schedules" element={<ProtectedLayout><SchedulesPage /></ProtectedLayout>} />
      </Routes>
    </AuthProvider>
  )
}

export default App