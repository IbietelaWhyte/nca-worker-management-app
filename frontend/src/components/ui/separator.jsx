import * as React from 'react'
import { Separator as SeparatorPrimitive } from 'radix-ui'

import { cn } from '@/lib/utils'

function Separator({ className, orientation = 'horizontal', decorative = true, ...props }) {
    return (
        <SeparatorPrimitive.Root
            data-slot="separator"
            decorative={decorative}
            orientation={orientation}
            className={cn(
                // v3 variant syntax on purpose: Tailwind is pinned at 3.4.19, and the v4 form
                // (data-horizontal:) this component shipped with compiles to nothing, leaving
                // every separator in the app at zero height.
                'shrink-0 bg-border data-[orientation=horizontal]:h-px data-[orientation=horizontal]:w-full data-[orientation=vertical]:w-px data-[orientation=vertical]:self-stretch',
                className
            )}
            {...props}
        />
    )
}

export { Separator }
