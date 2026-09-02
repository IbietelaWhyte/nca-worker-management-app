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
        <div className="flex flex-col w-64 min-h-screen bg-sidebar text-sidebar-foreground">
            {/* Logo area — the white wordmark on purple mirrors the church site's header. */}
            <div className="p-6">
                <img
                    src="/nca-logo-white.png"
                    alt="New Covenant Assembly"
                    className="w-40 h-auto"
                    width={752}
                    height={214}
                />
                <p className="text-[0.65rem] font-semibold uppercase tracking-[0.16em] text-sidebar-muted mt-3">
                    Worker Management
                </p>
            </div>

            <Separator className="bg-sidebar-border" />

            {/* Navigation links */}
            <nav className="flex-1 p-4 space-y-1">
                {visibleItems.map(({ to, icon: Icon, label }) => (
                    <NavLink
                        key={to}
                        to={to}
                        end={to === '/'}
                        className={({ isActive }) =>
                            cn(
                                // The 3px left border is transparent when inactive so the label
                                // does not shift sideways as the active item changes.
                                'flex items-center gap-3 pl-[9px] pr-3 py-2 rounded-md text-sm transition-colors border-l-[3px] border-transparent',
                                isActive
                                    ? 'bg-sidebar-active text-sidebar-foreground font-semibold border-l-highlight'
                                    : 'text-sidebar-muted hover:bg-sidebar-active/60 hover:text-sidebar-foreground'
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
