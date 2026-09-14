import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { apiRequest, ApiError } from "./api";


export interface CurrentUser {
  id: string;
  email: string;
  full_name: string;
}

interface AuthContextValue {
  user: CurrentUser | null;
  loading: boolean;
  refetch: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchMe = async () => {
    try {
      const me = await apiRequest<CurrentUser>("/auth/me");
      setUser(me);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 404)) {
        setUser(null);
      } else {
        throw err;
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchMe();
  }, []);

  const logout = async () => {
    await apiRequest("/auth/logout", { method: "POST" });
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, refetch: fetchMe, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components -- context + provider + hook belong together
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
