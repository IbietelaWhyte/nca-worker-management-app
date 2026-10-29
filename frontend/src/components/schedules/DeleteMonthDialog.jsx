import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
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
 * Deleting a department's month. Drafts go silently — nobody was told about them. Finalized rotas
 * go from today on only (past ones carry attendance), and everybody who had been told about a
 * deleted date gets one text. Owns its state, like DeleteWorkerDialog, so it can lock itself
 * closed while in flight and then show anybody a text could not reach.
 *
 * @param {object} props
 * @param {'draft'|'final'} props.status Which rotas the month's delete removes.
 * @param {number} props.count Rotas that will be deleted.
 * @param {number} props.people Distinct people on them.
 * @param {() => Promise<{warnings: string[]}>} props.onConfirm
 */
export default function DeleteMonthDialog({
    open,
    onOpenChange,
    monthLabel,
    status,
    count,
    people,
    onConfirm,
}) {
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState(null)
    const [warnings, setWarnings] = useState(null)

    const draft = status === 'draft'
    const rotas = `${count} ${draft ? 'draft ' : 'upcoming '}${count === 1 ? 'rota' : 'rotas'}`

    const close = () => {
        if (busy) return
        setError(null)
        setWarnings(null)
        onOpenChange(false)
    }

    const handleDelete = async () => {
        setError(null)
        setBusy(true)
        try {
            const result = await onConfirm()
            setBusy(false)
            // Anybody a cancellation could not reach has no other way of hearing: keep the dialog
            // open on their names rather than closing over them.
            if (result?.warnings?.length) {
                setWarnings(result.warnings)
            } else {
                onOpenChange(false)
            }
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Could not delete this month')
            setBusy(false)
        }
    }

    return (
        <Dialog open={open} onOpenChange={next => !next && close()}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <AlertTriangle size={18} className="text-destructive" />
                        {warnings ? 'Deleted' : `Delete ${rotas} for ${monthLabel}?`}
                    </DialogTitle>
                    {!warnings && (
                        <DialogDescription>
                            {draft
                                ? 'Nobody has been texted about them, so nobody is told. This cannot be undone.'
                                : `${people} ${people === 1 ? 'person' : 'people'} on them will be texted that they are no longer scheduled, if they had been told. Rotas already past are kept. This cannot be undone.`}
                        </DialogDescription>
                    )}
                </DialogHeader>

                {warnings && (
                    <Alert variant="warning">
                        <AlertDescription>
                            <p className="font-medium">Some people could not be texted:</p>
                            <ul className="mt-1 list-disc pl-5 text-sm">
                                {warnings.map(w => (
                                    <li key={w}>{w}</li>
                                ))}
                            </ul>
                        </AlertDescription>
                    </Alert>
                )}

                {error && (
                    <Alert variant="destructive">
                        <AlertDescription>{error}</AlertDescription>
                    </Alert>
                )}

                <DialogFooter>
                    {warnings ? (
                        <Button onClick={close}>Done</Button>
                    ) : (
                        <>
                            <Button variant="outline" onClick={close} disabled={busy}>
                                Cancel
                            </Button>
                            <Button
                                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                onClick={handleDelete}
                                disabled={busy || count === 0}
                            >
                                {busy ? 'Deleting...' : `Delete ${count === 1 ? 'rota' : 'rotas'}`}
                            </Button>
                        </>
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
