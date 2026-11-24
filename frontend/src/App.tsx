import { Navigate, Route, Routes, useLocation } from 'react-router'

import { AppShell } from './components/shell/AppShell'
import { AirPage } from './pages/AirPage'
import { AskPage } from './pages/AskPage'
import { FinderPage } from './pages/FinderPage'
import { HeatPage } from './pages/HeatPage'
import { Placeholder } from './pages/Placeholder'
import { TemperaturePage } from './pages/TemperaturePage'

function RedirectKeepingQuery({ to }: { to: string }) {
  const { search } = useLocation()
  return <Navigate to={{ pathname: to, search }} replace />
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<RedirectKeepingQuery to="/air" />} />
        <Route path="air" element={<AirPage />} />
        <Route path="temperature" element={<TemperaturePage />} />
        <Route path="heat" element={<HeatPage />} />
        <Route path="finder" element={<FinderPage />} />
        <Route path="ask" element={<AskPage />} />
        <Route
          path="alerts"
          element={<Placeholder title="Alerts" phase={12} note="Telegram alerts for AQI and heat." />}
        />
        <Route
          path="profile"
          element={<Placeholder title="Profile" phase={12} note="Language and saved places." />}
        />
        <Route path="*" element={<RedirectKeepingQuery to="/air" />} />
      </Route>
    </Routes>
  )
}
