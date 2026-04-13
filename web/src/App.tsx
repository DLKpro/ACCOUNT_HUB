import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuthStore } from "@/stores/auth-store";
import { AuthGuard } from "@/components/layout/auth-guard";
import { AppLayout } from "@/components/layout/app-layout";
import LoginPage from "@/pages/login";
import RegisterPage from "@/pages/register";
import DashboardPage from "@/pages/dashboard";
import EmailsPage from "@/pages/emails";
import ScanPage from "@/pages/scan";
import ScanDetailPage from "@/pages/scan-detail";
import ClosuresPage from "@/pages/closures";
import styles from "./App.module.css";

export default function App() {
  const hydrate = useAuthStore((s) => s.hydrate);
  const isLoading = useAuthStore((s) => s.isLoading);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  if (isLoading) {
    return (
      <div className={styles.loading}>
        <div className={styles.wordmark}>
          <span className={styles.wordmarkLight}>account</span>
          <span className={styles.wordmarkBold}>hub</span>
        </div>
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<AuthGuard><AppLayout /></AuthGuard>}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/emails" element={<EmailsPage />} />
        <Route path="/scan" element={<ScanPage />} />
        <Route path="/scan/:sessionId" element={<ScanDetailPage />} />
        <Route path="/closures" element={<ClosuresPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
