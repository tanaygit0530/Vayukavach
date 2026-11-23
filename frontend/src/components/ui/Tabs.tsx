import clsx from 'clsx'
import { useId, type KeyboardEvent } from 'react'

interface TabsProps<T extends string> {
  tabs: { id: T; label: string }[]
  value: T
  onChange: (id: T) => void
  label: string
}

/** Segmented control (ARIA tabs pattern, arrow-key navigation). */
export function Tabs<T extends string>({ tabs, value, onChange, label }: TabsProps<T>) {
  const id = useId()
  const onKey = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    event.preventDefault()
    const next = tabs[(index + step + tabs.length) % tabs.length]
    onChange(next.id)
    document.getElementById(`${id}-${next.id}`)?.focus()
  }
  return (
    <div role="tablist" aria-label={label} className="inline-flex rounded-full bg-slate-100 p-1">
      {tabs.map((tab, index) => {
        const active = tab.id === value
        return (
          <button
            key={tab.id}
            id={`${id}-${tab.id}`}
            role="tab"
            type="button"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(tab.id)}
            onKeyDown={(e) => onKey(e, index)}
            className={clsx(
              'focus-ring min-h-[36px] rounded-full px-4 text-[13px] font-medium transition-colors',
              active ? 'bg-white text-ink shadow-sm' : 'text-ink-muted hover:text-ink',
            )}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
