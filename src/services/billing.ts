export interface BillCalculationInput {
  periodStart: Date;
  periodEnd: Date;
  gridImportKwh: number;
  gridExportKwh: number;
  consumptionKwh: number;
  solarGenerationKwh: number;
  usageRatePerKwh: number;
  feedInRatePerKwh: number;
  dailySupplyCharge: number;
  carbonKgPerKwh: number;
}

export interface BillCalculation {
  usageCost: number;
  supplyCost: number;
  solarCredit: number;
  totalAmount: number;
  estimatedSavings: number;
  carbonAvoidedKg: number;
}

function money(value: number) {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

export function calculateBill(input: BillCalculationInput): BillCalculation {
  const msPerDay = 24 * 60 * 60 * 1000;
  const billableDays = Math.max(1, Math.ceil((input.periodEnd.getTime() - input.periodStart.getTime()) / msPerDay));
  const usageCost = money(input.gridImportKwh * input.usageRatePerKwh);
  const supplyCost = money(billableDays * input.dailySupplyCharge);
  const solarCredit = money(input.gridExportKwh * input.feedInRatePerKwh);
  const totalAmount = money(Math.max(0, usageCost + supplyCost - solarCredit));
  const solarSelfConsumptionKwh = Math.max(0, input.solarGenerationKwh - input.gridExportKwh);
  const estimatedSavings = money(solarSelfConsumptionKwh * input.usageRatePerKwh + solarCredit);
  const carbonAvoidedKg = Math.round(input.solarGenerationKwh * input.carbonKgPerKwh * 100) / 100;

  return { usageCost, supplyCost, solarCredit, totalAmount, estimatedSavings, carbonAvoidedKg };
}
