import { useAuth } from "./features/auth/AuthContext";
import LoginPage from "./features/auth/LoginPage";
import DashboardPage from "./features/dashboard/DashboardPage";


function ApplicationLoader() {
  return (
    <main className="application-loader">
      <div className="application-loader-mark">
        IO
      </div>

      <p>
        Restoring your secure workspace…
      </p>

      <div className="application-loader-track">
        <span />
      </div>
    </main>
  );
}


export default function App() {
  const {
    isAuthenticated,
    isInitializing,
  } = useAuth();

  if (isInitializing) {
    return <ApplicationLoader />;
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return <DashboardPage />;
}