import type { NextRequest } from "next/server";
import type { SupabaseClient } from "@supabase/supabase-js";
import { ZodError, type ZodType } from "zod";
import { apiError, ok, supabaseError, validationError } from "@backend/api/responses";
import {
  createApiSupabaseContext,
  createLocalDemoReadContext,
  getUserId,
  type BackendSupabaseContext,
} from "@backend/auth/supabase-context";
import type { Database, ManagementRole, PropertyRole } from "@backend/db/database.types";
import {
  contractInputSchema,
  controlCommandSchema,
  controlSettingsSchema,
  energyReadingInputSchema,
  leaseRequestInputSchema,
  leaseRequestPatchSchema,
  paginationQuerySchema,
  periodQuerySchema,
  priceAdjustmentInputSchema,
  priceAdjustmentPatchSchema,
  proposalInputSchema,
  proposalPatchSchema,
  solarAssessmentInputSchema,
  tariffInputSchema,
  uuidSchema,
} from "@backend/validation/schemas";
import { estimateSolar } from "@backend/services/solar-estimator";
import { MockEnergyControlProvider } from "@mock/backend/providers/controls/mock-energy-control-provider";

type Client = SupabaseClient;

interface DashboardReading {
  consumption_kwh: number | string;
  solar_generation_kwh: number | string;
  grid_import_kwh: number | string;
  grid_export_kwh: number | string;
  battery_soc_pct: number | string | null;
}

async function parseJson<T>(req: NextRequest, schema: ZodType<T>): Promise<{ data: T; response: null } | { data: null; response: Response }> {
  try {
    const body = await req.json();
    return { data: schema.parse(body), response: null };
  } catch (error) {
    if (error instanceof ZodError) return { data: null, response: validationError(error) };
    return { data: null, response: apiError("VALIDATION_ERROR", "Malformed JSON body", 400) };
  }
}

function queryParams(req: NextRequest) {
  return Object.fromEntries(req.nextUrl.searchParams.entries());
}

async function viewerRole(client: Client, propertyId: string, userId: string): Promise<PropertyRole | null> {
  const { data, error } = await client
    .from("property_memberships")
    .select("role")
    .eq("property_id", propertyId)
    .eq("user_id", userId)
    .eq("status", "active")
    .maybeSingle();
  if (error) throw new Error(error.message);
  return (data as { role?: PropertyRole } | null)?.role ?? null;
}

async function requireContext(req: NextRequest) {
  return createApiSupabaseContext(req, "user");
}

async function requirePropertyAccess(ctx: BackendSupabaseContext, propertyId: string, roles?: ManagementRole[]) {
  const userId = getUserId(ctx);
  const role = await viewerRole(ctx.supabase, propertyId, userId);
  if (!role) return { role: null, response: apiError("FORBIDDEN", "You do not have access to this property", 403) };
  if (roles && !roles.includes(role as ManagementRole)) {
    return { role, response: apiError("FORBIDDEN", "Your property role cannot perform this action", 403) };
  }
  return { role, response: null };
}

export async function getMe(req: NextRequest) {
  const { ctx, response } = await requireContext(req);
  if (response) return response;
  const userId = getUserId(ctx);
  const { data: profile, error } = await ctx.supabase.from("profiles").select("*").eq("id", userId).maybeSingle();
  if (error) return supabaseError(error);
  const { data: memberships, error: membershipError } = await ctx.supabase
    .from("property_memberships")
    .select("*, properties(*)")
    .eq("user_id", userId)
    .eq("status", "active");
  if (membershipError) return supabaseError(membershipError);
  return ok({ user: ctx.userClaims, profile, memberships });
}

export async function listProperties(req: NextRequest) {
  const { ctx, response } = await requireContext(req);
  const readCtx = ctx ?? createLocalDemoReadContext();
  if (!readCtx) return response ?? apiError("AUTHENTICATION_ERROR", "Authentication is required", 401);

  const { data, error } = await readCtx.supabase.from("properties").select("*, property_memberships(*)").order("created_at");
  if (error) return supabaseError(error);
  return ok({ data, mode: ctx ? "user" : "local_demo_admin_read" });
}

export async function getProperty(req: NextRequest, propertyId: string) {
  const id = uuidSchema.safeParse(propertyId);
  if (!id.success) return validationError(id.error);
  const { ctx, response } = await requireContext(req);
  const readCtx = ctx ?? createLocalDemoReadContext();
  if (!readCtx) return response ?? apiError("AUTHENTICATION_ERROR", "Authentication is required", 401);

  const access = ctx
    ? await requirePropertyAccess(ctx, id.data)
    : { role: "landlord" as const, response: null };
  if (access.response) return access.response;
  const { data, error } = await readCtx.supabase.from("properties").select("*").eq("id", id.data).single();
  if (error) return supabaseError(error);
  return ok({ data, viewer: { role: access.role } });
}

