export interface SolarAssumptions {
  panelWattageW: number;
  panelAreaM2: number;
  usableRoofPercentage: number;
  specificAnnualYieldKwhPerKw: number;
  installationCostPerKw: number;
  electricityRatePerKwh: number;
  feedInRatePerKwh: number;
  selfConsumptionRatio: number;
  annualDegradationPct: number;
  analysisPeriodYears: number;
  gridEmissionsKgPerKwh: number;
}

export interface SolarEstimateInput {
  roofAreaM2?: number | null;
  usableRoofAreaM2?: number | null;
  assumptions?: Partial<SolarAssumptions>;
}

export interface SolarEstimate {
  usableRoofAreaM2: number;
  estimatedPanelCount: number;
  estimatedSystemKw: number;
  estimatedAnnualGenerationKwh: number;
  estimatedInstallationCost: number;
  estimatedAnnualSavings: number;
  estimatedPaybackYears: number;
  estimatedRoiPct: number;
  estimatedCarbonReductionKgYear: number;
  assumptions: SolarAssumptions;
}

export const defaultSolarAssumptions: SolarAssumptions = {
  panelWattageW: 440,
  panelAreaM2: 2.0,
  usableRoofPercentage: 0.65,
  specificAnnualYieldKwhPerKw: 1450,
  installationCostPerKw: 1450,
  electricityRatePerKwh: 0.34,
  feedInRatePerKwh: 0.08,
  selfConsumptionRatio: 0.72,
  annualDegradationPct: 0.005,
  analysisPeriodYears: 20,
  gridEmissionsKgPerKwh: 0.68,
};

function round(value: number, places = 2) {
  const factor = 10 ** places;
  return Math.round((value + Number.EPSILON) * factor) / factor;
}

export function estimateSolar(input: SolarEstimateInput): SolarEstimate {
  const assumptions = { ...defaultSolarAssumptions, ...input.assumptions };
  const usableRoofAreaM2 =
    input.usableRoofAreaM2 ?? Math.max(0, input.roofAreaM2 ?? 0) * assumptions.usableRoofPercentage;
  const estimatedPanelCount = Math.floor(usableRoofAreaM2 / assumptions.panelAreaM2);
  const estimatedSystemKw = round((estimatedPanelCount * assumptions.panelWattageW) / 1000);
  const estimatedAnnualGenerationKwh = round(estimatedSystemKw * assumptions.specificAnnualYieldKwhPerKw);
  const estimatedInstallationCost = round(estimatedSystemKw * assumptions.installationCostPerKw);
  const selfConsumedKwh = estimatedAnnualGenerationKwh * assumptions.selfConsumptionRatio;
  const exportedKwh = estimatedAnnualGenerationKwh - selfConsumedKwh;
  const estimatedAnnualSavings = round(
    selfConsumedKwh * assumptions.electricityRatePerKwh + exportedKwh * assumptions.feedInRatePerKwh
  );
  const estimatedPaybackYears = estimatedAnnualSavings > 0 ? round(estimatedInstallationCost / estimatedAnnualSavings) : 0;
  const lifetimeSavings = estimatedAnnualSavings * assumptions.analysisPeriodYears;
  const estimatedRoiPct =
    estimatedInstallationCost > 0 ? round(((lifetimeSavings - estimatedInstallationCost) / estimatedInstallationCost) * 100) : 0;
  const estimatedCarbonReductionKgYear = round(estimatedAnnualGenerationKwh * assumptions.gridEmissionsKgPerKwh);

  return {
    usableRoofAreaM2: round(usableRoofAreaM2),
    estimatedPanelCount,
    estimatedSystemKw,
    estimatedAnnualGenerationKwh,
    estimatedInstallationCost,
    estimatedAnnualSavings,
    estimatedPaybackYears,
    estimatedRoiPct,
    estimatedCarbonReductionKgYear,
    assumptions,
  };
}
