import { NextResponse } from "next/server";
import { ZodError } from "zod";

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export function ok<T>(data: T, status = 200) {
  return NextResponse.json(data, { status });
}

export function apiError(code: string, message: string, status = 400, details?: unknown) {
  return NextResponse.json<ApiErrorBody>({ error: { code, message, details } }, { status });
}

export function validationError(error: ZodError) {
  return apiError("VALIDATION_ERROR", "Request validation failed", 400, error.flatten());
}

export function supabaseError(error: { message: string; code?: string } | null, fallback = "Database request failed") {
  return apiError(error?.code ?? "SUPABASE_ERROR", error?.message ?? fallback, 500);
}
