import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'

const name = assignment =>
    assignment?.workers
        ? `${assignment.workers.first_name} ${assignment.workers.last_name}`
        : 'Unknown worker'

/**
 * Confirming the one action here that writes about people nobody touched.
 *
 * It names them rather than counting them. "4 will be marked absent" is abstract; seeing "Grace
 * Okonkwo" is what makes somebody say "wait, she IS here" — and this record is what their head
 * reads later, so the moment to catch it is now.
 *
 * The confirm is the ordinary purple button, not destructive: finishing attendance is a routine
 * completion, and in this app red means delete. (`ui/button.jsx`'s destructive variant is an
 * underlined text link anyway, not a filled red button.)
 */
export default function FinishAttendanceDialog({
    open,
    untapped,
    busy,
    error,
    onCancel,
    onConfirm,
}) {
    const count = untapped.length

    return (
        <Dialog open={open} onOpenChange={next => !busy && !next && onCancel()}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>
                        {count === 0
                            ? 'Finish attendance?'
                            : `Mark ${count} ${count === 1 ? 'person' : 'people'} absent?`}
                    </DialogTitle>
                    <DialogDescription>
                        {count === 0
                            ? 'Everybody on this rota is marked. This just closes attendance for the service.'
                            : 'Everyone you have not tapped is recorded as absent for this service.'}
                    </DialogDescription>
                </DialogHeader>

                {count > 0 && (
                    <ul className="max-h-48 space-y-1 overflow-auto rounded-md border p-3 text-sm">
                        {untapped.map(assignment => (
                            <li key={assignment.id}>{name(assignment)}</li>
                        ))}
                    </ul>
                )}

                <p className="text-sm text-muted-foreground">
                    You can reopen the attendance afterwards to correct it.
                </p>

                {error && (
                    <Alert variant="destructive">
                        <p className="text-sm">{error}</p>
                    </Alert>
                )}

                <DialogFooter>
                    {/* "Keep going", not "Cancel": somebody who opened this by accident wants to
                        carry on tapping, and the button should say so. */}
                    <Button variant="outline" disabled={busy} onClick={onCancel}>
                        Keep going
                    </Button>
                    <Button disabled={busy} onClick={onConfirm}>
                        {busy
                            ? 'Finishing...'
                            : count === 0
                              ? 'Finish'
                              : `Mark ${count} absent and finish`}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
