import { Navigate, Route, Routes, useLocation } from 'react-router'

import { AppShell } from './components/shell/AppShell'
import { AirPage } from './pages/AirPage'
import { Placeholder } from './pages/Placeholder'

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
        <Route
          path="temperature"
          element={<Placeholder title="Temperature" phase={6} note="Temperature trend, 10-day forecast, sun and UV cards." />}
        />
        <Route
          path="heat"
          element={<Placeholder title="Heat" phase={7} note="Humid-heat level, safe work hours and tips." />}
        />
        <Route
          path="finder"
          element={<Placeholder title="Maps and Finder" phase={10} note="Cleaner-air and cooler-places finder with routes." />}
        />
        <Route
          path="ask"
          element={<Placeholder title="Ask VayuKavach" phase={11} note="Questions answered only from VayuKavach's data." />}
        />
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
