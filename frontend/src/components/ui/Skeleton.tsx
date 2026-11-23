import clsx from 'clsx'

/** Grey placeholder shape in the layout of the content it replaces. */
export function Skeleton({ className, round }: { className?: string; round?: boolean }) {
  return (
    <span
      aria-hidden
      className={clsx(
        'block bg-slate-200/80 motion-safe:animate-pulse',
        round ? 'rounded-full' : 'rounded-xl',
        className,
      )}
    />
  )
}

export function LoadingText({ label = 'Loading' }: { label?: string }) {
  return <span className="sr-only">{label}…</span>
}
