import { Button } from '@/components/ui/button'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'

const clock = seconds => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`

/**
 * "Still there?" — shown in the last minute before an idle sign-out.
 *
 * It cannot be dismissed by clicking outside or pressing Escape: either would read as activity,
 * and a warning closed by accident is a sign-out the person never saw coming. The confirm is the
 * ordinary purple button; nothing here is destructive.
 */
export default function IdleWarningDialog({ open, secondsLeft, onStay, onSignOut }) {
    return (
        <Dialog open={open}>
            <DialogContent
                className="sm:max-w-sm"
                showCloseButton={false}
                onEscapeKeyDown={e => e.preventDefault()}
                onPointerDownOutside={e => e.preventDefault()}
                onInteractOutside={e => e.preventDefault()}
            >
                <DialogHeader>
                    <DialogTitle>Still there?</DialogTitle>
                    <DialogDescription aria-live="polite">
                        You will be signed out in {clock(secondsLeft)} because nothing has happened
                        for a while. This keeps people&apos;s details safe on a shared computer.
                    </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                    <Button variant="outline" className="min-h-11 sm:min-h-9" onClick={onSignOut}>
                        Sign out now
                    </Button>
                    <Button className="min-h-11 sm:min-h-9" onClick={onStay} autoFocus>
                        Stay signed in
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
