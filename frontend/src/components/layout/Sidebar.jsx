import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Users, Building2, Calendar, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Separator } from '@/components/ui/separator'
import { useAuth } from '@/context/AuthContext'

// manageOnly items are only shown to admins and department heads; the pages
// themselves are management-oriented and backend reads are scoped accordingly.
const navItems = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/workers', icon: Users, label: 'Workers', manageOnly: true },
    { to: '/departments', icon: Building2, label: 'Departments', manageOnly: true },
    { to: '/availability', icon: Clock, label: 'Availability' },
    { to: '/schedules', icon: Calendar, label: 'Schedules', manageOnly: true },
]

export default function Sidebar() {
    const { isAdmin, isDepartmentHead } = useAuth()
    const canManage = isAdmin || isDepartmentHead
    const visibleItems = navItems.filter(item => !item.manageOnly || canManage)

    return (
        <div className="flex flex-col w-64 min-h-screen border-r bg-background">
            {/* App name / logo area */}
            <div className="p-6">
                <h1 className="text-lg font-bold tracking-tight">NCA Workers</h1>
                <p className="text-xs text-muted-foreground mt-1">Management Portal</p>
            </div>

            <Separator />

            {/* Navigation links */}
            <nav className="flex-1 p-4 space-y-1">
                {visibleItems.map(({ to, icon: Icon, label }) => (
                    <NavLink
                        key={to}
                        to={to}
                        end={to === '/'}
                        className={({ isActive }) =>
                            cn(
                                'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
                                isActive
                                    ? 'bg-primary text-primary-foreground font-medium'
                                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                            )
                        }
                    >
                        <Icon size={18} />
                        {label}
                    </NavLink>
                ))}
            </nav>
        </div>
    )
}
