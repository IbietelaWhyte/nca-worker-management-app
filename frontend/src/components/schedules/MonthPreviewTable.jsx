import { format } from 'date-fns'
import { AlertTriangle, CheckCircle, SkipForward } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { formatSlotRange } from '@/lib/staffing'

const STATUS_CONFIG = {
    planned: { label: 'Planned', variant: 'default', Icon: CheckCircle },
    understaffed: { label: 'Understaffed', variant: 'secondary', Icon: AlertTriangle },
    skipped_existing: { label: 'Already scheduled', variant: 'outline', Icon: SkipForward },
    skipped_no_workers: { label: 'Nobody available', variant: 'destructive', Icon: AlertTriangle },
}

const workerName = worker => `${worker.first_name} ${worker.last_name}`

// Workers in no subteam are their own group, labelled for the department itself.
const groupLabel = group => group.subteam?.name ?? 'Department (no subteam)'

// A group's slots are keyed by subteam so a swap only ever moves within that subteam.
export const groupKey = group => group.subteam?.id ?? ''

/**
 * The reviewable month plan, grouped by subteam.
 *
 * A department-wide schedule staffs each subteam to its own band, so each
 * date shows a section per subteam. Swap options come from that group's own alternates,
 * which is what keeps a subteam's quota intact.
 */
export default function MonthPreviewTable({ preview, selection, onSwap }) {
    const plannable = preview.dates.filter(d => d.status !== 'skipped_existing')
    const totalAssignments = Object.values(selection)
        .flatMap(byGroup => Object.values(byGroup))
        .flat().length

    return (
        <div className="space-y-3">
            <div className="max-h-[22rem] overflow-y-auto border rounded-lg divide-y">
                {preview.dates.map(datePlan => {
                    const config = STATUS_CONFIG[datePlan.status] ?? STATUS_CONFIG.planned
                    const { Icon } = config
                    const isSkipped = datePlan.status.startsWith('skipped')
                    const dateSelection = selection[datePlan.scheduled_date] ?? {}

                    return (
                        <div key={datePlan.scheduled_date} className="p-3 space-y-2">
                            <div className="flex items-center justify-between gap-3">
                                <p className="text-sm font-medium">
                                    {format(
                                        new Date(datePlan.scheduled_date + 'T00:00:00'),
                                        'EEE, MMM d'
                                    )}
                                </p>
                                <div className="flex shrink-0 items-center gap-2">
                                    {/* Gold, never red: a date can be both special and
                                        understaffed, and these say different things. This is
                                        the highest-value place for it — here is where a head
                                        decides which dates to keep. */}
                                    {datePlan.is_special && (
                                        <Badge variant="warning">
                                            {datePlan.special_service_name ?? 'Special'}
                                        </Badge>
                                    )}
                                    <Badge variant={config.variant}>
                                        <Icon size={12} className="mr-1" />
                                        {config.label}
                                    </Badge>
                                </div>
                            </div>

                            {datePlan.message && (
                                <p className="text-xs text-muted-foreground">{datePlan.message}</p>
                            )}

                            {!isSkipped &&
                                datePlan.groups.map(group => {
                                    const key = groupKey(group)
                                    const chosen = dateSelection[key] ?? []

                                    return (
                                        <div key={key || 'department'} className="pl-1 space-y-1.5">
                                            <div className="flex items-center justify-between gap-2">
                                                <p className="text-xs font-medium text-muted-foreground">
                                                    {groupLabel(group)}
                                                </p>
                                                <div className="flex items-center gap-1.5">
                                                    <span className="text-[11px] text-muted-foreground">
                                                        {chosen.length}/{group.max_workers}
                                                    </span>
                                                    {chosen.length < group.min_workers && (
                                                        <Badge variant="destructive">
                                                            {group.min_workers - chosen.length}{' '}
                                                            short
                                                        </Badge>
                                                    )}
                                                </div>
                                            </div>

                                            {group.message && (
                                                <p className="text-[11px] text-muted-foreground">
                                                    {group.message}
                                                </p>
                                            )}

                                            {chosen.map((workerId, index) => {
                                                // Swappable with anyone free in this group and
                                                // not already picked for it.
                                                const options = [
                                                    ...group.assignments.map(a => a.worker),
                                                    ...group.alternates,
                                                ].filter(
                                                    w => w.id === workerId || !chosen.includes(w.id)
                                                )

                                                return (
                                                    <Select
                                                        key={`${datePlan.scheduled_date}-${key}-${index}`}
                                                        value={workerId}
                                                        onValueChange={next =>
                                                            onSwap(
                                                                datePlan.scheduled_date,
                                                                key,
                                                                index,
                                                                next
                                                            )
                                                        }
                                                    >
                                                        <SelectTrigger size="sm">
                                                            <SelectValue />
                                                        </SelectTrigger>
                                                        <SelectContent>
                                                            {options.map(w => (
                                                                <SelectItem key={w.id} value={w.id}>
                                                                    {workerName(w)}
                                                                </SelectItem>
                                                            ))}
                                                        </SelectContent>
                                                    </Select>
                                                )
                                            })}
                                        </div>
                                    )
                                })}
                        </div>
                    )
                })}
            </div>

            <p className="text-xs text-muted-foreground">
                {plannable.length} date{plannable.length === 1 ? '' : 's'} to create ·{' '}
                {totalAssignments} assignment{totalAssignments === 1 ? '' : 's'} ·{' '}
                {formatSlotRange(preview.min_workers, preview.max_workers)} workers per date
            </p>
        </div>
    )
}
