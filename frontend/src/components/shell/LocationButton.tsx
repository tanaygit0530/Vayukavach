import { ChevronDown, MapPin } from 'lucide-react'
import { forwardRef } from 'react'

import { useDistricts } from '../../lib/queries'
import { Skeleton } from '../ui/Skeleton'

interface Props {
  place: string
  open: boolean
  onClick: () => void
}

/** The only way to open the Places drawer. */
export const LocationButton = forwardRef<HTMLButtonElement, Props>(function LocationButton(
  { place, open, onClick },
  ref,
) {
  const districts = useDistricts()
  const district = districts.data?.find((d) => d.id === place)
  return (
    <button
      ref={ref}
      type="button"
      onClick={onClick}
      aria-haspopup="dialog"
      aria-expanded={open}
      aria-controls="places-drawer"
      aria-label={`Change place. Current place: ${district ? `${district.name}, ${district.state}` : place}`}
      className="focus-ring glass-card inline-flex min-h-touch items-center gap-2 rounded-full px-4 text-[14px] font-medium"
    >
      <MapPin aria-hidden className="h-4 w-4 text-ink-muted" />
      {districts.isLoading ? (
        <Skeleton className="h-4 w-28" />
      ) : (
        <span>
          {district ? (
            <>
              {district.name}
              <span className="text-ink-muted">, {district.state}</span>
            </>
          ) : (
            'Choose a place'
          )}
        </span>
      )}
      <ChevronDown aria-hidden className="h-4 w-4 text-ink-muted" />
    </button>
  )
})
