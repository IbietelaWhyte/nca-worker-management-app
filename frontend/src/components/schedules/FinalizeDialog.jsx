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

/**
 * The one step that tells people. Everything before it — generating, saving a draft, editing a
 * draft — texts nobody; this publishes the rota and the notice job texts everybody on it.
 *
 * The confirm is the ordinary purple button: finalizing is a routine completion, and in this app
 * red means delete.
 *
 * @param {object} props
 * @param {number} props.count Rotas being finalized.
 * @param {number} props.people Distinct people on them, each texted once.
 * @param {string} [props.monthLabel] "March 2027" when finalizing a month.
 */
export default function FinalizeDialog({
    open,
    count,
    people,
    monthLabel,
    busy,
    error,
    onCancel,
    onConfirm,
}) {
    const what =
        count === 1 ? 'this rota' : `the ${count} rotas${monthLabel ? ` for ${monthLabel}` : ''}`
    const who = `${people} ${people === 1 ? 'person' : 'people'}`

    return (
        <Dialog open={open} onOpenChange={next => !busy && !next && onCancel()}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>
                        {count === 1 ? 'Finalize this rota?' : `Finalize ${count} rotas?`}
                    </DialogTitle>
                    <DialogDescription>
                        Everyone on {what} ({who}) will get a text saying they have been scheduled,
                        within about 10 minutes.
                    </DialogDescription>
                </DialogHeader>

                <p className="text-sm text-muted-foreground">
                    You can still change a rota after it is finalized, but each change texts the
                    people it affects.
                </p>

                {error && (
                    <Alert variant="destructive">
                        <p className="text-sm">{error}</p>
                    </Alert>
                )}

                <DialogFooter>
                    <Button variant="outline" disabled={busy} onClick={onCancel}>
                        Not yet
                    </Button>
                    <Button disabled={busy} onClick={onConfirm}>
                        {busy ? 'Finalizing...' : 'Yes, finalize and text them'}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
