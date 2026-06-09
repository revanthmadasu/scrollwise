import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { FeedPage } from "./pages/FeedPage";
import { DiscoverPage } from "./pages/DiscoverPage";
import { InterestsPage } from "./pages/InterestsPage";
import { ProgressPage } from "./pages/ProgressPage";
import { WaitlistPage } from "./pages/WaitlistPage";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/waitlist" element={<WaitlistPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
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
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
