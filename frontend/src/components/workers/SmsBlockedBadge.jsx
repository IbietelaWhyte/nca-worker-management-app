import { MessageSquareOff } from 'lucide-react'
import { smsBlock } from '@/lib/sms'
import { Badge } from '@/components/ui/badge'

/** Flags a worker the app has stopped texting, so somebody reaches them another way. */
export default function SmsBlockedBadge({ worker, className }) {
    const block = smsBlock(worker)
    if (!block) return null
    return (
        <Badge
            variant="destructive"
            title={block.hint}
            aria-label={block.hint}
            className={className}
        >
            <MessageSquareOff size={10} className="mr-1" />
            {block.label}
        </Badge>
    )
}
