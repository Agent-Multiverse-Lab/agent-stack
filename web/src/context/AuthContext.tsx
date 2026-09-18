import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";

import { getCurrentUser, loginUser, registerUser } from "@/api/auth";
import {
  clearAccessToken,
  getAccessToken,
  saveAccessToken,
} from "@/api/session";
import type { LoginRequest, RegisterRequest, UserResponse } from "@/types/auth";

interface AuthState {
  accessToken: string | null;
  user: UserResponse | null;
  login: (payload: LoginRequest) => Promise<void>;
  register: (payload: RegisterRequest) => Promise<UserResponse>;
  logout: () => void;
  restore: () => Promise<boolean>;
}

const AuthContext = createContext<AuthState | null>(null);

const isExpired = (token: string) => {
  try {
    const payload = JSON.parse(
      atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")),
    ) as { exp?: unknown };
    return typeof payload.exp === "number" && payload.exp * 1000 <= Date.now();
  } catch {
    return false;
  }
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(getAccessToken);
  const [user, setUser] = useState<UserResponse | null>(null);
  const tokenRef = useRef(accessToken);
  const userRef = useRef(user);
  const validatedToken = useRef<string | null>(null);
  const restorePromise = useRef<Promise<boolean> | null>(null);

  const logout = useCallback(() => {
    tokenRef.current = null;
    userRef.current = null;
    validatedToken.current = null;
    setAccessToken(null);
    setUser(null);
    clearAccessToken();
  }, []);

  const restore = useCallback(async () => {
    const token = tokenRef.current;
    if (!token) return false;
    if (isExpired(token)) {
      logout();
      return false;
    }
    if (validatedToken.current === token && userRef.current) return true;
    if (restorePromise.current) return restorePromise.current;

    const request = (async () => {
      try {
        const currentUser = await getCurrentUser();
        if (tokenRef.current !== token) return false;
        userRef.current = currentUser;
        setUser(currentUser);
        validatedToken.current = token;
        return true;
      } catch {
        if (tokenRef.current === token) logout();
        return false;
      }
    })();
    restorePromise.current = request;
    try {
      return await request;
    } finally {
      if (restorePromise.current === request) restorePromise.current = null;
    }
  }, [logout]);

  const login = useCallback(async (payload: LoginRequest) => {
    const response = await loginUser(payload);
    tokenRef.current = response.access_token;
    userRef.current = response.user;
    validatedToken.current = response.access_token;
    saveAccessToken(response.access_token);
    setAccessToken(response.access_token);
    setUser(response.user);
  }, []);

  const value = useMemo(
    () => ({
      accessToken,
      user,
      login,
      register: registerUser,
      logout,
      restore,
    }),
    [accessToken, user, login, logout, restore],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("AuthProvider is missing");
  return context;
}
