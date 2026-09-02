import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { LogOut, Menu, Settings } from 'lucide-react'
import { Button } from '@/components/ui/button'

function getInitials(email) {
    if (!email) return '?'
    return email.charAt(0).toUpperCase()
}

export default function TopBar({ onOpenNav }) {
    const { user, signOut } = useAuth()
    const navigate = useNavigate()

    return (
        <div className="h-16 border-b flex items-center px-4 md:px-6 bg-background">
            {/* Below md the sidebar is a drawer, and this is what opens it. */}
            <Button
                variant="ghost"
                size="icon"
                className="md:hidden -ml-2"
                onClick={onOpenNav}
                aria-label="Open navigation"
            >
                <Menu size={20} />
            </Button>

            {/* Right side — user menu. ml-auto rather than justify-between on the row, because
                the menu button above is the only other child and it disappears from md up. */}
            <DropdownMenu>
                <DropdownMenuTrigger asChild>
                    <button className="ml-auto flex size-11 items-center justify-center rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                        <Avatar className="h-8 w-8 cursor-pointer">
                            <AvatarFallback className="text-xs bg-primary text-primary-foreground">
                                {getInitials(user?.email)}
                            </AvatarFallback>
                        </Avatar>
                    </button>
                </DropdownMenuTrigger>

                <DropdownMenuContent align="end" className="w-48">
                    <DropdownMenuLabel className="text-xs text-muted-foreground font-normal truncate">
                        {user?.email}
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                        onClick={() => navigate('/account')}
                        className="cursor-pointer"
                    >
                        <Settings size={14} className="mr-2" />
                        Account settings
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                        onClick={signOut}
                        className="text-destructive focus:text-destructive cursor-pointer"
                    >
                        <LogOut size={14} className="mr-2" />
                        Sign out
                    </DropdownMenuItem>
                </DropdownMenuContent>
            </DropdownMenu>
        </div>
    )
}
