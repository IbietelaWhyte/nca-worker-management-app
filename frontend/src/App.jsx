import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate, useParams } from 'react-router-dom'
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
const HelpPage = lazy(() => import('@/pages/HelpPage'))
const AvailabilityLinkPage = lazy(() => import('@/pages/AvailabilityLinkPage'))
const ResetPasswordPage = lazy(() => import('@/pages/ResetPasswordPage'))

/**
 * Old /confirm/{token} links, sent by SMS before confirming was removed, land here.
 *
 * The token is the same per-worker row the availability page uses, so the link still identifies
 * its owner — it just has nothing to confirm any more. Redirecting turns a dead link sitting in
 * somebody's messages into a working one, which is cheaper than the 404 they would otherwise hit
 * and better than a page explaining a feature that no longer exists.
 */
const ConfirmLinkRedirect = () => {
    const { token } = useParams()
    return <Navigate to={`/availability/${token}`} replace />
}

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
                    <Route
                        path="/help"
                        element={
                            <ProtectedLayout>
                                <HelpPage />
                            </ProtectedLayout>
                        }
                    />
                    {/* Retired: confirming a duty. Kept so texts already sent still work. */}
                    <Route path="/confirm/:token" element={<ConfirmLinkRedirect />} />

                    {/* Public route — reached from an SMS prompt, no session required */}
                    <Route path="/availability/:token" element={<AvailabilityLinkPage />} />
                    {/* Public route — password recovery link target */}
                    <Route path="/reset-password" element={<ResetPasswordPage />} />
                </Routes>
            </Suspense>
        </AuthProvider>
    )
}

export default App
