import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { orderGroups } from '@/lib/rota'
import { Button } from '@/components/ui/button'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'

/**
 * Arrange the subteams of an exported rota, top to bottom.
 *
 * Up and down buttons rather than drag and drop: no extra dependency, a reliable tap target on a
 * phone, and usable from the keyboard. The list is short — a department's subteams plus the
 * Department group — so moving one place at a time is quick enough.
 *
 * Mounted only while open, so each opening starts from the order currently in use.
 */
export default function RotaOrderDialog({ groups, onSave, onClose }) {
    const [working, setWorking] = useState(groups)

    const move = (index, offset) =>
        setWorking(prev => {
            const next = [...prev]
            const [item] = next.splice(index, 1)
            next.splice(index + offset, 0, item)
            return next
        })

    return (
        <Dialog open onOpenChange={open => !open && onClose()}>
            <DialogContent className="sm:max-w-sm">
                <DialogHeader>
                    <DialogTitle>Subteam order</DialogTitle>
                    <DialogDescription>
                        The order subteams appear in on each date of the exported rota. Remembered
                        on this device for this department.
                    </DialogDescription>
                </DialogHeader>

                <ol className="divide-y rounded-md border">
                    {working.map((group, index) => (
                        <li key={group.key} className="flex items-center gap-2 px-3 py-2">
                            <span className="w-5 text-right text-xs text-muted-foreground">
                                {index + 1}
                            </span>
                            <span className="min-w-0 flex-1 truncate text-sm">{group.label}</span>
                            <Button
                                variant="outline"
                                size="icon-sm"
                                aria-label={`Move ${group.label} up`}
                                disabled={index === 0}
                                onClick={() => move(index, -1)}
                            >
                                <ChevronUp size={16} />
                            </Button>
                            <Button
                                variant="outline"
                                size="icon-sm"
                                aria-label={`Move ${group.label} down`}
                                disabled={index === working.length - 1}
                                onClick={() => move(index, 1)}
                            >
                                <ChevronDown size={16} />
                            </Button>
                        </li>
                    ))}
                </ol>

                <DialogFooter className="sm:justify-between">
                    {/* An empty order is the default: alphabetical, Department last. */}
                    <Button variant="ghost" onClick={() => setWorking(orderGroups(working, []))}>
                        Reset to A–Z
                    </Button>
                    <div className="flex flex-col-reverse gap-2 sm:flex-row">
                        <Button variant="outline" onClick={onClose}>
                            Cancel
                        </Button>
                        <Button onClick={() => onSave(working.map(group => group.key))}>
                            Save
                        </Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
