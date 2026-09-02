import * as React from 'react'
import { Dialog as SheetPrimitive } from 'radix-ui'
import { XIcon } from 'lucide-react'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

/**
 * A panel that slides in from an edge. Built on the same Radix Dialog as `dialog.jsx` — it is a
 * dialog that happens to be anchored to a side rather than centred, so it inherits the focus trap,
 * the Escape handling and the scroll lock for free.
 *
 * Used for the mobile navigation drawer; the sidebar renders inside it below `md`.
 */

function Sheet({ ...props }) {
    return <SheetPrimitive.Root data-slot="sheet" {...props} />
}

function SheetTrigger({ ...props }) {
    return <SheetPrimitive.Trigger data-slot="sheet-trigger" {...props} />
}

function SheetClose({ ...props }) {
    return <SheetPrimitive.Close data-slot="sheet-close" {...props} />
}

function SheetOverlay({ className, ...props }) {
    return (
        <SheetPrimitive.Overlay
            data-slot="sheet-overlay"
            className={cn(
                'fixed inset-0 isolate z-50 bg-foreground/20 duration-200 data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0',
                className
            )}
            {...props}
        />
    )
}

const SIDE_CLASSES = {
    left: 'inset-y-0 left-0 h-full w-72 max-w-[85%] border-r data-open:slide-in-from-left data-closed:slide-out-to-left',
    right: 'inset-y-0 right-0 h-full w-72 max-w-[85%] border-l data-open:slide-in-from-right data-closed:slide-out-to-right',
}

function SheetContent({ className, children, side = 'left', showCloseButton = true, ...props }) {
    return (
        <SheetPrimitive.Portal data-slot="sheet-portal">
            <SheetOverlay />
            <SheetPrimitive.Content
                data-slot="sheet-content"
                className={cn(
                    'fixed z-50 flex flex-col overflow-y-auto bg-background duration-200 outline-none data-open:animate-in data-closed:animate-out',
                    SIDE_CLASSES[side],
                    className
                )}
                {...props}
            >
                {children}
                {showCloseButton && (
                    <SheetPrimitive.Close data-slot="sheet-close" asChild>
                        <Button
                            variant="ghost"
                            className="absolute top-3 right-3 size-11"
                            size="icon"
                        >
                            <XIcon />
                            <span className="sr-only">Close menu</span>
                        </Button>
                    </SheetPrimitive.Close>
                )}
            </SheetPrimitive.Content>
        </SheetPrimitive.Portal>
    )
}

/**
 * Radix requires a title and description on every dialog for screen readers. The nav drawer has no
 * visible heading, so these are rendered visually hidden.
 */
function SheetTitle({ className, ...props }) {
    return (
        <SheetPrimitive.Title
            data-slot="sheet-title"
            className={cn('text-base leading-none font-medium', className)}
            {...props}
        />
    )
}

function SheetDescription({ className, ...props }) {
    return (
        <SheetPrimitive.Description
            data-slot="sheet-description"
            className={cn('text-sm text-muted-foreground', className)}
            {...props}
        />
    )
}

export { Sheet, SheetTrigger, SheetClose, SheetOverlay, SheetContent, SheetTitle, SheetDescription }