export async function getDashboard(req: NextRequest, propertyId: string) {
  const id = uuidSchema.safeParse(propertyId);
  if (!id.success) return validationError(id.error);
  const period = periodQuerySchema.safeParse(queryParams(req));
  if (!period.success) return validationError(period.error);

  const { ctx, response } = await requireContext(req);
  const readCtx = ctx ?? createLocalDemoReadContext();
  if (!readCtx) return response ?? apiError("AUTHENTICATION_ERROR", "Authentication is required", 401);

  const access = ctx
    ? await requirePropertyAccess(ctx, id.data)
    : { role: "landlord" as const, response: null };
  if (access.response) return access.response;

  const to = new Date(period.data.to ?? new Date().toISOString());
  const from = new Date(period.data.from ?? new Date(to.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString());
  const { data: property, error: propertyError } = await readCtx.supabase.from("properties").select("*").eq("id", id.data).single();
  if (propertyError) return supabaseError(propertyError);

  const { data: readings, error: readingError } = await readCtx.supabase
    .from("energy_readings")
    .select("*")
    .eq("property_id", id.data)
    .gte("interval_start", from.toISOString())
    .lt("interval_start", to.toISOString())
    .order("interval_start");
  if (readingError) return supabaseError(readingError);

  const dashboardReadings = (readings ?? []) as DashboardReading[];
  const totals = dashboardReadings.reduce(
    (acc, reading) => {
      acc.consumptionKwh += Number(reading.consumption_kwh);
      acc.solarGenerationKwh += Number(reading.solar_generation_kwh);
      acc.gridImportKwh += Number(reading.grid_import_kwh);
      acc.gridExportKwh += Number(reading.grid_export_kwh);
      if (reading.battery_soc_pct != null) acc.batterySocPct = Number(reading.battery_soc_pct);
      return acc;
    },
    { consumptionKwh: 0, solarGenerationKwh: 0, gridImportKwh: 0, gridExportKwh: 0, batterySocPct: null as number | null }
  );

  const { data: tariff } = await readCtx.supabase
    .from("energy_tariffs")
    .select("*")
    .eq("property_id", id.data)
    .lte("valid_from", to.toISOString())
    .or(`valid_to.is.null,valid_to.gt.${from.toISOString()}`)
    .order("valid_from", { ascending: false })
    .limit(1)
    .maybeSingle();

  const gridRatePerKwh = tariff
    ? Number(tariff.grid_rate_cents_per_kwh ?? Number(tariff.usage_rate_per_kwh) * 100) / 100
    : 0;
  const estimatedCost = tariff
    ? Math.round((totals.gridImportKwh * gridRatePerKwh - totals.gridExportKwh * Number(tariff.feed_in_rate_per_kwh)) * 100) / 100
    : 0;
  const estimatedSavings = tariff
    ? Math.round((Math.max(0, totals.solarGenerationKwh - totals.gridExportKwh) * gridRatePerKwh + totals.gridExportKwh * Number(tariff.feed_in_rate_per_kwh)) * 100) / 100
    : 0;

  const base = {
    property,
    viewer: { role: access.role, mode: ctx ? "user" : "local_demo_admin_read" },
    period: { from: from.toISOString(), to: to.toISOString(), granularity: period.data.granularity },
    energy: totals,
    financial: { estimatedCost, estimatedSavings, currency: tariff?.currency ?? "AUD" },
    sustainability: { carbonAvoidedKg: Math.round(totals.solarGenerationKwh * 0.68 * 100) / 100 },
    units: { energy: "kWh", currency: tariff?.currency ?? "AUD", carbon: "kgCO2e" },
    series: readings ?? [],
  };

  if (access.role === "tenant") return ok(base);

  const [{ data: solarAssessment }, { data: pendingPriceAdjustments }, { data: pendingLeaseRequests }] = await Promise.all([
    readCtx.supabase.from("solar_assessments").select("*").eq("property_id", id.data).order("created_at", { ascending: false }).limit(1).maybeSingle(),
    readCtx.supabase.from("price_adjustments").select("*").eq("property_id", id.data).in("status", ["draft", "pending"]),
    readCtx.supabase.from("lease_requests").select("*").eq("property_id", id.data).in("status", ["submitted", "under_review"]),
  ]);

  return ok({ ...base, roi: solarAssessment?.estimated_roi_pct ?? null, solarAssessment, currentTariff: tariff, pendingPriceAdjustments, pendingLeaseRequests });
}

export async function listTable(req: NextRequest, propertyId: string, table: keyof Database["public"]["Tables"]) {
  const id = uuidSchema.safeParse(propertyId);
  if (!id.success) return validationError(id.error);
  const { ctx, response } = await requireContext(req);
  if (response) return response;
  const access = await requirePropertyAccess(ctx, id.data);
  if (access.response) return access.response;
  const { data, error } = await ctx.supabase.from(table).select("*").eq("property_id", id.data).order("created_at", { ascending: false });
  if (error) return supabaseError(error);
  return ok({ data });
}

export async function listEnergyReadings(req: NextRequest, propertyId: string) {
  const id = uuidSchema.safeParse(propertyId);
  if (!id.success) return validationError(id.error);
  const query = paginationQuerySchema.safeParse(queryParams(req));
  if (!query.success) return validationError(query.error);
  const { ctx, response } = await requireContext(req);
  if (response) return response;
  const access = await requirePropertyAccess(ctx, id.data);
  if (access.response) return access.response;
  let builder = ctx.supabase.from("energy_readings").select("*").eq("property_id", id.data).order("interval_start", { ascending: false }).limit(query.data.limit);
  if (query.data.from) builder = builder.gte("interval_start", query.data.from);
  if (query.data.to) builder = builder.lt("interval_start", query.data.to);
  if (query.data.cursor) builder = builder.lt("interval_start", query.data.cursor);
  const { data, error } = await builder;
  if (error) return supabaseError(error);
  return ok({ data, nextCursor: data?.at(-1)?.interval_start ?? null });
}

export async function createEnergyReading(req: NextRequest, propertyId: string) {
  const id = uuidSchema.safeParse(propertyId);
  if (!id.success) return validationError(id.error);
  const parsed = await parseJson(req, energyReadingInputSchema);
  if (parsed.response) return parsed.response;
  const { ctx, response } = await requireContext(req);
  if (response) return response;
  const access = await requirePropertyAccess(ctx, id.data, ["landlord", "agent"]);
  if (access.response) return access.response;
  const input = parsed.data;
  const { data, error } = await ctx.supabase.from("energy_readings").insert({
    property_id: id.data,
    meter_id: input.meterId ?? null,
    interval_start: input.intervalStart,
    interval_end: input.intervalEnd,
    consumption_kwh: input.consumptionKwh,
    solar_generation_kwh: input.solarGenerationKwh,
    solar_consumed_by_tenant_kwh: input.solarConsumedByTenantKwh ?? null,
    grid_import_kwh: input.gridImportKwh,
    grid_export_kwh: input.gridExportKwh,
    battery_charge_kwh: input.batteryChargeKwh,
    battery_discharge_kwh: input.batteryDischargeKwh,
    battery_soc_pct: input.batterySocPct ?? null,
    source: input.source,
    finalized_at: input.finalizedAt ?? null,
  }).select("*").single();
  if (error) return supabaseError(error);
  return ok({ data }, 201);
}

export async function createTariff(req: NextRequest, propertyId: string) {
  const parsed = await parseJson(req, tariffInputSchema);
  if (parsed.response) return parsed.response;
  const { ctx, response } = await requireContext(req);
  if (response) return response;
  const access = await requirePropertyAccess(ctx, propertyId, ["landlord", "agent"]);
  if (access.response) return access.response;
  const input = parsed.data;
  const { data, error } = await ctx.supabase.from("energy_tariffs").insert({
    property_id: propertyId,
    name: input.name,
    usage_rate_per_kwh: input.usageRatePerKwh,
    grid_rate_cents_per_kwh: input.gridRateCentsPerKwh ?? input.usageRatePerKwh * 100,
    feed_in_rate_per_kwh: input.feedInRatePerKwh,
    daily_supply_charge: input.dailySupplyCharge,
    currency: input.currency,
    valid_from: input.validFrom,
    valid_to: input.validTo ?? null,
    created_by: getUserId(ctx),
  }).select("*").single();
  if (error) return supabaseError(error);
  return ok({ data }, 201);
}

export async function createSolarAssessment(req: NextRequest, propertyId: string) {
  const parsed = await parseJson(req, solarAssessmentInputSchema);
  if (parsed.response) return parsed.response;
  const { ctx, response } = await requireContext(req);
  if (response) return response;
  const access = await requirePropertyAccess(ctx, propertyId, ["landlord", "agent"]);
  if (access.response) return access.response;
  const estimate = estimateSolar({
    roofAreaM2: parsed.data.roofAreaM2,
    usableRoofAreaM2: parsed.data.usableRoofAreaM2,
    assumptions: parsed.data.assumptions,
  });
  const { data, error } = await ctx.supabase.from("solar_assessments").insert({
    property_id: propertyId,
    image_path: parsed.data.imagePath ?? null,
    image_source: parsed.data.imageSource ?? null,
    roof_area_m2: parsed.data.roofAreaM2 ?? null,
    usable_roof_area_m2: estimate.usableRoofAreaM2,
    estimated_panel_count: estimate.estimatedPanelCount,
    estimated_system_kw: estimate.estimatedSystemKw,
    estimated_annual_generation_kwh: estimate.estimatedAnnualGenerationKwh,
    estimated_installation_cost: estimate.estimatedInstallationCost,
    estimated_annual_savings: estimate.estimatedAnnualSavings,
    estimated_payback_years: estimate.estimatedPaybackYears,
    estimated_roi_pct: estimate.estimatedRoiPct,
    estimated_carbon_reduction_kg_year: estimate.estimatedCarbonReductionKgYear,
    assumptions: estimate.assumptions,
    status: "completed",
    created_by: getUserId(ctx),
  }).select("*").single();
  if (error) return supabaseError(error);
  return ok({ data, label: "Estimate only" }, 201);
}

export async function createPriceAdjustment(req: NextRequest, propertyId: string) {
  const parsed = await parseJson(req, priceAdjustmentInputSchema);
  if (parsed.response) return parsed.response;
  const { ctx, response } = await requireContext(req);
  if (response) return response;
  const access = await requirePropertyAccess(ctx, propertyId, ["landlord", "agent"]);
  if (access.response) return access.response;
  const input = parsed.data;
  const { data, error } = await ctx.supabase.from("price_adjustments").insert({
    property_id: propertyId,
    previous_tariff_id: input.previousTariffId ?? null,
    proposed_usage_rate: input.proposedUsageRate ?? null,
    proposed_feed_in_rate: input.proposedFeedInRate ?? null,
    proposed_daily_charge: input.proposedDailyCharge ?? null,
    reason: input.reason ?? null,
    effective_from: input.effectiveFrom,
    status: input.status,
    created_by: getUserId(ctx),
  }).select("*").single();
  if (error) return supabaseError(error);
  return ok({ data }, 201);
}

export async function patchById(req: NextRequest, id: string, table: "price_adjustments" | "lease_requests" | "proposals") {
  const parsedId = uuidSchema.safeParse(id);
  if (!parsedId.success) return validationError(parsedId.error);
  const schema: ZodType<Record<string, unknown>> =
    table === "price_adjustments" ? priceAdjustmentPatchSchema : table === "lease_requests" ? leaseRequestPatchSchema : proposalPatchSchema;
  const parsed = await parseJson(req, schema);
  if (parsed.response) return parsed.response;
  const { ctx, response } = await requireContext(req);
  if (response) return response;
  const { data: existing, error: existingError } = await ctx.supabase.from(table).select("*").eq("id", parsedId.data).single();
  if (existingError) return supabaseError(existingError);
  const access = await requirePropertyAccess(ctx, existing.property_id, ["landlord", "agent"]);
  if (access.response) return access.response;

  const body = parsed.data as Record<string, unknown>;
  const update =
    table === "lease_requests"
      ? { status: body.status, review_notes: body.reviewNotes ?? null, reviewed_by: getUserId(ctx) }
      : table === "price_adjustments"
        ? { status: body.status, approved_by: ["approved", "applied"].includes(String(body.status)) ? getUserId(ctx) : null }
        : { status: body.status, terms: body.terms ?? existing.terms };

  const { data, error } = await ctx.supabase.from(table).update(update).eq("id", parsedId.data).select("*").single();
  if (error) return supabaseError(error);
  return ok({ data });
}

export async function createLeaseRequest(req: NextRequest, propertyId: string) {
  const parsed = await parseJson(req, leaseRequestInputSchema);
  if (parsed.response) return parsed.response;
  const { ctx, response } = await requireContext(req);
  if (response) return response;
  const access = await requirePropertyAccess(ctx, propertyId);
  if (access.response) return access.response;
  if (access.role !== "tenant") return apiError("FORBIDDEN", "Only tenants can submit lease requests", 403);
  const { data, error } = await ctx.supabase.from("lease_requests").insert({
    property_id: propertyId,
    tenant_user_id: getUserId(ctx),
    request_type: parsed.data.requestType,
    message: parsed.data.message,
  }).select("*").single();
  if (error) return supabaseError(error);
  return ok({ data }, 201);
}

export async function createProposal(req: NextRequest, propertyId: string) {
  const parsed = await parseJson(req, proposalInputSchema);
  if (parsed.response) return parsed.response;
  const { ctx, response } = await requireContext(req);
  if (response) return response;
  const access = await requirePropertyAccess(ctx, propertyId, ["landlord", "agent"]);
  if (access.response) return access.response;
  const input = parsed.data;
  const { data, error } = await ctx.supabase.from("proposals").insert({
    property_id: propertyId,
    proposal_type: input.proposalType,
    title: input.title,
    description: input.description,
    proposed_by: getUserId(ctx),
    recipient_user_id: input.recipientUserId ?? null,
    status: input.status,
    financial_summary: input.financialSummary,
    terms: input.terms,
    valid_until: input.validUntil ?? null,
  }).select("*").single();
  if (error) return supabaseError(error);
  return ok({ data }, 201);
}

export async function createContract(req: NextRequest, propertyId: string) {
  const parsed = await parseJson(req, contractInputSchema);
  if (parsed.response) return parsed.response;
  const { ctx, response } = await requireContext(req);
  if (response) return response;
  const access = await requirePropertyAccess(ctx, propertyId, ["landlord", "agent"]);
  if (access.response) return access.response;
  const input = parsed.data;
  const terms = {
    draftNotice: "DRAFT - Requires human/legal review before execution",
    ...input.terms,
  };
  const { data, error } = await ctx.supabase.from("contracts").insert({
    property_id: propertyId,
    proposal_id: input.proposalId ?? null,
    contract_type: input.contractType,
    tenant_user_id: input.tenantUserId ?? null,
    landlord_user_id: input.landlordUserId ?? null,
    agent_user_id: input.agentUserId ?? null,
    terms,
    effective_from: input.effectiveFrom ?? null,
    effective_to: input.effectiveTo ?? null,
    created_by: getUserId(ctx),
  }).select("*").single();
  if (error) return supabaseError(error);
  return ok({ data }, 201);
}

export async function getEnergyControls(req: NextRequest, propertyId: string) {
  const { ctx, response } = await requireContext(req);
  if (response) return response;
  const access = await requirePropertyAccess(ctx, propertyId);
  if (access.response) return access.response;
  const [{ data: settings }, { data: commands }] = await Promise.all([
    ctx.supabase.from("energy_control_settings").select("*").eq("property_id", propertyId).maybeSingle(),
    ctx.supabase.from("energy_control_commands").select("*").eq("property_id", propertyId).order("requested_at", { ascending: false }).limit(50),
  ]);
  return ok({ settings, commands });
}

export async function putEnergyControls(req: NextRequest, propertyId: string) {
  const parsed = await parseJson(req, controlSettingsSchema);
  if (parsed.response) return parsed.response;
  const { ctx, response } = await requireContext(req);
  if (response) return response;
  const access = await requirePropertyAccess(ctx, propertyId, ["landlord", "agent"]);
  if (access.response) return access.response;
  const { data, error } = await ctx.supabase.from("energy_control_settings").upsert({
    property_id: propertyId,
    mode: parsed.data.mode,
    battery_min_reserve_pct: parsed.data.batteryMinReservePct,
    allow_grid_export: parsed.data.allowGridExport,
    max_grid_import_kw: parsed.data.maxGridImportKw ?? null,
    updated_by: getUserId(ctx),
  }, { onConflict: "property_id" }).select("*").single();
  if (error) return supabaseError(error);
  return ok({ data });
}

export async function createControlCommand(req: NextRequest, propertyId: string) {
  const parsed = await parseJson(req, controlCommandSchema);
  if (parsed.response) return parsed.response;
  const { ctx, response } = await requireContext(req);
  if (response) return response;
  const access = await requirePropertyAccess(ctx, propertyId, ["landlord", "agent"]);
  if (access.response) return access.response;
  const provider = new MockEnergyControlProvider();
  const providerResult = await provider.sendCommand(parsed.data.commandType, parsed.data.payload);
  const { data, error } = await ctx.supabase.from("energy_control_commands").insert({
    property_id: propertyId,
    command_type: parsed.data.commandType,
    payload: parsed.data.payload,
    status: providerResult.acknowledged ? "acknowledged" : "failed",
    requested_by: getUserId(ctx),
    processed_at: new Date().toISOString(),
    response: providerResult.response,
  }).select("*").single();
  if (error) return supabaseError(error);
  return ok({ data }, 201);
}
