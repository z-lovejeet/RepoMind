import type { ReactNode } from "react";
import { AuthProvider as BaseAuthProvider } from "../../hooks/useAuth";

export function AuthProvider({ children }: { children: ReactNode }) {
  return <BaseAuthProvider>{children}</BaseAuthProvider>;
}

export default AuthProvider;
