import { useState } from 'react'
import { format } from 'date-fns'
import { ChevronRight, FileClock, ImageDown, Send, Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useMonthlyLeads } from '@/hooks/useMonthlyLeads'
import { groupByMonth } from '@/lib/drafts'
import { summarizeStaffing } from '@/lib/staffing'
import UnderstaffedBadge from './UnderstaffedBadge'
import FinalizeDialog from './FinalizeDialog'
import DeleteMonthDialog from './DeleteMonthDialog'
import RotaExportDialog from './RotaExportDialog'

const readableDate = dateStr => format(new Date(dateStr + 'T00:00:00'), 'EEE d MMM')

/**
 * Every draft the department has, grouped by month. A draft texts nobody, so this is where a
 * month is reviewed and fixed before anybody hears about it; Finalize month is what tells them.
 *
 * One card list at every width: four short fields per row read fine on a phone, so this skips the
 * table/card split the other browse views need.
 */
/**
 * One draft month as the same shareable image the Month view exports. Its own component so the
 * monthly leads are fetched for that month, and only while it is open.
 */
function DraftMonthImage({ group, departmentId, departmentName, onClose }) {
    const monthlyLeads = useMonthlyLeads(departmentId, `${group.key}-01`)
    return (
        <Dialog open onOpenChange={next => !next && onClose()}>
            <DialogContent className="sm:max-w-4xl">
                <DialogHeader>
                    <DialogTitle>{group.label} draft as an image</DialogTitle>
                </DialogHeader>
                <RotaExportDialog
                    departmentId={departmentId}
                    departmentName={departmentName}
                    month={new Date(group.year, group.month - 1, 1)}
                    schedules={group.schedules}
                    monthlyLeads={monthlyLeads}
                    onClose={onClose}
                    draft
                />
            </DialogContent>
        </Dialog>
    )
}

export default function DraftsView({
    drafts,
    canManage,
    departmentId,
    departmentName,
    onOpen,
    onFinalizeMonth,
    onDeleteMonth,
}) {
    // { action: 'finalize' | 'delete' | 'image', group } — one month at a time.
    const [pending, setPending] = useState(null)
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState(null)

    const months = groupByMonth(drafts)

    if (months.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-8 text-center">
                <FileClock size={32} className="text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                    No drafts. Use Generate Month and choose Save Draft to plan a month without
                    texting anybody yet.
                </p>
            </div>
        )
    }

    const finalize = async () => {
        setBusy(true)
        setError(null)
        try {
            await onFinalizeMonth(pending.group.year, pending.group.month)
            setPending(null)
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Could not finalize this month')
        } finally {
            setBusy(false)
        }
    }

    return (
        <div className="space-y-6">
            <p className="text-sm text-muted-foreground">
                Drafts are not shown to workers and nobody is texted about them. Open one to edit
                it, then finalize it on its own or the whole month at once.
            </p>

            {months.map(group => (
                <section key={group.key} className="space-y-2">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <h3 className="font-semibold">
                            {group.label}{' '}
                            <span className="text-sm font-normal text-muted-foreground">
                                · {group.schedules.length}{' '}
                                {group.schedules.length === 1 ? 'draft' : 'drafts'}
                            </span>
                        </h3>
                        {canManage && (
                            <div className="flex flex-wrap gap-2">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setPending({ action: 'image', group })}
                                >
                                    <ImageDown size={14} className="mr-1.5" />
                                    View as image
                                </Button>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="text-destructive hover:text-destructive"
                                    onClick={() => setPending({ action: 'delete', group })}
                                >
                                    <Trash2 size={14} className="mr-1.5" />
                                    Delete month
                                </Button>
                                <Button
                                    size="sm"
                                    onClick={() => {
                                        setError(null)
                                        setPending({ action: 'finalize', group })
                                    }}
                                >
                                    <Send size={14} className="mr-1.5" />
                                    Finalize month
                                </Button>
                            </div>
                        )}
                    </div>

                    <ul className="space-y-2">
                        {group.schedules.map(schedule => {
                            const { assigned, max, short, understaffed } =
                                summarizeStaffing(schedule)
                            return (
                                <li key={schedule.id}>
                                    <button
                                        type="button"
                                        onClick={() => onOpen(schedule)}
                                        className="flex w-full items-center justify-between gap-3 rounded-lg border p-3 text-left transition-colors hover:bg-accent"
                                    >
                                        <div className="min-w-0 space-y-1">
                                            <p className="flex flex-wrap items-center gap-2 font-medium">
                                                {readableDate(schedule.scheduled_date)}
                                                <span className="font-normal text-muted-foreground">
                                                    {schedule.start_time?.slice(0, 5)}
                                                </span>
                                                {schedule.special_service_name && (
                                                    <Badge variant="warning">
                                                        {schedule.special_service_name}
                                                    </Badge>
                                                )}
                                            </p>
                                            <p className="truncate text-sm text-muted-foreground">
                                                {schedule.title}
                                                {schedule.creator &&
                                                    ` · started by ${schedule.creator.first_name} ${schedule.creator.last_name}`}
                                            </p>
                                            <div className="flex flex-wrap items-center gap-1.5">
                                                <Badge
                                                    variant={
                                                        understaffed ? 'destructive' : 'secondary'
                                                    }
                                                >
                                                    {assigned}/{max} assigned
                                                </Badge>
                                                {understaffed && (
                                                    <UnderstaffedBadge short={short} />
                                                )}
                                            </div>
                                        </div>
                                        <ChevronRight
                                            size={18}
                                            className="shrink-0 text-muted-foreground"
                                        />
                                    </button>
                                </li>
                            )
                        })}
                    </ul>
                </section>
            ))}

            {pending?.action === 'image' && (
                <DraftMonthImage
                    group={pending.group}
                    departmentId={departmentId}
                    departmentName={departmentName}
                    onClose={() => setPending(null)}
                />
            )}

            <FinalizeDialog
                open={pending?.action === 'finalize'}
                count={pending?.group.schedules.length ?? 0}
                people={pending?.group.people ?? 0}
                monthLabel={pending?.group.label}
                busy={busy}
                error={error}
                onCancel={() => setPending(null)}
                onConfirm={finalize}
            />

            <DeleteMonthDialog
                open={pending?.action === 'delete'}
                onOpenChange={next => !next && setPending(null)}
                monthLabel={pending?.group.label}
                status="draft"
                count={pending?.group.schedules.length ?? 0}
                people={pending?.group.people ?? 0}
                onConfirm={() => onDeleteMonth(pending.group.year, pending.group.month)}
            />
        </div>
    )
}
