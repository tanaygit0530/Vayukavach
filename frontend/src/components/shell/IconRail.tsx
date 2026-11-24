import clsx from 'clsx'
import { NavLink } from 'react-router'

import { Logo } from './Logo'
import { FOOTER_NAV, MAIN_NAV, type NavItem } from './nav'

function RailLink({ item, place }: { item: NavItem; place: string }) {
  const Icon = item.icon
  return (
    <NavLink
      to={{ pathname: item.path, search: `?place=${place}` }}
      aria-label={item.label}
      title={item.label}
      className={({ isActive }) =>
        clsx(
          'focus-ring grid h-[44px] w-[44px] place-items-center rounded-full transition-colors',
          isActive ? 'bg-ink text-white' : 'text-ink-muted hover:bg-slate-100 hover:text-ink',
        )
      }
    >
      <Icon aria-hidden className="h-[20px] w-[20px]" strokeWidth={1.8} />
    </NavLink>
  )
}

/** 74 px icon rail on the left; a bottom bar under 768 px. */
export function IconRail({ place }: { place: string }) {
  return (
    <nav
      aria-label="Main"
      className={clsx(
        'glass-card z-30 flex items-center',
        // phones: bottom bar
        'fixed inset-x-3 bottom-3 h-[64px] justify-center gap-1 rounded-[22px] px-2',
        // tablet and up: left rail
        'md:static md:inset-auto md:h-full md:w-rail md:flex-col md:justify-start md:gap-0 md:rounded-card md:px-0 md:py-4',
      )}
    >
      <div className="hidden md:mb-4 md:block md:border-b md:border-slate-200 md:pb-4">
        <Logo />
      </div>
      <ul className="flex items-center gap-1 md:flex-col md:gap-3">
        {MAIN_NAV.map((item) => (
          <li key={item.path}>
            <RailLink item={item} place={place} />
          </li>
        ))}
      </ul>
      {/* phones: Alerts and Profile sit at the end of the same bar */}
      <ul className="flex items-center gap-1 md:mt-auto md:flex-col md:gap-3">
        {FOOTER_NAV.map((item) => (
          <li key={item.path}>
            <RailLink item={item} place={place} />
          </li>
        ))}
      </ul>
    </nav>
  )
}
