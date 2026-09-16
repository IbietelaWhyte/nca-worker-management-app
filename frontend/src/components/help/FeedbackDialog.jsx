import { useState } from 'react'
import { browserContext, submitFeedback } from '@/api/feedback'
import { Button } from '@/components/ui/button'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'

// Where a problem happened. A short list the reporter picks from, rather than a route captured
// automatically: somebody opens Help after hitting the problem, so the page they came from is a
// guess, and a wrong guess sends triage the wrong way.
const AREAS = [
    'Dashboard',
    'My availability',
    'Schedules and rotas',
    'Workers',
    'Departments',
    'My account',
    'Text messages',
    'Somewhere else',
]

const EMPTY = { kind: 'bug', title: '', details: '', page: '' }

/**
 * Report a bug or suggest an improvement, filed as a GitHub issue by the backend.
 *
 * The notice about what gets attached is not boilerplate: reports land on a public tracker, so
 * somebody typing here deserves to know that before they type, not after.
 */
export default function FeedbackDialog({ open, onOpenChange }) {
    const [form, setForm] = useState(EMPTY)
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState(null)
    const [reference, setReference] = useState(null)

    const isBug = form.kind === 'bug'
    const set = (field, value) => setForm(prev => ({ ...prev, [field]: value }))

    const close = next => {
        onOpenChange(next)
        if (!next) {
            // Reset only on the way out, so a failed send keeps everything they typed.
            setForm(EMPTY)
            setError(null)
            setReference(null)
        }
    }

    const handleSubmit = async event => {
        event.preventDefault()
        if (form.title.trim().length < 3) return setError('Please give this a short name.')
        if (form.details.trim().length < 20)
            return setError('Please say a little more — a sentence or two is plenty.')

        setBusy(true)
        setError(null)
        try {
            const response = await submitFeedback({
                kind: form.kind,
                title: form.title.trim(),
                details: form.details.trim(),
                page: isBug && form.page ? form.page : null,
                ...browserContext(),
            })
            setReference(response.data.reference)
        } catch (err) {
            setError(
                err.response?.data?.detail ??
                    'Your report could not be sent. Please check your connection and try again.'
            )
        } finally {
            setBusy(false)
        }
    }

    return (
        <Dialog open={open} onOpenChange={close}>
            <DialogContent className="sm:max-w-lg">
                {reference ? (
                    <>
                        <DialogHeader>
                            <DialogTitle>Thank you</DialogTitle>
                            <DialogDescription>
                                Your report has been passed on. If you need to follow it up, quote
                                reference {reference}.
                            </DialogDescription>
                        </DialogHeader>
                        <DialogFooter>
                            <Button onClick={() => close(false)}>Close</Button>
                        </DialogFooter>
                    </>
                ) : (
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <DialogHeader>
                            <DialogTitle>Report a problem or suggest an improvement</DialogTitle>
                            <DialogDescription>
                                Tell us what happened in your own words.
                            </DialogDescription>
                        </DialogHeader>

                        <fieldset className="space-y-2">
                            <legend className="text-sm font-medium">
                                What kind of thing is this?
                            </legend>
                            <div className="flex flex-wrap gap-2">
                                {[
                                    { value: 'bug', label: 'Something is broken' },
                                    { value: 'idea', label: 'I have an idea' },
                                ].map(option => (
                                    <label
                                        key={option.value}
                                        className="flex min-h-11 cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm has-checked:border-primary has-checked:bg-primary/5 has-checked:font-medium"
                                    >
                                        <input
                                            type="radio"
                                            name="kind"
                                            value={option.value}
                                            checked={form.kind === option.value}
                                            onChange={e => set('kind', e.target.value)}
                                            className="accent-primary"
                                        />
                                        {option.label}
                                    </label>
                                ))}
                            </div>
                        </fieldset>

                        <div className="space-y-2">
                            <Label htmlFor="feedback-title">Short name</Label>
                            <Input
                                id="feedback-title"
                                value={form.title}
                                onChange={e => set('title', e.target.value)}
                                maxLength={80}
                                placeholder={
                                    isBug
                                        ? 'e.g. Availability will not save'
                                        : 'e.g. Show the rota for next month'
                                }
                            />
                        </div>

                        {isBug && (
                            <div className="space-y-2">
                                <Label htmlFor="feedback-area">
                                    Where did it happen?{' '}
                                    <span className="text-muted-foreground">(optional)</span>
                                </Label>
                                <select
                                    id="feedback-area"
                                    value={form.page}
                                    onChange={e => set('page', e.target.value)}
                                    className="w-full rounded-md border bg-background px-3 py-2 text-base focus:ring-2 focus:ring-ring focus:outline-none sm:text-sm"
                                >
                                    <option value="">— Choose a page —</option>
                                    {AREAS.map(area => (
                                        <option key={area} value={area}>
                                            {area}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        )}

                        <div className="space-y-2">
                            <Label htmlFor="feedback-details">
                                {isBug
                                    ? 'What happened, and what did you expect instead?'
                                    : 'What would you like to be able to do?'}
                            </Label>
                            <textarea
                                id="feedback-details"
                                value={form.details}
                                onChange={e => set('details', e.target.value)}
                                rows={5}
                                maxLength={2000}
                                className="w-full rounded-md border bg-background px-3 py-2 text-base focus:ring-2 focus:ring-ring focus:outline-none sm:text-sm"
                            />
                        </div>

                        <p className="text-xs text-muted-foreground">
                            Your report is sent to the people who build this app, along with which
                            browser you are using. It does not include your name, email or phone
                            number — but reports are kept somewhere public, so please do not write
                            personal details about other people here.
                        </p>

                        {error && (
                            <Alert variant="destructive">
                                <AlertDescription>{error}</AlertDescription>
                            </Alert>
                        )}

                        <DialogFooter>
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => close(false)}
                                disabled={busy}
                            >
                                Cancel
                            </Button>
                            <Button type="submit" disabled={busy}>
                                {busy ? 'Sending...' : 'Send report'}
                            </Button>
                        </DialogFooter>
                    </form>
                )}
            </DialogContent>
        </Dialog>
    )
}
