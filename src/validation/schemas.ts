import { z } from "zod";

export const uuidSchema = z.string().uuid();
export const isoDateSchema = z.string().datetime({ offset: true });
export const nonNegativeNumber = z.coerce.number().finite().min(0);
export const percentage = z.coerce.number().finite().min(0).max(100);

export const periodQuerySchema = z.object({
  from: isoDateSchema.optional(),
  to: isoDateSchema.optional(),
  granularity: z.enum(["hour", "day", "week", "month"]).default("day"),
});

export const paginationQuerySchema = z.object({
  from: isoDateSchema.optional(),
  to: isoDateSchema.optional(),
  limit: z.coerce.number().int().min(1).max(500).default(200),
  cursor: isoDateSchema.optional(),
});

export const energyReadingInputSchema = z
  .object({
    meterId: uuidSchema.nullish(),
    intervalStart: isoDateSchema,
    intervalEnd: isoDateSchema,
    consumptionKwh: nonNegativeNumber.default(0),
    solarGenerationKwh: nonNegativeNumber.default(0),
    solarConsumedByTenantKwh: nonNegativeNumber.nullish(),
    gridImportKwh: nonNegativeNumber.default(0),
    gridExportKwh: nonNegativeNumber.default(0),
    batteryChargeKwh: nonNegativeNumber.default(0),
    batteryDischargeKwh: nonNegativeNumber.default(0),
    batterySocPct: percentage.nullish(),
    finalizedAt: isoDateSchema.nullish(),
    source: z.enum(["mock", "meter_api", "manual", "simulation"]).default("manual"),
  })
  .refine((value) => new Date(value.intervalEnd) > new Date(value.intervalStart), {
    message: "intervalEnd must be after intervalStart",
    path: ["intervalEnd"],
  })
  .refine(
    (value) =>
      value.solarConsumedByTenantKwh == null ||
      value.solarConsumedByTenantKwh <= value.consumptionKwh + 0.001,
    {
      message: "solarConsumedByTenantKwh cannot exceed interval consumption",
      path: ["solarConsumedByTenantKwh"],
    }
  )
  .refine(
    (value) =>
      value.solarConsumedByTenantKwh == null ||
      value.solarConsumedByTenantKwh <= value.solarGenerationKwh + 0.001,
    {
      message: "solarConsumedByTenantKwh cannot exceed interval solar generation",
      path: ["solarConsumedByTenantKwh"],
    }
  );

export const meterIngestionSchema = z.object({
  readings: z.array(energyReadingInputSchema.extend({ propertyId: uuidSchema })).min(1).max(1000),
});

export const tariffInputSchema = z.object({
  name: z.string().min(1).max(120),
  usageRatePerKwh: nonNegativeNumber,
  gridRateCentsPerKwh: nonNegativeNumber.optional(),
  feedInRatePerKwh: nonNegativeNumber.default(0),
  dailySupplyCharge: nonNegativeNumber.default(0),
  currency: z.string().min(3).max(3).default("AUD"),
  validFrom: isoDateSchema,
  validTo: isoDateSchema.nullish(),
});

export const priceAdjustmentInputSchema = z.object({
  previousTariffId: uuidSchema.nullish(),
  proposedUsageRate: nonNegativeNumber.nullish(),
  proposedFeedInRate: nonNegativeNumber.nullish(),
  proposedDailyCharge: nonNegativeNumber.nullish(),
  reason: z.string().max(1000).nullish(),
  effectiveFrom: isoDateSchema,
  status: z.enum(["draft", "pending"]).default("draft"),
});

export const priceAdjustmentPatchSchema = z.object({
  status: z.enum(["draft", "pending", "approved", "rejected", "applied"]),
  reason: z.string().max(1000).optional(),
});

export const solarAssessmentInputSchema = z.object({
  imagePath: z.string().min(1).nullish(),
  imageSource: z.string().min(1).nullish(),
  roofAreaM2: nonNegativeNumber.nullish(),
  usableRoofAreaM2: nonNegativeNumber.optional(),
  assumptions: z.record(z.string(), z.unknown()).default({}),
});

export const leaseRequestInputSchema = z.object({
  requestType: z.string().min(1).max(120),
  message: z.string().min(1).max(5000),
});

export const leaseRequestPatchSchema = z.object({
  status: z.enum(["under_review", "approved", "rejected", "cancelled"]),
  reviewNotes: z.string().max(5000).nullish(),
});

export const proposalInputSchema = z.object({
  proposalType: z.enum(["solar", "energy_price", "ppa", "lease"]),
  title: z.string().min(1).max(160),
  description: z.string().min(1).max(5000),
  recipientUserId: uuidSchema.nullish(),
  status: z.enum(["draft", "sent"]).default("draft"),
  financialSummary: z.record(z.string(), z.unknown()).default({}),
  terms: z.record(z.string(), z.unknown()).default({}),
  validUntil: isoDateSchema.nullish(),
});

export const proposalPatchSchema = z.object({
  status: z.enum(["draft", "sent", "accepted", "rejected", "expired"]),
  terms: z.record(z.string(), z.unknown()).optional(),
});

export const contractInputSchema = z.object({
  proposalId: uuidSchema.nullish(),
  contractType: z.enum(["ppa", "lease_amendment", "energy_agreement"]),
  tenantUserId: uuidSchema.nullish(),
  landlordUserId: uuidSchema.nullish(),
  agentUserId: uuidSchema.nullish(),
  effectiveFrom: z.string().date().nullish(),
  effectiveTo: z.string().date().nullish(),
  terms: z.record(z.string(), z.unknown()).default({}),
});

export const controlSettingsSchema = z.object({
  mode: z.enum(["automatic", "self_consumption", "backup", "manual"]),
  batteryMinReservePct: percentage,
  allowGridExport: z.boolean(),
  maxGridImportKw: nonNegativeNumber.nullish(),
});

export const controlCommandSchema = z.object({
  commandType: z.string().min(1).max(120),
  payload: z.record(z.string(), z.unknown()).default({}),
});
