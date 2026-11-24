import clsx from 'clsx'
import { useCallback, useRef, useState } from 'react'
import { Outlet, useLocation } from 'react-router'

import { usePlace } from '../../lib/place'
import { Header } from './Header'
import { IconRail } from './IconRail'
import { PlacesDrawer } from './PlacesDrawer'

export interface ShellContext {
  place: string
}

const BACKGROUNDS: Record<string, string> = {
  '/air': 'clouds-bg',
  '/temperature': 'clouds-bg',
  '/ask': 'clouds-bg',
  '/alerts': 'clouds-bg',
  '/reports': 'clouds-bg',
  '/profile': 'clouds-bg',
  '/finder': 'clouds-bg',
  '/heat': 'heat-bg',
}

export function AppShell() {
  const [place, setPlace] = usePlace()
  const [open, setOpen] = useState(false)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const { pathname } = useLocation()

  const close = useCallback(() => {
    setOpen(false)
    buttonRef.current?.focus()
  }, [])

  return (
    <div className={clsx('min-h-full p-3 md:p-4', BACKGROUNDS[pathname] ?? 'bg-page')}>
      <a
        href="#main"
        className="focus-ring sr-only z-50 rounded-full bg-white px-4 py-2 focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Skip to content
      </a>
      <div className="mx-auto flex min-h-[calc(100vh-24px)] max-w-[1600px] gap-4 md:h-[calc(100vh-32px)]">
        <IconRail place={place} />
        <div className="flex min-w-0 flex-1 flex-col gap-4 pb-[84px] md:overflow-y-auto md:pb-0">
          <Header ref={buttonRef} place={place} drawerOpen={open} onOpenPlaces={() => setOpen(true)} />
          <main id="main" className="flex-1">
            <Outlet context={{ place } satisfies ShellContext} />
          </main>
          <footer className={clsx('pb-1 text-[11px]', pathname === '/heat' ? 'text-white/85' : 'text-ink-muted')}>
            Data: CPCB via data.gov.in · OpenAQ · Open-Meteo and CAMS (CC BY 4.0) · Map ©
            OpenStreetMap contributors
          </footer>
        </div>
      </div>
      <PlacesDrawer open={open} place={place} onClose={close} onChoose={setPlace} />
    </div>
  )
}
