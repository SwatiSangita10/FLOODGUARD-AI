import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './App.css'
import AppShell from './components/AppShell'
import AssistantPage from './pages/AssistantPage'
import AlertDetailPage from './pages/AlertDetailPage'
import AlertsPage from './pages/AlertsPage'
import OverviewPage from './pages/OverviewPage'
import ReportsPage from './pages/ReportsPage'
import ResourcesPage from './pages/ResourcesPage'
import RiskPage from './pages/RiskPage'
import RoutesPage from './pages/RoutesPage'
import SettingsPage from './pages/SettingsPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<OverviewPage />} />
          <Route path="resources" element={<ResourcesPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="alerts/:alertId" element={<AlertDetailPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="routes" element={<RoutesPage />} />
          <Route path="risk" element={<RiskPage />} />
          <Route path="assistant" element={<AssistantPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
