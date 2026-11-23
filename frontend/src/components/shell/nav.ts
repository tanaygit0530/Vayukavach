import { Bell, Flame, Map, MessageCircle, Thermometer, UserRound, Wind, type LucideIcon } from 'lucide-react'

export interface NavItem {
  path: string
  label: string
  icon: LucideIcon
}

export const MAIN_NAV: NavItem[] = [
  { path: '/air', label: 'Air quality', icon: Wind },
  { path: '/temperature', label: 'Temperature', icon: Thermometer },
  { path: '/heat', label: 'Heat', icon: Flame },
  { path: '/finder', label: 'Maps and Finder', icon: Map },
  { path: '/ask', label: 'Ask VayuKavach', icon: MessageCircle },
]

export const FOOTER_NAV: NavItem[] = [
  { path: '/alerts', label: 'Alerts', icon: Bell },
  { path: '/profile', label: 'Profile', icon: UserRound },
]
