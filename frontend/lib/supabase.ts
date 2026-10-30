/* NOVA — Supabase Browser Client */

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// These two variables MUST be set at runtime (browser). They are safe for the
// browser because they are the public anon / publishable key:
//   NEXT_PUBLIC_SUPABASE_URL              — Your Supabase project URL
//   NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY  — Your Supabase anon / publishable key
//
// Set them in .env.local for local development and in the Vercel project
// settings for production. Never use the service-role key here.

function createSupabaseClient(): SupabaseClient {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

  if (!url || !key) {
    throw new Error(
      "[NOVA] Missing Supabase environment variables.\n" +
      "Please set NEXT_PUBLIC_SUPABASE_URL and " +
      "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY in your .env.local (local) " +
      "or Vercel project settings (production)."
    );
  }

  return createClient(url, key);
}

// Lazily initialised singleton — the client is only created when first accessed
// at runtime, not during Next.js module evaluation / static analysis.
let _supabase: SupabaseClient | null = null;

export function getSupabaseClient(): SupabaseClient {
  if (!_supabase) {
    _supabase = createSupabaseClient();
  }
  return _supabase;
}

// Convenience named export for the common import pattern used in auth.tsx.
// Re-uses the same singleton.
export const supabase = new Proxy({} as SupabaseClient, {
  get(_target, prop) {
    return (getSupabaseClient() as unknown as Record<string | symbol, unknown>)[prop];
  },
});
