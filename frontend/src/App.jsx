import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import { AuthProvider } from '@/context/AuthContext'
import ProtectedRoute from '@/components/ProtectedRoute'
import AppLayout from '@/components/layout/AppLayout'

// Route components are lazy-loaded so each page ships as its own chunk
// instead of one large bundle.
const LoginPage = lazy(() => import('@/pages/LoginPage'))
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const WorkersPage = lazy(() => import('@/pages/WorkersPage'))
const RegisterUser = lazy(() => import('@/components/workers/RegisterUser'))
const DepartmentsPage = lazy(() => import('@/pages/DepartmentsPage'))
const DepartmentDetailPage = lazy(() => import('@/pages/DepartmentDetailPage'))
const SchedulesPage = lazy(() => import('@/pages/SchedulesPage'))
const AvailabilityPage = lazy(() => import('@/pages/AvailabilityPage'))
const ScheduleDetailPage = lazy(() => import('@/pages/ScheduleDetailPage'))
const AccountPage = lazy(() => import('@/pages/AccountPage'))
const ConfirmPage = lazy(() => import('@/pages/ConfirmPage'))
const ResetPasswordPage = lazy(() => import('@/pages/ResetPasswordPage'))

const PageFallback = () => (
    <div className="min-h-screen flex items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
    </div>
)

const ProtectedLayout = ({ children }) => (
    <ProtectedRoute>
        <AppLayout>{children}</AppLayout>
    </ProtectedRoute>
)

function App() {
    return (
        <AuthProvider>
            <Suspense fallback={<PageFallback />}>
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
                    <Route
                        path="/account"
                        element={
                            <ProtectedLayout>
                                <AccountPage />
                            </ProtectedLayout>
                        }
                    />
                    {/* Public route — no auth required, accessible by workers via SMS link */}
                    <Route path="/confirm/:token" element={<ConfirmPage />} />
                    {/* Public route — password recovery link target */}
                    <Route path="/reset-password" element={<ResetPasswordPage />} />
                </Routes>
            </Suspense>
        </AuthProvider>
    )
}

export default App
