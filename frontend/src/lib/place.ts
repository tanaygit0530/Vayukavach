import { useCallback, useEffect } from 'react'
import { useSearchParams } from 'react-router'

export const DEFAULT_PLACE = 'delhi'
export const STORAGE_KEY = 'vayukavach.place'

export function readStoredPlace(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY)
  } catch {
    return null // private mode or blocked storage
  }
}

function storePlace(place: string) {
  try {
    window.localStorage.setItem(STORAGE_KEY, place)
  } catch {
    /* ignore: the URL still carries the place */
  }
}

const SLUG = /^[a-z0-9-]{2,64}$/

/** Selected district: ?place= in the URL wins, then localStorage, then Delhi. */
export function usePlace(): [string, (place: string) => void] {
  const [params, setParams] = useSearchParams()
  const fromUrl = params.get('place')?.toLowerCase() ?? null
  const place =
    (fromUrl && SLUG.test(fromUrl) ? fromUrl : null) ?? readStoredPlace() ?? DEFAULT_PLACE

  useEffect(() => {
    storePlace(place)
    if (fromUrl !== place) {
      const next = new URLSearchParams(params)
      next.set('place', place)
      setParams(next, { replace: true })
    }
  }, [place, fromUrl, params, setParams])

  const setPlace = useCallback(
    (next: string) => {
      storePlace(next)
      const updated = new URLSearchParams(params)
      updated.set('place', next)
      setParams(updated)
    },
    [params, setParams],
  )

  return [place, setPlace]
}
