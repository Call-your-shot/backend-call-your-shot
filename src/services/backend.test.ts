import { describe, expect, it } from "vitest";
import { canIngestMeterData, canManageProperty, canReadProperty, canTenantCreateLeaseRequest } from "@backend/services/authorization";
import { calculateBill } from "@backend/services/billing";
import { estimateSolar } from "@backend/services/solar-estimator";
import { energyReadingInputSchema } from "@backend/validation/schemas";

describe("property authorization matrix", () => {
  it("tenant can read assigned property and create lease requests but cannot manage tariffs", () => {
    expect(canReadProperty("tenant")).toBe(true);
    expect(canTenantCreateLeaseRequest("tenant")).toBe(true);
    expect(canManageProperty("tenant")).toBe(false);
  });

  it("landlord and assigned agent can manage their property", () => {
    expect(canManageProperty("landlord")).toBe(true);
    expect(canManageProperty("agent")).toBe(true);
  });

  it("unrelated users cannot read or manage a property", () => {
    expect(canReadProperty(null)).toBe(false);
    expect(canManageProperty(null)).toBe(false);
  });

  it("meter ingestion rejects normal tenant access", () => {
    expect(canIngestMeterData("user")).toBe(false);
    expect(canIngestMeterData("secret")).toBe(true);
  });
});

describe("energy validation", () => {
  it("rejects negative readings", () => {
    const parsed = energyReadingInputSchema.safeParse({
      intervalStart: "2026-08-01T00:00:00.000Z",
      intervalEnd: "2026-08-01T01:00:00.000Z",
      consumptionKwh: -1,
    });
    expect(parsed.success).toBe(false);
  });

  it("rejects invalid battery SOC", () => {
    const parsed = energyReadingInputSchema.safeParse({
      intervalStart: "2026-08-01T00:00:00.000Z",
      intervalEnd: "2026-08-01T01:00:00.000Z",
      batterySocPct: 101,
    });
    expect(parsed.success).toBe(false);
  });
});

describe("billing", () => {
  it("calculates currency with cent rounding", () => {
    const bill = calculateBill({
      periodStart: new Date("2026-08-01T00:00:00.000Z"),
      periodEnd: new Date("2026-08-31T00:00:00.000Z"),
      gridImportKwh: 100,
      gridExportKwh: 20,
      consumptionKwh: 160,
      solarGenerationKwh: 80,
      usageRatePerKwh: 0.34,
      gridRateCentsPerKwh: 34,
      feedInRatePerKwh: 0.08,
      dailySupplyCharge: 1.12,
      carbonKgPerKwh: 0.68,
    });

    expect(bill).toEqual({
      usageCost: 34,
      supplyCost: 33.6,
      solarCredit: 1.6,
      totalAmount: 66,
      estimatedSavings: 22,
      carbonAvoidedKg: 54.4,
    });
  });

  it("uses grid cents rate for imported energy when battery is depleted", () => {
    const bill = calculateBill({
      periodStart: new Date("2026-08-01T00:00:00.000Z"),
      periodEnd: new Date("2026-08-02T00:00:00.000Z"),
      gridImportKwh: 10,
      gridExportKwh: 0,
      consumptionKwh: 10,
      solarGenerationKwh: 0,
      usageRatePerKwh: 0.2,
      gridRateCentsPerKwh: 40,
      feedInRatePerKwh: 0,
      dailySupplyCharge: 1,
      carbonKgPerKwh: 0.68,
    });

    expect(bill.usageCost).toBe(4);
    expect(bill.totalAmount).toBe(5);
  });
});

describe("solar estimator", () => {
  it("is deterministic for identical assumptions", () => {
    const input = { roofAreaM2: 100, assumptions: { panelWattageW: 400, panelAreaM2: 2 } };
    expect(estimateSolar(input)).toEqual(estimateSolar(input));
  });

  it("calculates expected panel count and ROI", () => {
    const estimate = estimateSolar({ usableRoofAreaM2: 20, assumptions: { panelWattageW: 500, panelAreaM2: 2 } });
    expect(estimate.estimatedPanelCount).toBe(10);
    expect(estimate.estimatedSystemKw).toBe(5);
    expect(estimate.estimatedRoiPct).toBeGreaterThan(0);
  });
});
