import { cn } from '@/lib/utils'
import { Check, X } from 'lucide-react'

const DAYS = [
  { key: 'sunday', label: 'Sun' },
  { key: 'monday', label: 'Mon' },
  { key: 'tuesday', label: 'Tue' },
  { key: 'wednesday', label: 'Wed' },
  { key: 'thursday', label: 'Thu' },
  { key: 'friday', label: 'Fri' },
  { key: 'saturday', label: 'Sat' },
]

export default function WeeklyGrid({ availabilityByDay, onToggle, loading }) {
  return (
    <div className="grid grid-cols-7 gap-2">
      {DAYS.map(({ key, label }) => {
        const record = availabilityByDay[key]
        const isAvailable = record?.is_available ?? false

        return (
          <button
            key={key}
            onClick={() => onToggle(key, record)}
            disabled={loading}
            className={cn(
              "flex flex-col items-center justify-center gap-2 p-4 rounded-lg border-2 transition-all",
              "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
              isAvailable
                ? "border-primary bg-primary text-primary-foreground hover:bg-primary/90"
                : "border-border bg-background text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            )}
          >
            <span className="text-xs font-semibold uppercase tracking-wide">
              {label}
            </span>
            <div className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center",
              isAvailable ? "bg-primary-foreground/20" : "bg-muted"
            )}>
              {isAvailable
                ? <Check size={16} strokeWidth={2.5} />
                : <X size={16} strokeWidth={2} />
              }
            </div>
            <span className="text-xs">
              {isAvailable ? 'Available' : 'Unavailable'}
            </span>
          </button>
        )
      })}
    </div>
  )
}