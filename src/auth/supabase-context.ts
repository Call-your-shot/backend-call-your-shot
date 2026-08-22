import { createServerClient } from "@supabase/ssr";
import type { SupabaseContext, SupabaseEnv, AuthModeWithKey } from "@supabase/server";
import type { SupabaseClient } from "@supabase/supabase-js";
import {
  createAdminClient,
  createContextClient,
  extractCredentials,
  verifyCredentials,
} from "@supabase/server/core";
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { apiError } from "@backend/api/responses";
import { readBackendEnv } from "@backend/config/env";
import type { Database } from "@backend/db/database.types";

export type BackendSupabaseContext = Omit<SupabaseContext<Database>, "supabase" | "supabaseAdmin"> & {
  // Replace this with Supabase CLI generated types once a project is linked.
  // The migration is the source of truth; this keeps route handlers compiling before generation.
  supabase: SupabaseClient;
  supabaseAdmin: SupabaseClient;
};

function buildEnv(): Partial<SupabaseEnv> {
  const env = readBackendEnv();
  return {
    url: env.SUPABASE_URL,
    publishableKeys: env.SUPABASE_PUBLISHABLE_KEY ? { default: env.SUPABASE_PUBLISHABLE_KEY } : {},
    secretKeys: env.SUPABASE_SECRET_KEY ? { default: env.SUPABASE_SECRET_KEY } : {},
  };
}

async function tokenFromCookies() {
  const env = readBackendEnv();
  if (!env.SUPABASE_URL || !env.SUPABASE_PUBLISHABLE_KEY) return null;

  const cookieStore = await cookies();
  const client = createServerClient(env.SUPABASE_URL, env.SUPABASE_PUBLISHABLE_KEY, {
    cookies: {
      getAll: () => cookieStore.getAll(),
      setAll: (cookiesToSet) => {
        try {
          cookiesToSet.forEach(({ name, value, options }) => cookieStore.set(name, value, options));
        } catch {
          // Middleware handles refresh-cookie writes in framework contexts that allow it.
        }
      },
    },
  });

  const { data } = await client.auth.getSession();
  return data.session?.access_token ?? null;
}

export async function createApiSupabaseContext(
  request: NextRequest,
  auth: AuthModeWithKey | AuthModeWithKey[] = "user"
): Promise<{ ctx: BackendSupabaseContext; response: null } | { ctx: null; response: Response }> {
  const env = buildEnv();
  const credentials = extractCredentials(request);
  const token = credentials.token ?? (Array.isArray(auth) || auth === "user" ? await tokenFromCookies() : null);

  const { data, error } = await verifyCredentials({ token, apikey: credentials.apikey }, { auth, env });
  if (error) {
    return { ctx: null, response: apiError("AUTHENTICATION_ERROR", error.message, error.status) };
  }

  const ctx: BackendSupabaseContext = {
    supabase: createContextClient({ auth: { token: data.token, keyName: data.keyName }, env }),
    supabaseAdmin: createAdminClient({ env }),
    userClaims: data.userClaims,
    jwtClaims: data.jwtClaims,
    authMode: data.authMode,
  };

  return { ctx, response: null };
}

export function getUserId(ctx: BackendSupabaseContext) {
  const userId = ctx.userClaims?.id;
  if (!userId) throw new Error("Authenticated user id is unavailable");
  return userId;
}
