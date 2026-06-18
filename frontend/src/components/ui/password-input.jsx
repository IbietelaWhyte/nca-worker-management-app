import * as React from 'react'
import { Eye, EyeOff } from 'lucide-react'

import { cn } from '@/lib/utils'
import { Input } from '@/components/ui/input'

// A password Input with a show/hide eye toggle. Forwards all props to the underlying Input.
function PasswordInput({ className, ...props }) {
    const [visible, setVisible] = React.useState(false)

    return (
        <div className="relative">
            <Input
                type={visible ? 'text' : 'password'}
                className={cn('pr-9', className)}
                {...props}
            />
            <button
                type="button"
                tabIndex={-1}
                onClick={() => setVisible(v => !v)}
                aria-label={visible ? 'Hide password' : 'Show password'}
                className="absolute inset-y-0 right-0 flex items-center px-2.5 text-muted-foreground hover:text-foreground focus:outline-none"
            >
                {visible ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
        </div>
    )
}

export { PasswordInput }
