import { Routes, Route } from 'react-router-dom'
import { AuthProvider } from '@/context/AuthContext'
import ProtectedRoute from '@/components/ProtectedRoute'
import AppLayout from '@/components/layout/AppLayout'
import LoginPage from '@/pages/LoginPage'
import DashboardPage from '@/pages/DashboardPage'
import WorkersPage from '@/pages/WorkersPage'
import RegisterUser from '@/components/workers/RegisterUser'
import DepartmentsPage from '@/pages/DepartmentsPage'
import DepartmentDetailPage from '@/pages/DepartmentDetailPage'
import SchedulesPage from '@/pages/SchedulesPage'
import AvailabilityPage from '@/pages/AvailabilityPage'
import ScheduleDetailPage from '@/pages/ScheduleDetailPage'
import ConfirmPage from '@/pages/ConfirmPage'

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
                <Route
                    path="/"
                    element={
                        <ProtectedLayout>
                            <DashboardPage />
                        </ProtectedLayout>
                    }
                />
                <Route
                    path="/workers"
                    element={
                        <ProtectedLayout>
                            <WorkersPage />
                        </ProtectedLayout>
                    }
                />
                <Route
                    path="/workers/register"
                    element={
                        <ProtectedLayout>
                            <RegisterUser />
                        </ProtectedLayout>
                    }
                />
                <Route
                    path="/departments"
                    element={
                        <ProtectedLayout>
                            <DepartmentsPage />
                        </ProtectedLayout>
                    }
                />
                <Route
                    path="/departments/:id"
                    element={
                        <ProtectedLayout>
                            <DepartmentDetailPage />
                        </ProtectedLayout>
                    }
                />
                <Route
                    path="/availability"
                    element={
                        <ProtectedLayout>
                            <AvailabilityPage />
                        </ProtectedLayout>
                    }
                />
                <Route
                    path="/schedules"
                    element={
                        <ProtectedLayout>
                            <SchedulesPage />
                        </ProtectedLayout>
                    }
                />
                <Route
                    path="/schedules/:id"
                    element={
                        <ProtectedLayout>
                            <ScheduleDetailPage />
                        </ProtectedLayout>
                    }
                />
                {/* Public route — no auth required, accessible by workers via SMS link */}
                <Route path="/confirm/:token" element={<ConfirmPage />} />
            </Routes>
        </AuthProvider>
    )
}

export default App
