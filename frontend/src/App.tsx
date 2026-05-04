import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { ProtectedRoute } from "@/auth/ProtectedRoute";
import { Layout } from "@/components/Layout";
import { AdminPage } from "@/pages/AdminPage";
import { AuditPage } from "@/pages/AuditPage";
import { BacktestPage } from "@/pages/BacktestPage";
import { CoachPage } from "@/pages/CoachPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { DecisionsPage } from "@/pages/DecisionsPage";
import { LoginPage } from "@/pages/LoginPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { SignupPage } from "@/pages/SignupPage";
import { TradesPage } from "@/pages/TradesPage";
import { TuningPage } from "@/pages/TuningPage";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/decisions" element={<DecisionsPage />} />
            <Route path="/trades" element={<TradesPage />} />
            <Route path="/tuning" element={<TuningPage />} />
            <Route path="/coach" element={<CoachPage />} />
            <Route path="/backtest" element={<BacktestPage />} />
            <Route path="/audit" element={<AuditPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/admin" element={<AdminPage />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
