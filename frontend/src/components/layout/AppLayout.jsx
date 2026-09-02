import { useState } from 'react'
import Sidebar, { SidebarNav } from './Sidebar'
import TopBar from './TopBar'
import { Sheet, SheetContent, SheetTitle, SheetDescription } from '@/components/ui/sheet'

export default function AppLayout({ children }) {
    const [navOpen, setNavOpen] = useState(false)

    return (
        <div className="flex min-h-screen bg-background">
            {/* Sidebar — a fixed rail from md up */}
            <Sidebar />

            {/* Below md the same nav slides in over the page instead. At 375px the rail alone
                would take 256px of a 375px screen, leaving nothing for the page. */}
            <Sheet open={navOpen} onOpenChange={setNavOpen}>
                <SheetContent side="left" className="bg-sidebar text-sidebar-foreground md:hidden">
                    <SheetTitle className="sr-only">Navigation</SheetTitle>
                    <SheetDescription className="sr-only">
                        Links to the sections of the worker management app.
                    </SheetDescription>
                    <SidebarNav onNavigate={() => setNavOpen(false)} />
                </SheetContent>
            </Sheet>

            {/* Main area — topbar + page content. min-w-0 so a wide child scrolls inside the
                page rather than stretching the flex row. */}
            <div className="flex flex-col flex-1 min-w-0">
                <TopBar onOpenNav={() => setNavOpen(true)} />
                <main className="flex-1 p-4 md:p-6 overflow-auto">{children}</main>
            </div>
        </div>
    )
}
