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
import { LogOut } from 'lucide-react'

function getInitials(email) {
    if (!email) return '?'
    return email.charAt(0).toUpperCase()
}

export default function TopBar() {
    const { user, signOut } = useAuth()

    return (
        <div className="h-16 border-b flex items-center justify-between px-6 bg-background">
            {/* Left side — page context could go here later */}
            <div />

            {/* Right side — user menu */}
            <DropdownMenu>
                <DropdownMenuTrigger asChild>
                    <button className="flex items-center gap-2 rounded-full focus:outline-none focus:ring-2 focus:ring-ring">
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
