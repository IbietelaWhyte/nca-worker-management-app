import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AlertCircle } from 'lucide-react'
import SpecificDatesCalendar from '@/components/availability/SpecificDatesCalendar'
import {
    clearAvailabilityByLink,
    getAvailabilityByLink,
    setAvailabilityByLink,
} from '@/api/availabilityLink'
import BrandMark from '@/components/layout/BrandMark'

// The public twin of AvailabilityPage. Same calendar, but the worker is identified by the token
// in the URL instead of a session — most workers have no login account, so a prompt pointing at
// the app would reach almost nobody.
//
// Page states:
// loading -> resolving the token
// ready   -> calendar shown
// invalid -> token unknown or expired
// error   -> unexpected network / server error

export default function AvailabilityLinkPage() {
    const { token } = useParams()

    const [pageState, setPageState] = useState('loading')
    const [workerName, setWorkerName] = useState('')
    const [dates, setDates] = useState([])
    const [saving, setSaving] = useState(false)
    const [errorMessage, setErrorMessage] = useState('')

    useEffect(() => {
        async function fetchAvailability() {
            try {
                const data = await getAvailabilityByLink(token)
                setWorkerName(data.worker_name)
                setDates(data.dates ?? [])
                setPageState('ready')
            } catch (err) {
                const status = err.response?.status
                if (status === 404 || status === 410) {
                    setErrorMessage(
                        status === 410
                            ? 'This link has expired.'
                            : 'This link is invalid or does not exist.'
                    )
                    setPageState('invalid')
                } else {
                    setErrorMessage('Something went wrong. Please try again later.')
                    setPageState('error')
                }
            }
        }

        fetchAvailability()
    }, [token])

    // Same three-state cycle as the signed-in page: unset -> available -> unavailable -> unset.
    async function handleDateClick(dateStr, existing) {
        setSaving(true)
        setErrorMessage('')
        try {
            if (!existing) {
                const record = await setAvailabilityByLink(token, dateStr, true)
                setDates(prev => [...prev, record])
            } else if (existing.is_available) {
                const record = await setAvailabilityByLink(token, dateStr, false)
                setDates(prev => prev.map(d => (d.id === existing.id ? record : d)))
            } else {
                await clearAvailabilityByLink(token, dateStr)
                setDates(prev => prev.filter(d => d.id !== existing.id))
            }
        } catch (err) {
            if (err.response?.status === 410) {
                setErrorMessage('This link has expired.')
                setPageState('invalid')
            } else {
                setErrorMessage('Could not save that date. Please try again.')
            }
        } finally {
            setSaving(false)
        }
    }

    return (
        <div className="min-h-dvh bg-muted flex items-center justify-center p-4">
            <div className="w-full max-w-lg bg-card rounded-2xl shadow-md p-5 sm:p-8">
                <div className="flex flex-col items-center gap-3 mb-8">
                    <BrandMark className="w-36" />
                    <p className="text-center text-xs font-semibold text-muted-foreground uppercase tracking-[0.18em]">
                        Your Availability
                    </p>
                </div>

                {pageState === 'loading' && (
                    <div className="flex flex-col items-center gap-4 py-8 text-muted-foreground">
                        <div className="h-8 w-8 rounded-full border-4 border-border border-t-primary animate-spin" />
                        <p className="text-sm">Loading your availability…</p>
                    </div>
                )}

                {pageState === 'ready' && (
                    <div className="space-y-6">
                        <div className="text-center">
                            <h1 className="text-xl font-semibold text-foreground">
                                Hi {workerName}
                            </h1>
                            <p className="text-sm text-muted-foreground mt-1">
                                Tap the dates you can serve. Tap again to mark yourself unavailable,
                                and once more to clear it.
                            </p>
                        </div>

                        {errorMessage && (
                            <p className="text-sm text-destructive text-center">{errorMessage}</p>
                        )}

                        <SpecificDatesCalendar
                            specificDates={dates}
                            onDateClick={handleDateClick}
                            loading={saving}
                        />

                        <p className="text-xs text-center text-muted-foreground">
                            Your answers save as you tap. You can return to this link any time.
                        </p>
                    </div>
                )}

                {(pageState === 'invalid' || pageState === 'error') && (
                    <div className="flex flex-col items-center gap-4 py-6 text-center">
                        <AlertCircle className="h-14 w-14 text-warning" />
                        <div>
                            <h2 className="text-lg font-semibold text-foreground">
                                Link unavailable
                            </h2>
                            <p className="text-sm text-muted-foreground mt-1">{errorMessage}</p>
                        </div>
                        <p className="text-xs text-muted-foreground mt-2">
                            Contact your supervisor if you need assistance.
                        </p>
                    </div>
                )}
            </div>
        </div>
    )
}
