import type { NextRequest } from "next/server";
import { apiError, ok, supabaseError, validationError } from "@backend/api/responses";
import { createApiSupabaseContext } from "@backend/auth/supabase-context";
import { meterIngestionSchema } from "@backend/validation/schemas";

export async function ingestMeterReadings(req: NextRequest) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return apiError("VALIDATION_ERROR", "Malformed JSON body", 400);
  }

  const parsed = meterIngestionSchema.safeParse(body);
  if (!parsed.success) return validationError(parsed.error);

  const { ctx, response } = await createApiSupabaseContext(req, "secret");
  if (response) return response;

  const rows = parsed.data.readings.map((reading) => ({
    property_id: reading.propertyId,
    meter_id: reading.meterId ?? null,
    interval_start: reading.intervalStart,
    interval_end: reading.intervalEnd,
    consumption_kwh: reading.consumptionKwh,
    solar_generation_kwh: reading.solarGenerationKwh,
    grid_import_kwh: reading.gridImportKwh,
    grid_export_kwh: reading.gridExportKwh,
    battery_soc_pct: reading.batterySocPct ?? null,
    source: reading.source,
  }));

  const { data, error } = await ctx.supabaseAdmin
    .from("energy_readings")
    .upsert(rows, {
      onConflict: "property_id,meter_id,interval_start,interval_end,source",
      ignoreDuplicates: false,
    })
    .select("id, property_id, interval_start, interval_end");

  if (error) return supabaseError(error);
  return ok({ data, ingested: data?.length ?? 0 });
}
