import { useEffect, useState } from 'react'
import { ChevronDown, MessageSquarePlus } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { faqSectionsFor } from '@/lib/faq'
import { getFeedbackConfig } from '@/api/feedback'
import FeedbackDialog from '@/components/help/FeedbackDialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

/**
 * One question. A native <details> rather than a hand-rolled disclosure: it opens without
 * JavaScript, is keyboard and screen-reader operable as it stands, and lets the browser's own
 * find-in-page open the answer it matched.
 */
function FaqItem({ question, answer }) {
    return (
        <details className="group border-b last:border-b-0">
            {/* list-none kills the triangle everywhere except Safari, which needs the webkit
                pseudo-element. min-h-11 keeps the tap target at 44px. */}
            <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 p-4 text-sm font-medium hover:bg-accent [&::-webkit-details-marker]:hidden">
                {question}
                <ChevronDown
                    size={16}
                    className="shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
                />
            </summary>
            <p className="px-4 pb-4 text-sm leading-relaxed text-muted-foreground">{answer}</p>
        </details>
    )
}

/**
 * The answers to the questions workers and heads of department actually ask, in one place.
 *
 * Every signed-in user sees the same page; heads of department simply get more sections, since
 * they serve on rotas themselves and need the worker-facing answers as much as anybody.
 */
export default function HelpPage() {
    const { isDepartmentHead } = useAuth()
    const sections = faqSectionsFor(isDepartmentHead)
    const [reportingEnabled, setReportingEnabled] = useState(false)
    const [dialogOpen, setDialogOpen] = useState(false)

    // Hidden rather than broken when the backend has no GitHub credentials: a Send button that
    // always fails is worse than no button. A failed check leaves it hidden for the same reason.
    useEffect(() => {
        getFeedbackConfig()
            .then(response => setReportingEnabled(response.data.enabled))
            .catch(() => setReportingEnabled(false))
    }, [])

    return (
        <div className="max-w-3xl space-y-6">
            <div>
                <h2 className="text-2xl font-bold">Help</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                    The questions that come up most often.
                </p>
            </div>

            {sections.map(section => (
                <section key={section.id} className="space-y-2.5">
                    <h3 className="text-xs font-bold uppercase tracking-[0.1em] text-muted-foreground">
                        {section.title}
                    </h3>
                    <Card>
                        {section.items.map(item => (
                            <FaqItem key={item.question} {...item} />
                        ))}
                    </Card>
                </section>
            ))}

            {reportingEnabled && (
                <Card>
                    <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                            <h3 className="text-base font-semibold">Not answered here?</h3>
                            <p className="mt-1 text-sm text-muted-foreground">
                                Tell us what went wrong, or what would make this app easier to use.
                            </p>
                        </div>
                        <Button onClick={() => setDialogOpen(true)} className="shrink-0">
                            <MessageSquarePlus size={16} />
                            Report a problem
                        </Button>
                    </CardContent>
                </Card>
            )}

            <p className="text-sm text-muted-foreground">
                Still stuck? Speak to your head of department, or an administrator if it is about
                your account.
            </p>

            <FeedbackDialog open={dialogOpen} onOpenChange={setDialogOpen} />
        </div>
    )
}
