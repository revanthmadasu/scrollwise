import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AdminProtectedRoute } from "./components/AdminProtectedRoute";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";
import { AdminLoginPage } from "./pages/AdminLoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { FeedPage } from "./pages/FeedPage";
import { DiscoverPage } from "./pages/DiscoverPage";
import { InterestsPage } from "./pages/InterestsPage";
import { ProgressPage } from "./pages/ProgressPage";
import { WaitlistPage } from "./pages/WaitlistPage";
import { TemplateShowcase } from "./pages/TemplateShowcase";
import { TemplateBuilderPage } from "./pages/TemplateBuilderPage";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/waitlist" element={<WaitlistPage />} />
          <Route path="/templates" element={<TemplateShowcase />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/admin/login" element={<AdminLoginPage />} />

          {/* Consumer app shell */}
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<FeedPage />} />
            <Route path="/discover" element={<DiscoverPage />} />
            <Route path="/interests" element={<InterestsPage />} />
            <Route path="/progress" element={<ProgressPage />} />
          </Route>

          {/* Admin shell — guarded by admin role, its own login flow */}
          <Route
            element={
              <AdminProtectedRoute>
                <Layout />
              </AdminProtectedRoute>
            }
          >
            <Route path="/admin/templates" element={<TemplateBuilderPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
