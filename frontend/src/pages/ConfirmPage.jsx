import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { CheckCircle, XCircle, Clock, AlertCircle, CalendarDays, User } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { getConfirmationDetails, submitConfirmation } from '@/api/confirmation'

// Page states:
// loading  -> fetching assignment details on mount
// ready    -> details loaded, waiting for worker action
// done     -> worker has confirmed/declined (success)
// invalid  -> token not found, already used, or expired (no action possible)
// error    -> unexpected network / server error

export default function ConfirmPage() {
    const { token } = useParams()

    const [pageState, setPageState] = useState('loading')
    const [details, setDetails] = useState(null)
    const [submitting, setSubmitting] = useState(null) // 'confirmed' | 'declined' | null
    const [chosenAction, setChosenAction] = useState(null)
    const [errorMessage, setErrorMessage] = useState('')

    useEffect(() => {
        async function fetchDetails() {
            try {
                const data = await getConfirmationDetails(token)
                setDetails(data)

                if (data.already_used) {
                    setErrorMessage('This confirmation link has already been used.')
                    setPageState('invalid')
                } else if (data.expired) {
                    setErrorMessage('This confirmation link has expired.')
                    setPageState('invalid')
                } else {
                    setPageState('ready')
                }
            } catch (err) {
                if (err.response?.status === 404) {
                    setErrorMessage('This confirmation link is invalid or does not exist.')
                    setPageState('invalid')
                } else {
                    setErrorMessage('Something went wrong. Please try again later.')
                    setPageState('error')
                }
            }
        }

        fetchDetails()
    }, [token])

    async function handleAction(action) {
        setSubmitting(action)
        try {
            await submitConfirmation(token, action)
            setChosenAction(action)
            setPageState('done')
        } catch (err) {
            if (err.response?.status === 410) {
                setErrorMessage(err.response.data?.detail ?? 'This link is no longer valid.')
                setPageState('invalid')
            } else {
                setErrorMessage('Something went wrong. Please try again.')
                setPageState('error')
            }
        } finally {
            setSubmitting(null)
        }
    }

    return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
            <div className="w-full max-w-md bg-white rounded-2xl shadow-md p-8">
                {/* Logo / app name */}
                <p className="text-center text-sm font-semibold text-gray-400 uppercase tracking-widest mb-8">
                    Worker Schedule
                </p>

                {pageState === 'loading' && <LoadingState />}
                {pageState === 'ready' && details && (
                    <ReadyState details={details} submitting={submitting} onAction={handleAction} />
                )}
                {pageState === 'done' && <DoneState action={chosenAction} details={details} />}
                {(pageState === 'invalid' || pageState === 'error') && (
                    <InvalidState message={errorMessage} />
                )}
            </div>
        </div>
    )
}

// Sub-components

function LoadingState() {
    return (
        <div className="flex flex-col items-center gap-4 py-8 text-gray-500">
            <div className="h-8 w-8 rounded-full border-4 border-gray-200 border-t-primary animate-spin" />
            <p className="text-sm">Loading your schedule…</p>
        </div>
    )
}

function ReadyState({ details, submitting, onAction }) {
    return (
        <div className="space-y-6">
            <div className="text-center">
                <h1 className="text-xl font-semibold text-gray-900">Schedule Confirmation</h1>
                <p className="text-sm text-gray-500 mt-1">Please confirm your availability</p>
            </div>

            {/* Assignment details card */}
            <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 space-y-3">
                <DetailRow
                    icon={<User className="h-4 w-4 text-gray-400" />}
                    label="Worker"
                    value={details.worker_name}
                />
                <DetailRow
                    icon={<CalendarDays className="h-4 w-4 text-gray-400" />}
                    label="Event"
                    value={details.schedule_title}
                />
                <DetailRow
                    icon={<Clock className="h-4 w-4 text-gray-400" />}
                    label="Date"
                    value={details.scheduled_date}
                />
                <DetailRow
                    icon={<Clock className="h-4 w-4 text-gray-400" />}
                    label="Time"
                    value={`${details.start_time} – ${details.end_time}`}
                />
            </div>

            {/* Action buttons */}
            <div className="grid grid-cols-2 gap-3">
                <Button
                    onClick={() => onAction('confirmed')}
                    disabled={submitting !== null}
                    className="gap-2 bg-green-600 hover:bg-green-700 text-white"
                >
                    {submitting === 'confirmed' ? (
                        <span className="h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                    ) : (
                        <CheckCircle className="h-4 w-4" />
                    )}
                    Confirm
                </Button>
                <Button
                    variant="outline"
                    onClick={() => onAction('declined')}
                    disabled={submitting !== null}
                    className="gap-2 border-red-300 text-red-600 hover:bg-red-50 hover:text-red-700"
                >
                    {submitting === 'declined' ? (
                        <span className="h-4 w-4 rounded-full border-2 border-red-400 border-t-transparent animate-spin" />
                    ) : (
                        <XCircle className="h-4 w-4" />
                    )}
                    Decline
                </Button>
            </div>

            <p className="text-xs text-center text-gray-400">
                This link can only be used once and expires after 48 hours.
            </p>
        </div>
    )
}

function DoneState({ action, details }) {
    const confirmed = action === 'confirmed'
    return (
        <div className="flex flex-col items-center gap-4 py-6 text-center">
            {confirmed ? (
                <CheckCircle className="h-14 w-14 text-green-500" />
            ) : (
                <XCircle className="h-14 w-14 text-red-400" />
            )}
            <div>
                <h2 className="text-lg font-semibold text-gray-900">
                    {confirmed ? "You're confirmed!" : 'Response recorded'}
                </h2>
                <p className="text-sm text-gray-500 mt-1">
                    {confirmed
                        ? `See you at ${details?.schedule_title} on ${details?.scheduled_date}.`
                        : 'Your declination has been noted. Your supervisor will be in touch.'}
                </p>
            </div>
            <p className="text-xs text-gray-400 mt-2">You can now close this page.</p>
        </div>
    )
}

function InvalidState({ message }) {
    return (
        <div className="flex flex-col items-center gap-4 py-6 text-center">
            <AlertCircle className="h-14 w-14 text-amber-400" />
            <div>
                <h2 className="text-lg font-semibold text-gray-900">Link unavailable</h2>
                <p className="text-sm text-gray-500 mt-1">{message}</p>
            </div>
            <p className="text-xs text-gray-400 mt-2">
                Contact your supervisor if you need assistance.
            </p>
        </div>
    )
}

function DetailRow({ icon, label, value }) {
    return (
        <div className="flex items-start gap-3">
            <span className="mt-0.5 shrink-0">{icon}</span>
            <div className="flex-1 flex justify-between gap-2">
                <span className="text-xs text-gray-400 w-12 shrink-0">{label}</span>
                <span className="text-sm font-medium text-gray-800 text-right">{value}</span>
            </div>
        </div>
    )
}
