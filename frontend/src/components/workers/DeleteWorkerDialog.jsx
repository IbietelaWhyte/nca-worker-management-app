import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'

// Unlike the other worker dialogs this owns its own <Dialog> wrapper, so it can lock itself
// closed while the delete is in flight.
export default function DeleteWorkerDialog({ worker, open, onOpenChange, onDeleted }) {
    const [deleting, setDeleting] = useState(false)
    const [error, setError] = useState(null)

    if (!worker) return null

    const name = `${worker.first_name} ${worker.last_name}`

    const handleDelete = async () => {
        setError(null)
        setDeleting(true)
        try {
            await onDeleted(worker.id)
            setDeleting(false)
            onOpenChange(false)
        } catch (err) {
            // The backend blocks deletion when the worker still has upcoming assignments or
            // heads a department. Those messages tell the user what to do, so show them as-is.
            setError(err.response?.data?.detail ?? err.message ?? 'Failed to delete this worker')
            setDeleting(false)
        }
    }

    const handleOpenChange = next => {
        if (deleting) return
        setError(null)
        onOpenChange(next)
    }

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <AlertTriangle size={18} className="text-destructive" />
                        Delete {name}?
                    </DialogTitle>
                    <DialogDescription>
                        This permanently removes their profile, login, roles, department
                        memberships, availability and past schedule assignments. This cannot be
                        undone.
                    </DialogDescription>
                </DialogHeader>

                {error && (
                    <Alert variant="destructive">
                        <AlertDescription>{error}</AlertDescription>
                    </Alert>
                )}

                <DialogFooter>
                    <Button
                        variant="outline"
                        onClick={() => handleOpenChange(false)}
                        disabled={deleting}
                    >
                        Cancel
                    </Button>
                    <Button
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        onClick={handleDelete}
                        disabled={deleting}
                    >
                        {deleting ? 'Deleting...' : 'Delete worker'}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
