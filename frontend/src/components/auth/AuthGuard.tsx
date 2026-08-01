import { Navigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import Loader from "../ui/Loader";

interface AuthGuardProps {
  children: React.ReactNode;
}

export default function AuthGuard({ children }: AuthGuardProps) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="auth-guard-loading">
        <Loader size="lg" />
        <p>Loading...</p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
