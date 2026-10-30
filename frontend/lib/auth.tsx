/* NOVA — Authentication via Supabase Auth */

"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "./supabase";

// ── Types ────────────────────────────────────────────────────────────────────

/**
 * Normalised user object exposed throughout the app.
 * `name` is sourced from `user_metadata.full_name` set at sign-up.
 * `created_at` is the Supabase account creation timestamp.
 */
export interface AuthUser {
  id: string;
  name: string;
  email: string;
  created_at: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Convert a Supabase session's user to the app's AuthUser shape. */
function sessionToUser(session: Session): AuthUser {
  const su = session.user;
  return {
    id: su.id,
    // full_name is stored in user_metadata during signUp
    name:
      (su.user_metadata?.full_name as string | undefined) ||
      su.email?.split("@")[0] ||
      "User",
    email: su.email ?? "",
    created_at: su.created_at ?? "",
  };
}

// ── Context ──────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // 1. Subscribe to future session changes first so we don't miss any events
    //    that arrive while the initial getSession() call is in-flight.
    const { data: listener } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setUser(session ? sessionToUser(session) : null);
        setIsLoading(false);
      }
    );

    // 2. Hydrate the initial session. onAuthStateChange will NOT fire for an
    //    already-existing session on first load, so we read it explicitly.
    supabase.auth.getSession().then(({ data }) => {
      setUser(data.session ? sessionToUser(data.session) : null);
      setIsLoading(false);
    });

    return () => {
      listener.subscription.unsubscribe();
    };
  }, []);

  /**
   * Manually re-read the current session. Exposed on the context so callers
   * can force a re-sync (e.g. after an email confirmation redirect).
   */
  const refresh = useCallback(async () => {
    const { data } = await supabase.auth.getSession();
    setUser(data.session ? sessionToUser(data.session) : null);
    setIsLoading(false);
  }, []);

  /**
   * Sign in with email and password.
   * Throws a human-readable Error on failure so the login page can display it.
   */
  const login = useCallback(async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (error) throw new Error(error.message);
    if (data.session) setUser(sessionToUser(data.session));
  }, []);

  /**
   * Create a new account and sign in.
   * `name` is stored as `full_name` in user_metadata so it survives sessions.
   *
   * NOTE: If Supabase email confirmation is enabled (recommended for
   * production), the user must confirm their email before they can sign in.
   * In that case `data.session` will be null and we throw a sentinel string
   * so the login page can display a friendly confirmation message.
   */
  const register = useCallback(
    async (name: string, email: string, password: string) => {
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: { data: { full_name: name.trim() } },
      });
      if (error) throw new Error(error.message);

      if (data.session) {
        // Auto-confirmed (email confirmation disabled in Supabase dashboard)
        setUser(sessionToUser(data.session));
      } else {
        // Email confirmation required — use a sentinel so login/page.tsx can
        // render an info banner instead of a red error.
        throw new Error("__CONFIRM_EMAIL__");
      }
    },
    []
  );

  /**
   * Sign out and clear local user state.
   */
  const logout = useCallback(async () => {
    await supabase.auth.signOut();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, isLoading, login, register, logout, refresh }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
