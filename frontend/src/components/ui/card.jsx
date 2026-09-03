import * as React from 'react'

import { cn } from '@/lib/utils'

/**
 * The surface primitive the app had been hand-rolling as `border rounded-lg p-4` in six places.
 *
 * `CardHeader` and `CardFooter` deliberately have no padding of their own beyond the card's — they
 * take a tinted background and a rule instead, so a card can be a plain block or a banded one
 * without a second wrapper.
 */
function Card({ className, ...props }) {
    return (
        <div
            data-slot="card"
            className={cn(
                'flex flex-col overflow-hidden rounded-lg border bg-card text-card-foreground',
                className
            )}
            {...props}
        />
    )
}

function CardHeader({ className, muted = false, ...props }) {
    return (
        <div
            data-slot="card-header"
            className={cn(
                'flex flex-col gap-1 border-b p-4',
                muted && 'bg-secondary text-secondary-foreground',
                className
            )}
            {...props}
        />
    )
}

function CardTitle({ className, ...props }) {
    return (
        <h3
            data-slot="card-title"
            className={cn('text-base leading-tight font-semibold text-foreground', className)}
            {...props}
        />
    )
}

function CardDescription({ className, ...props }) {
    return (
        <p
            data-slot="card-description"
            className={cn('text-sm text-muted-foreground', className)}
            {...props}
        />
    )
}

function CardContent({ className, ...props }) {
    return <div data-slot="card-content" className={cn('p-4', className)} {...props} />
}

function CardFooter({ className, ...props }) {
    return (
        <div
            data-slot="card-footer"
            className={cn(
                'flex flex-wrap items-center justify-end gap-2 border-t bg-muted/50 p-3',
                className
            )}
            {...props}
        />
    )
}

export { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter }
