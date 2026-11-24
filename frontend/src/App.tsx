import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router'

import { AppShell } from './components/shell/AppShell'
import { LoadingText } from './components/ui/Skeleton'
import { AirPage } from './pages/AirPage'
import { Placeholder } from './pages/Placeholder'

// The Air tab is the landing page and ships in the main bundle; the other tabs load on demand
// so phones download and parse less before the first screen is usable.
const TemperaturePage = lazy(() => import('./pages/TemperaturePage').then((m) => ({ default: m.TemperaturePage })))
const HeatPage = lazy(() => import('./pages/HeatPage').then((m) => ({ default: m.HeatPage })))
const FinderPage = lazy(() => import('./pages/FinderPage').then((m) => ({ default: m.FinderPage })))
const AskPage = lazy(() => import('./pages/AskPage').then((m) => ({ default: m.AskPage })))
const AlertsPage = lazy(() => import('./pages/AlertsPage').then((m) => ({ default: m.AlertsPage })))
const ReportsPage = lazy(() => import('./pages/ReportsPage').then((m) => ({ default: m.ReportsPage })))

function RedirectKeepingQuery({ to }: { to: string }) {
  const { search } = useLocation()
  return <Navigate to={{ pathname: to, search }} replace />
}

const page = (node: ReactNode) => <Suspense fallback={<LoadingText label="Loading" />}>{node}</Suspense>

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<RedirectKeepingQuery to="/air" />} />
        <Route path="air" element={<AirPage />} />
        <Route path="temperature" element={page(<TemperaturePage />)} />
        <Route path="heat" element={page(<HeatPage />)} />
        <Route path="finder" element={page(<FinderPage />)} />
        <Route path="ask" element={page(<AskPage />)} />
        <Route path="alerts" element={page(<AlertsPage />)} />
        <Route path="reports" element={page(<ReportsPage />)} />
        <Route
          path="profile"
          element={<Placeholder title="Profile" phase={12} note="Language and saved places." />}
        />
        <Route path="*" element={<RedirectKeepingQuery to="/air" />} />
      </Route>
    </Routes>
  )
}
