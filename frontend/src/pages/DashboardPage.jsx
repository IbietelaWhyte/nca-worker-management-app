import { format } from 'date-fns'
import { Link } from 'react-router-dom'
import { CalendarDays, CalendarPlus } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { useDashboard } from '@/hooks/useDashboard'
import { useMyDuties } from '@/hooks/useMyDuties'
import { Alert } from '@/components/ui/alert'
import { buttonVariants } from '@/components/ui/button'
import AttentionList from '@/components/dashboard/AttentionList'
import DutyCard from '@/components/dashboard/DutyCard'
import NextServiceCard from '@/components/dashboard/NextServiceCard'
import UpcomingList from '@/components/dashboard/UpcomingList'

function SectionLabel({ children }) {
    return (
        <h3 className="mb-2.5 text-xs font-bold tracking-[0.1em] text-muted-foreground uppercase">
            {children}
        </h3>
    )
}

function Loading({ what }) {
    return (
        <div className="flex h-64 items-center justify-center">
            <p className="text-muted-foreground">Loading {what}...</p>
        </div>
    )
}

/**
 * The board: every upcoming service across the departments the viewer manages.
 *
 * No role branch inside — `GET /departments` is scoped server-side, so an admin lays out five
 * departments and a head of department lays out one, from the same markup.
 */
function DepartmentBoard() {
    const { upcoming, attention, loading, error } = useDashboard()

    if (loading) return <Loading what="your dashboard" />

    const [next, ...rest] = upcoming

    return (
        <>
            {error && (
                <Alert variant="destructive">
                    <p className="text-sm">{error}</p>
                </Alert>
            )}

            <section>
                <SectionLabel>Upcoming</SectionLabel>
                {next ? (
                    <div className="space-y-2.5">
                        <NextServiceCard entry={next} />
                        <UpcomingList entries={rest} />
                    </div>
                ) : (
                    <div className="flex h-48 flex-col items-center justify-center gap-3 rounded-lg border border-dashed p-6 text-center">
                        <CalendarDays size={32} className="text-muted-foreground" />
                        <p className="text-sm text-muted-foreground">
                            Nothing scheduled in the next two months
                        </p>
                        <Link
                            to="/schedules"
                            className={buttonVariants({ variant: 'outline', size: 'sm' })}
                        >
                            <CalendarPlus size={14} className="mr-2" />
                            Generate a month
                        </Link>
                    </div>
                )}
            </section>

            {attention.length > 0 && (
                <section>
                    <SectionLabel>Needs attention</SectionLabel>
                    <AttentionList items={attention} />
                </section>
            )}
        </>
    )
}

/** What a worker with no management role sees: their own duties, and nobody else's. */
function MyDuties() {
    const { next, later, profile, loading, error, answer } = useMyDuties()

    if (loading) return <Loading what="your duties" />

    if (error) {
        return (
            <Alert variant="destructive">
                <p className="text-sm">{error}</p>
            </Alert>
        )
    }

    // A login can exist without a worker record behind it, which is a different thing from having
    // nothing scheduled — say so rather than showing an empty rota.
    if (!profile) {
        return (
            <div className="flex h-48 flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-6 text-center">
                <p className="text-sm text-muted-foreground">
                    Your account is not linked to a worker profile yet.
                </p>
                <p className="text-xs text-muted-foreground">
                    An administrator can connect it for you.
                </p>
            </div>
        )
    }

    if (!next) {
        return (
            <section>
                <SectionLabel>Your duties</SectionLabel>
                <div className="flex h-48 flex-col items-center justify-center gap-3 rounded-lg border border-dashed p-6 text-center">
                    <CalendarDays size={32} className="text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">
                        You are not scheduled for anything yet
                    </p>
                    <Link
                        to="/availability"
                        className={buttonVariants({ variant: 'outline', size: 'sm' })}
                    >
                        Set your availability
                    </Link>
                </div>
            </section>
        )
    }

    return (
        <>
            <section>
                <SectionLabel>Your next duty</SectionLabel>
                <DutyCard assignment={next} onAnswer={answer} />
            </section>

            {later.length > 0 && (
                <section>
                    <SectionLabel>Also coming up</SectionLabel>
                    <div className="space-y-2.5">
                        {later.map(assignment => (
                            <DutyCard
                                key={assignment.id}
                                assignment={assignment}
                                onAnswer={answer}
                            />
                        ))}
                    </div>
                </section>
            )}
        </>
    )
}

export default function DashboardPage() {
    const { isDepartmentHead } = useAuth()

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-2xl font-bold">{format(new Date(), 'EEEE, d MMMM')}</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                    {isDepartmentHead
                        ? 'What is coming up, and who still owes an answer.'
                        : 'Your upcoming duties.'}
                </p>
            </div>

            {/*
             * isDepartmentHead is the right gate rather than isAdmin: GET /departments scopes heads
             * of department, but lets a plain worker fall through to every department, so keying
             * the board on "departments I can see" would show a volunteer the whole church's rotas.
             */}
            {isDepartmentHead ? <DepartmentBoard /> : <MyDuties />}
        </div>
    )
}
