import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { setAccessToken, setSessionLostHandler } from '../services/apiClient.js';
import * as authService from '../services/authService.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [booting, setBooting] = useState(true);

  const clear = useCallback(() => {
    setAccessToken(null);
    setSession(null);
  }, []);

  useEffect(() => {
    setSessionLostHandler(() => setSession(null));
    return () => setSessionLostHandler(null);
  }, []);

  // On cold start the access token is gone (it only ever lived in memory), so
  // the HttpOnly refresh cookie is what restores the session.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const restored = await authService.restoreSession();
        if (!cancelled) setSession(restored);
      } catch {
        if (!cancelled) setSession(null);
      } finally {
        if (!cancelled) setBooting(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (identifier, password) => {
    const next = await authService.login(identifier, password);
    setSession(next);
    return next;
  }, []);

  const signUp = useCallback(async (details) => {
    const next = await authService.register(details);
    setSession(next);
    return next;
  }, []);

  const signOut = useCallback(async () => {
    try {
      await authService.logout();
    } finally {
      clear();
    }
  }, [clear]);

  const refreshUser = useCallback(async () => {
    const next = await authService.me();
    setSession(next);
    return next;
  }, []);

  const value = useMemo(
    () => ({
      session,
      user: session?.user ?? null,
      workspace: session?.workspace ?? null,
      timezone: session?.workspace?.timezone ?? 'UTC',
      isAuthenticated: Boolean(session?.user),
      isAdmin: session?.user?.role === 'ADMIN',
      mustChangePassword: Boolean(session?.user?.must_change_password),
      booting,
      signIn,
      signUp,
      signOut,
      refreshUser,
    }),
    [session, booting, signIn, signUp, signOut, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>');
  return context;
}
