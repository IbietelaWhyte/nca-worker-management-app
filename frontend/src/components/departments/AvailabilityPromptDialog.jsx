import { useEffect, useState } from 'react'
import { format } from 'date-fns'
import { CalendarClock, Send, Trash2 } from 'lucide-react'
import {
    createAvailabilityPrompt,
    deleteAvailabilityPrompt,
    getAvailabilityPrompts,
    sendAvailabilityPromptNow,
} from '@/api/availabilityPrompts'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'

const plural = (count, noun) => `${count} ${noun}${count === 1 ? '' : 's'}`

const describe = prompt =>
    prompt.mode === 'once'
        ? `Once on ${prompt.send_on}`
        : `Monthly on day ${prompt.repeat_day} of the month`

/**
 * Ask a department's workers to enter their availability — now, or on a schedule.
 *
 * Each message costs money to send, so this is a dialog with an explicit button rather than the
 * browser confirm() used by the schedule reminders.
 */
export default function AvailabilityPromptDialog({ open, onOpenChange, departmentId }) {
    const [prompts, setPrompts] = useState([])
    const [mode, setMode] = useState('once')
    const [sendOn, setSendOn] = useState(format(new Date(), 'yyyy-MM-dd'))
    const [repeatDay, setRepeatDay] = useState('20')
    const [busy, setBusy] = useState(false)
    const [result, setResult] = useState(null)
    const [error, setError] = useState(null)

    useEffect(() => {
        if (!open || !departmentId) return
        let cancelled = false
        getAvailabilityPrompts(departmentId)
            .then(response => {
                if (!cancelled) setPrompts(response.data)
            })
            .catch(() => {
                if (!cancelled) setError('Could not load the scheduled prompts.')
            })
        return () => {
            cancelled = true
        }
    }, [open, departmentId])

    const handleSendNow = async () => {
        setBusy(true)
        setError(null)
        setResult(null)
        try {
            const response = await sendAvailabilityPromptNow(departmentId)
            setResult(response.data)
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Could not send the prompt.')
        } finally {
            setBusy(false)
        }
    }

    const handleSchedule = async () => {
        setBusy(true)
        setError(null)
        setResult(null)
        try {
            const payload =
                mode === 'once'
                    ? { mode, send_on: sendOn }
                    : { mode, repeat_day: Number(repeatDay) }
            const response = await createAvailabilityPrompt(departmentId, payload)
            setPrompts(prev => [response.data, ...prev])
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Could not schedule the prompt.')
        } finally {
            setBusy(false)
        }
    }

    const handleDelete = async promptId => {
        setError(null)
        try {
            await deleteAvailabilityPrompt(departmentId, promptId)
            setPrompts(prev => prev.filter(p => p.id !== promptId))
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Could not remove the prompt.')
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-lg">
                <DialogHeader>
                    <DialogTitle>Prompt for availability</DialogTitle>
                    <DialogDescription>
                        Text this department&apos;s active workers a link where they can enter the
                        dates they can serve. No login is needed to use the link.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-5">
                    {error && (
                        <Alert variant="destructive">
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    )}

                    {result && (
                        <Alert>
                            <AlertDescription>
                                Texted {plural(result.sent, 'worker')}.
                                {result.skipped_no_phone > 0 &&
                                    ` ${plural(result.skipped_no_phone, 'worker')} skipped — no phone number on file.`}
                                {result.failed > 0 &&
                                    ` ${plural(result.failed, 'message')} failed to send.`}
                            </AlertDescription>
                        </Alert>
                    )}

                    <div className="flex justify-end">
                        <Button onClick={handleSendNow} disabled={busy}>
                            <Send size={16} className="mr-2" />
                            {busy ? 'Sending…' : 'Send now'}
                        </Button>
                    </div>

                    <div className="border-t pt-5 space-y-3">
                        <Label>Or schedule it</Label>
                        <div className="flex flex-col gap-2 sm:flex-row">
                            <Select value={mode} onValueChange={setMode}>
                                <SelectTrigger className="w-full sm:w-40">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="once">Once</SelectItem>
                                    <SelectItem value="monthly">Every month</SelectItem>
                                </SelectContent>
                            </Select>

                            {mode === 'once' ? (
                                <Input
                                    type="date"
                                    value={sendOn}
                                    onChange={e => setSendOn(e.target.value)}
                                    className="flex-1"
                                />
                            ) : (
                                <Input
                                    type="number"
                                    min={1}
                                    max={28}
                                    value={repeatDay}
                                    onChange={e => setRepeatDay(e.target.value)}
                                    className="flex-1"
                                    // Capped at 28 so the day exists in February.
                                    placeholder="Day of month (1-28)"
                                />
                            )}

                            <Button variant="outline" onClick={handleSchedule} disabled={busy}>
                                <CalendarClock size={16} className="mr-2" />
                                Schedule
                            </Button>
                        </div>
                    </div>

                    {prompts.length > 0 && (
                        <div className="border-t pt-5 space-y-2">
                            <Label>Scheduled</Label>
                            {prompts.map(prompt => (
                                <div
                                    key={prompt.id}
                                    className="flex items-center justify-between text-sm rounded-md border px-3 py-2"
                                >
                                    <span>
                                        {describe(prompt)}
                                        {prompt.last_sent_on && (
                                            <span className="text-muted-foreground">
                                                {' '}
                                                · last sent {prompt.last_sent_on}
                                            </span>
                                        )}
                                    </span>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        onClick={() => handleDelete(prompt.id)}
                                        className="-mr-2 shrink-0 text-muted-foreground hover:text-destructive"
                                        aria-label="Remove prompt"
                                    >
                                        <Trash2 size={16} />
                                    </Button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    )
}
