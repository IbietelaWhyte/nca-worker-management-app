import { useState } from 'react'
import { format } from 'date-fns'
import { CalendarIcon, Plus, ShieldAlert, Trash2 } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { useSpecialServices } from '@/hooks/useSpecialServices'
import {
    DAY_OPTIONS,
    WEEK_OPTIONS,
    describeSpecialService,
    weekCaveat,
} from '@/lib/specialServices'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'

const emptyRule = { name: '', day_of_week: 'sunday', week_of_month: 1 }
const emptyOneOff = { name: '', service_date: null }

/**
 * Church-wide special services: the dates the rota treats as bigger than an ordinary service.
 *
 * Two card-list sections and no `<Table>`. Three fields per row is legible at every width, so
 * this page skips the hidden-md/md:hidden split the browse tables need — deliberately, not by
 * omission.
 *
 * Admin-only, and it says so itself rather than redirecting: `ProtectedRoute` has no role prop,
 * and a head who follows a link here deserves an explanation rather than a bounce.
 */
export default function SpecialServicesPage() {
    const { isAdmin } = useAuth()
    const { services, loading, error, addService, editService, removeService } =
        useSpecialServices()
    const [ruleOpen, setRuleOpen] = useState(false)
    const [oneOffOpen, setOneOffOpen] = useState(false)
    const [rule, setRule] = useState(emptyRule)
    const [oneOff, setOneOff] = useState(emptyOneOff)
    const [calendarOpen, setCalendarOpen] = useState(false)
    const [saving, setSaving] = useState(false)
    const [formError, setFormError] = useState(null)
    const [removeTarget, setRemoveTarget] = useState(null)

    if (!isAdmin) {
        return (
            <Alert>
                <div className="flex items-start gap-3">
                    <ShieldAlert size={18} className="mt-0.5 shrink-0 text-muted-foreground" />
                    <div>
                        <p className="text-sm font-medium">Administrators only</p>
                        <p className="mt-1 text-sm text-muted-foreground">
                            Special services apply to every department&apos;s rota, so they are set
                            church-wide. Ask an administrator to add or change one.
                        </p>
                    </div>
                </div>
            </Alert>
        )
    }

    const rules = services.filter(s => s.kind === 'recurring')
    const oneOffs = services.filter(s => s.kind === 'one_off')

    const submit = async (payload, close) => {
        setFormError(null)
        setSaving(true)
        try {
            await addService(payload)
            close()
        } catch (err) {
            setFormError(err.response?.data?.detail ?? 'Could not save that')
        } finally {
            setSaving(false)
        }
    }

    const handleAddRule = () => {
        if (!rule.name.trim()) return setFormError('Give it a name')
        return submit({ kind: 'recurring', ...rule, name: rule.name.trim() }, () => {
            setRule(emptyRule)
            setRuleOpen(false)
        })
    }

    const handleAddOneOff = () => {
        if (!oneOff.name.trim()) return setFormError('Give it a name')
        if (!oneOff.service_date) return setFormError('Pick a date')
        return submit(
            {
                kind: 'one_off',
                name: oneOff.name.trim(),
                service_date: format(oneOff.service_date, 'yyyy-MM-dd'),
            },
            () => {
                setOneOff(emptyOneOff)
                setOneOffOpen(false)
            }
        )
    }

    const handleRemove = async () => {
        setSaving(true)
        try {
            await removeService(removeTarget.id)
            setRemoveTarget(null)
        } finally {
            setSaving(false)
        }
    }

    const renderCard = service => (
        <li
            key={service.id}
            className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between"
        >
            <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-2 font-medium">
                    {service.name}
                    {!service.is_active && <Badge variant="outline">Off</Badge>}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                    {describeSpecialService(service)}
                </p>
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-2">
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => editService(service.id, { is_active: !service.is_active })}
                >
                    {service.is_active ? 'Turn off' : 'Turn on'}
                </Button>
                <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    onClick={() => setRemoveTarget(service)}
                >
                    <Trash2 size={14} className="mr-1" />
                    Delete
                </Button>
            </div>
        </li>
    )

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h2 className="text-2xl font-bold">Special services</h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Dates the rota treats as bigger than an ordinary service. Workers take turns
                        on these separately, so the same few people do not get every one.
                    </p>
                </div>
            </div>

            {error && (
                <Alert variant="destructive">
                    <p className="text-sm">{error}</p>
                </Alert>
            )}

            {loading ? (
                <p className="py-8 text-center text-sm text-muted-foreground">Loading...</p>
            ) : (
                <>
                    <section className="space-y-3">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                            <h3 className="font-semibold">Every month</h3>
                            <Button size="sm" variant="outline" onClick={() => setRuleOpen(true)}>
                                <Plus size={16} className="mr-2" />
                                Add a monthly one
                            </Button>
                        </div>
                        {rules.length === 0 ? (
                            <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                                Nothing recurring yet. &ldquo;The first Sunday of every month&rdquo;
                                is the usual one.
                            </p>
                        ) : (
                            <ul className="space-y-2">{rules.map(renderCard)}</ul>
                        )}
                    </section>

                    <section className="space-y-3">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                            <h3 className="font-semibold">One-off dates</h3>
                            <Button size="sm" variant="outline" onClick={() => setOneOffOpen(true)}>
                                <Plus size={16} className="mr-2" />
                                Add a date
                            </Button>
                        </div>
                        {oneOffs.length === 0 ? (
                            <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                                No named dates yet, such as a Jesus is Lord Service.
                            </p>
                        ) : (
                            <ul className="space-y-2">{oneOffs.map(renderCard)}</ul>
                        )}
                    </section>
                </>
            )}

            {/* A rule is a sentence with two selects, never a cron editor. "Second and fourth
                Sunday" is two rows — there is deliberately no syntax for it. */}
            <Dialog
                open={ruleOpen}
                onOpenChange={next => {
                    if (saving) return
                    setFormError(null)
                    setRuleOpen(next)
                }}
            >
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>A service every month</DialogTitle>
                        <DialogDescription>
                            It will apply to every department&apos;s rota on that day.
                        </DialogDescription>
                    </DialogHeader>

                    {formError && (
                        <Alert variant="destructive">
                            <p className="text-sm">{formError}</p>
                        </Alert>
                    )}

                    <div className="space-y-2">
                        <Label htmlFor="rule-name">Name</Label>
                        <Input
                            id="rule-name"
                            value={rule.name}
                            onChange={e => setRule(prev => ({ ...prev, name: e.target.value }))}
                            placeholder="e.g. Communion"
                        />
                    </div>

                    <div className="space-y-2">
                        <Label>When</Label>
                        <div className="flex flex-wrap items-center gap-2 text-sm">
                            <span className="text-muted-foreground">On the</span>
                            <Select
                                value={String(rule.week_of_month)}
                                onValueChange={value =>
                                    setRule(prev => ({ ...prev, week_of_month: Number(value) }))
                                }
                            >
                                <SelectTrigger className="w-28">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {WEEK_OPTIONS.map(w => (
                                        <SelectItem key={w.value} value={String(w.value)}>
                                            {w.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <Select
                                value={rule.day_of_week}
                                onValueChange={value =>
                                    setRule(prev => ({ ...prev, day_of_week: value }))
                                }
                            >
                                <SelectTrigger className="w-36">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {DAY_OPTIONS.map(d => (
                                        <SelectItem key={d.value} value={d.value}>
                                            {d.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <span className="text-muted-foreground">of every month</span>
                        </div>
                        {weekCaveat(rule.week_of_month) && (
                            <p className="text-xs text-muted-foreground">
                                {weekCaveat(rule.week_of_month)}
                            </p>
                        )}
                    </div>

                    <DialogFooter>
                        <Button
                            variant="outline"
                            disabled={saving}
                            onClick={() => setRuleOpen(false)}
                        >
                            Cancel
                        </Button>
                        <Button disabled={saving} onClick={handleAddRule}>
                            {saving ? 'Saving...' : 'Add'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <Dialog
                open={oneOffOpen}
                onOpenChange={next => {
                    if (saving) return
                    setFormError(null)
                    setOneOffOpen(next)
                }}
            >
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>A one-off date</DialogTitle>
                        <DialogDescription>
                            For a service that does not follow a monthly pattern.
                        </DialogDescription>
                    </DialogHeader>

                    {formError && (
                        <Alert variant="destructive">
                            <p className="text-sm">{formError}</p>
                        </Alert>
                    )}

                    <div className="space-y-2">
                        <Label htmlFor="one-off-name">Name</Label>
                        <Input
                            id="one-off-name"
                            value={oneOff.name}
                            onChange={e => setOneOff(prev => ({ ...prev, name: e.target.value }))}
                            placeholder="e.g. Jesus is Lord Service"
                        />
                    </div>

                    <div className="space-y-2">
                        <Label>Date</Label>
                        <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
                            <PopoverTrigger asChild>
                                <Button
                                    type="button"
                                    variant="outline"
                                    className={cn(
                                        'w-full justify-start text-left font-normal',
                                        !oneOff.service_date && 'text-muted-foreground'
                                    )}
                                >
                                    <CalendarIcon size={16} className="mr-2" />
                                    {oneOff.service_date
                                        ? format(oneOff.service_date, 'PPP')
                                        : 'Pick a date'}
                                </Button>
                            </PopoverTrigger>
                            <PopoverContent className="w-auto p-0" align="start">
                                <Calendar
                                    mode="single"
                                    selected={oneOff.service_date}
                                    onSelect={value => {
                                        setOneOff(prev => ({ ...prev, service_date: value }))
                                        setCalendarOpen(false)
                                    }}
                                    initialFocus
                                />
                            </PopoverContent>
                        </Popover>
                    </div>

                    <DialogFooter>
                        <Button
                            variant="outline"
                            disabled={saving}
                            onClick={() => setOneOffOpen(false)}
                        >
                            Cancel
                        </Button>
                        <Button disabled={saving} onClick={handleAddOneOff}>
                            {saving ? 'Saving...' : 'Add'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <Dialog
                open={removeTarget !== null}
                onOpenChange={next => !saving && !next && setRemoveTarget(null)}
            >
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>Delete {removeTarget?.name}?</DialogTitle>
                        <DialogDescription>
                            Rotas already generated keep their record of it, so past dates stay
                            special and nobody&apos;s turn is undone. Future dates become ordinary.
                            Turning it off instead does the same without deleting it.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button
                            variant="outline"
                            disabled={saving}
                            onClick={() => setRemoveTarget(null)}
                        >
                            Cancel
                        </Button>
                        <Button variant="destructive" disabled={saving} onClick={handleRemove}>
                            {saving ? 'Deleting...' : 'Delete'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
