import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { CheckCircle, XCircle, AlertCircle, CalendarDays } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { getConfirmationDetails, submitConfirmation } from '@/api/confirmation'

// Page states:
// loading  -> fetching the worker's duties on mount
// ready    -> duties loaded, waiting for the worker to answer them
// invalid  -> token not found or expired (no action possible)
// error    -> unexpected network / server error
//
// There is no terminal "done" state any more: one link covers every upcoming date, so the worker
// answers them one at a time and the page stays open until they are finished.

export default function ConfirmPage() {
    const { token } = useParams()

    const [pageState, setPageState] = useState('loading')
    const [workerName, setWorkerName] = useState('')
    const [assignments, setAssignments] = useState([])
    const [submittingId, setSubmittingId] = useState(null)
    const [errorMessage, setErrorMessage] = useState('')

    useEffect(() => {
        async function fetchDetails() {
            try {
                const data = await getConfirmationDetails(token)
                setWorkerName(data.worker_name)
                setAssignments(data.assignments ?? [])

                if (data.expired) {
                    setErrorMessage('This link has expired.')
                    setPageState('invalid')
                } else {
                    setPageState('ready')
                }
            } catch (err) {
                if (err.response?.status === 404) {
                    setErrorMessage('This link is invalid or does not exist.')
                    setPageState('invalid')
                } else {
                    setErrorMessage('Something went wrong. Please try again later.')
                    setPageState('error')
                }
            }
        }

        fetchDetails()
    }, [token])

    async function handleAction(assignmentId, action) {
        setSubmittingId(assignmentId)
        setErrorMessage('')
        try {
            await submitConfirmation(token, assignmentId, action)
            // Patch just the answered row; the rest stay actionable.
            setAssignments(prev =>
                prev.map(a => (a.assignment_id === assignmentId ? { ...a, status: action } : a))
            )
        } catch (err) {
            if (err.response?.status === 410) {
                setErrorMessage(err.response.data?.detail ?? 'This link is no longer valid.')
                setPageState('invalid')
            } else {
                setErrorMessage('Could not save that. Please try again.')
            }
        } finally {
            setSubmittingId(null)
        }
    }

    const answered = assignments.filter(a => a.status !== 'pending').length

    return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
            <div className="w-full max-w-lg bg-white rounded-2xl shadow-md p-8">
                <p className="text-center text-sm font-semibold text-gray-400 uppercase tracking-widest mb-8">
                    Worker Schedule
                </p>

                {pageState === 'loading' && <LoadingState />}

                {pageState === 'ready' && (
                    <div className="space-y-6">
                        <div className="text-center">
                            <h1 className="text-xl font-semibold text-gray-900">Hi {workerName}</h1>
                            <p className="text-sm text-gray-500 mt-1">
                                {assignments.length === 0
                                    ? 'You have no upcoming duties right now.'
                                    : 'Please confirm or decline each date below.'}
                            </p>
                        </div>

                        {errorMessage && (
                            <p className="text-sm text-red-600 text-center">{errorMessage}</p>
                        )}

                        <div className="space-y-3">
                            {assignments.map(assignment => (
                                <AssignmentRow
                                    key={assignment.assignment_id}
                                    assignment={assignment}
                                    submitting={submittingId === assignment.assignment_id}
                                    disabled={submittingId !== null}
                                    onAction={handleAction}
                                />
                            ))}
                        </div>

                        {assignments.length > 0 && (
                            <p className="text-xs text-center text-gray-400">
                                {answered} of {assignments.length} answered. You can come back to
                                this link any time to change your response.
                            </p>
                        )}
                    </div>
                )}

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

function AssignmentRow({ assignment, submitting, disabled, onAction }) {
    const confirmed = assignment.status === 'confirmed'
    const declined = assignment.status === 'declined'

    return (
        <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 space-y-3">
            <div className="flex items-start gap-3">
                <CalendarDays className="h-4 w-4 text-gray-400 mt-0.5 shrink-0" />
                <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900">{assignment.schedule_title}</p>
                    <p className="text-xs text-gray-500">
                        {assignment.scheduled_date} · {assignment.start_time} –{' '}
                        {assignment.end_time}
                    </p>
                </div>
            </div>

            {confirmed || declined ? (
                <div
                    className={`flex items-center gap-2 text-sm font-medium ${
                        confirmed ? 'text-green-700' : 'text-red-600'
                    }`}
                >
                    {confirmed ? (
                        <CheckCircle className="h-4 w-4" />
                    ) : (
                        <XCircle className="h-4 w-4" />
                    )}
                    {confirmed ? "You're confirmed" : 'You declined'}
                    <button
                        type="button"
                        onClick={() =>
                            onAction(assignment.assignment_id, confirmed ? 'declined' : 'confirmed')
                        }
                        disabled={disabled}
                        className="ml-auto text-xs font-normal text-gray-500 underline hover:text-gray-700 disabled:opacity-50"
                    >
                        Change
                    </button>
                </div>
            ) : (
                <div className="grid grid-cols-2 gap-3">
                    <Button
                        onClick={() => onAction(assignment.assignment_id, 'confirmed')}
                        disabled={disabled}
                        className="gap-2 bg-green-600 hover:bg-green-700 text-white"
                    >
                        {submitting ? (
                            <span className="h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                        ) : (
                            <CheckCircle className="h-4 w-4" />
                        )}
                        Confirm
                    </Button>
                    <Button
                        variant="outline"
                        onClick={() => onAction(assignment.assignment_id, 'declined')}
                        disabled={disabled}
                        className="gap-2 border-red-300 text-red-600 hover:bg-red-50 hover:text-red-700"
                    >
                        <XCircle className="h-4 w-4" />
                        Decline
                    </Button>
                </div>
            )}
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
