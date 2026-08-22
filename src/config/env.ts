import { z } from "zod";

const envSchema = z.object({
  SUPABASE_URL: z.string().url().optional(),
  SUPABASE_PUBLISHABLE_KEY: z.string().min(1).optional(),
  SUPABASE_SECRET_KEY: z.string().min(1).optional(),
  SUPABASE_JWKS_URL: z.string().url().optional(),
  SUPABASE_INTERNAL_INGESTION_KEY: z.string().min(24).optional(),
});

export function readBackendEnv() {
  return envSchema.parse(process.env);
}

export function getRequiredEnv(name: keyof z.infer<typeof envSchema>): string {
  const value = readBackendEnv()[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}
