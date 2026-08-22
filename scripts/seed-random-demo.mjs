import { randomUUID } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { createClient } from "@supabase/supabase-js";

const root = process.cwd();

function loadEnvFile(fileName) {
  const filePath = path.join(root, fileName);
  if (!fs.existsSync(filePath)) return;

  const raw = fs.readFileSync(filePath, "utf8");
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match) continue;
    const [, key, value] = match;
    if (!process.env[key]) {
      process.env[key] = value.replace(/^['"]|['"]$/g, "");
    }
  }
}

loadEnvFile(".env.local");
loadEnvFile(".env");
loadEnvFile(".env.example");

const supabaseUrl = process.env.SUPABASE_URL;
const secretKey = process.env.SUPABASE_SECRET_KEY;

if (!supabaseUrl || !secretKey || secretKey.includes("your_secret_key") || secretKey.includes("replace-with")) {
  console.error("Missing real SUPABASE_URL / SUPABASE_SECRET_KEY. Add them to .env.local or export them first.");
  process.exit(1);
}

const supabase = createClient(supabaseUrl, secretKey, {
  auth: {
    persistSession: false,
    autoRefreshToken: false,
  },
});

const runId = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 12);
const suburb = randomChoice(["Bellambi", "Wollongong", "Fairy Meadow", "Thirroul", "Corrimal"]);
const propertyId = randomUUID();
const secondPropertyId = randomUUID();
const meterId = randomUUID();

const users = {
  tenant: {
    email: `tenant.${runId}@example.com`,
    name: "Random Tenant",
    password: `Demo-${runId}-Tenant!`,
  },
  landlord: {
    email: `landlord.${runId}@example.com`,
    name: "Random Landlord",
    password: `Demo-${runId}-Landlord!`,
  },
  agent: {
    email: `agent.${runId}@example.com`,
    name: "Random Agent",
    password: `Demo-${runId}-Agent!`,
  },
};

function randomChoice(values) {
  return values[Math.floor(Math.random() * values.length)];
}

function round(value, places = 3) {
  const factor = 10 ** places;
  return Math.round(value * factor) / factor;
}

async function must(label, promise) {
  const { data, error } = await promise;
  if (error) {
    console.error(`${label} failed:`, error.message);
    process.exit(1);
  }
  return data;
}

async function createUser(kind) {
  const user = users[kind];
  const created = await supabase.auth.admin.createUser({
    email: user.email,
    password: user.password,
    email_confirm: true,
    user_metadata: { full_name: user.name },
  });

  if (created.error) {
    console.error(`create ${kind} user failed:`, created.error.message);
    process.exit(1);
  }

  return created.data.user;
}

function buildReadings() {
  const readings = [];
  const now = new Date();
  now.setMinutes(0, 0, 0);
  const start = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
  let battery = 50 + Math.random() * 20;

  for (let time = start.getTime(); time <= now.getTime(); time += 60 * 60 * 1000) {
    const intervalStart = new Date(time);
    const intervalEnd = new Date(time + 60 * 60 * 1000);
    const hour = intervalStart.getHours();
    const daylight = hour >= 6 && hour <= 18 ? Math.sin(((hour - 6) / 12) * Math.PI) : 0;
    const eveningBoost = hour >= 17 && hour <= 22 ? 0.65 : 0;
    const morningBoost = hour >= 6 && hour <= 9 ? 0.25 : 0;
    const consumption = Math.max(0.12, 0.42 + eveningBoost + morningBoost + Math.random() * 0.18);
    const solar = Math.max(0, daylight * (2.2 + Math.random() * 1.5));
    const gridImport = Math.max(0, consumption - solar * 0.72);
    const gridExport = Math.max(0, solar - consumption);
    battery = Math.min(100, Math.max(0, battery + solar * 3.2 - consumption * 2.1 - (hour > 18 ? 1.4 : 0)));

    readings.push({
      property_id: propertyId,
      meter_id: meterId,
      interval_start: intervalStart.toISOString(),
      interval_end: intervalEnd.toISOString(),
      consumption_kwh: round(consumption),
      solar_generation_kwh: round(solar),
      grid_import_kwh: round(gridImport),
      grid_export_kwh: round(gridExport),
      battery_soc_pct: round(battery, 1),
      source: "mock",
    });
  }

  return readings;
}

const tenant = await createUser("tenant");
const landlord = await createUser("landlord");
const agent = await createUser("agent");

await must(
  "profiles",
  supabase.from("profiles").upsert([
    { id: tenant.id, full_name: users.tenant.name, phone: "+61 400 010 001" },
    { id: landlord.id, full_name: users.landlord.name, phone: "+61 400 010 002" },
    { id: agent.id, full_name: users.agent.name, phone: "+61 400 010 003" },
  ])
);

await must(
  "properties",
  supabase.from("properties").insert([
    {
      id: propertyId,
      name: `${suburb} Random Solar Rental ${runId}`,
      address_line_1: `${Math.floor(10 + Math.random() * 80)} Demo Circuit`,
      suburb,
      state: "NSW",
      postcode: randomChoice(["2500", "2518", "2519", "2515"]),
      country: "Australia",
      latitude: round(-34.42 + Math.random() * 0.12, 6),
      longitude: round(150.86 + Math.random() * 0.1, 6),
      timezone: "Australia/Sydney",
      roof_area_m2: round(90 + Math.random() * 80, 1),
      usable_roof_area_m2: round(55 + Math.random() * 45, 1),
    },
    {
      id: secondPropertyId,
      name: `Private Landlord Property ${runId}`,
      address_line_1: `${Math.floor(1 + Math.random() * 90)} Control Street`,
      suburb: "Wollongong",
      state: "NSW",
      postcode: "2500",
      country: "Australia",
      timezone: "Australia/Sydney",
      roof_area_m2: round(80 + Math.random() * 60, 1),
      usable_roof_area_m2: round(40 + Math.random() * 40, 1),
    },
  ])
);

await must(
  "memberships",
  supabase.from("property_memberships").insert([
    { property_id: propertyId, user_id: tenant.id, role: "tenant", status: "active" },
    { property_id: propertyId, user_id: landlord.id, role: "landlord", status: "active" },
    { property_id: propertyId, user_id: agent.id, role: "agent", status: "active" },
    { property_id: secondPropertyId, user_id: landlord.id, role: "landlord", status: "active" },
  ])
);

await must(
  "meter",
  supabase.from("meters").insert({
    id: meterId,
    property_id: propertyId,
    external_meter_id: `RANDOM-${runId}`,
    meter_type: "hybrid",
    provider: "random-demo",
    status: "active",
    metadata: { interval: "hour", generatedAt: new Date().toISOString() },
  })
);

const tariffId = randomUUID();
const gridRateCents = round(28 + Math.random() * 16, 2);
const gridRatePerKwh = gridRateCents / 100;
const feedInRate = round(0.06 + Math.random() * 0.04, 4);
const dailySupplyCharge = round(0.9 + Math.random() * 0.5, 2);
await must(
  "tariff",
  supabase.from("energy_tariffs").insert({
    id: tariffId,
    property_id: propertyId,
    name: "Random Demo Solar Tariff",
    usage_rate_per_kwh: round(gridRatePerKwh, 4),
    grid_rate_cents_per_kwh: gridRateCents,
    feed_in_rate_per_kwh: feedInRate,
    daily_supply_charge: dailySupplyCharge,
    currency: "AUD",
    valid_from: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString(),
    created_by: landlord.id,
  })
);

const readings = buildReadings();
for (let i = 0; i < readings.length; i += 500) {
  await must(
    `energy readings ${i}`,
    supabase.from("energy_readings").insert(readings.slice(i, i + 500))
  );
}

const totals = readings.reduce(
  (acc, row) => {
    acc.consumption += row.consumption_kwh;
    acc.solar += row.solar_generation_kwh;
    acc.import += row.grid_import_kwh;
    acc.export += row.grid_export_kwh;
    return acc;
  },
  { consumption: 0, solar: 0, import: 0, export: 0 }
);

const usageCost = round(totals.import * gridRatePerKwh, 2);
const supplyCost = round(30 * dailySupplyCharge, 2);
const solarCredit = round(totals.export * feedInRate, 2);
const totalAmount = round(Math.max(0, usageCost + supplyCost - solarCredit), 2);
const estimatedSavings = round(Math.max(0, totals.solar - totals.export) * gridRatePerKwh + solarCredit, 2);

await must(
  "bill",
  supabase.from("bills").insert({
    property_id: propertyId,
    tenant_user_id: tenant.id,
    tariff_id: tariffId,
    period_start: readings[0].interval_start,
    period_end: readings.at(-1).interval_end,
    consumption_kwh: round(totals.consumption, 2),
    solar_generation_kwh: round(totals.solar, 2),
    grid_import_kwh: round(totals.import, 2),
    grid_export_kwh: round(totals.export, 2),
    usage_cost: usageCost,
    supply_cost: supplyCost,
    solar_credit: solarCredit,
    total_amount: totalAmount,
    estimated_savings: estimatedSavings,
    carbon_avoided_kg: round(totals.solar * 0.68, 2),
    status: "issued",
  })
);

await must(
  "solar assessment",
  supabase.from("solar_assessments").insert({
    property_id: propertyId,
    roof_area_m2: 125,
    usable_roof_area_m2: 82,
    estimated_panel_count: 41,
    estimated_system_kw: 18.04,
    estimated_annual_generation_kwh: 26158,
    estimated_installation_cost: 26158,
    estimated_annual_savings: 6900,
    estimated_payback_years: 3.79,
    estimated_roi_pct: 427.6,
    estimated_carbon_reduction_kg_year: 17787,
    assumptions: {
      panelWattageW: 440,
      panelAreaM2: 2,
      specificAnnualYieldKwhPerKw: 1450,
      gridEmissionsKgPerKwh: 0.68,
      generatedBy: "backend/scripts/seed-random-demo.mjs",
    },
    status: "completed",
    created_by: landlord.id,
  })
);

await must(
  "lease request",
  supabase.from("lease_requests").insert({
    property_id: propertyId,
    tenant_user_id: tenant.id,
    request_type: "random_demo_request",
    message: "Please review the randomly seeded solar sharing proposal.",
    status: "submitted",
  })
);

await must(
  "proposal",
  supabase.from("proposals").insert({
    property_id: propertyId,
    proposal_type: "ppa",
    title: `Random PPA Proposal ${runId}`,
    description: "Randomly generated demo proposal for Supabase-backed dashboard testing.",
    proposed_by: landlord.id,
    recipient_user_id: tenant.id,
    status: "sent",
    financial_summary: { estimatedSavings, totalAmount, currency: "AUD" },
    terms: { draftNotice: "DRAFT - Requires human/legal review before execution" },
    valid_until: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
  })
);

await must(
  "control settings",
  supabase.from("energy_control_settings").insert({
    property_id: propertyId,
    mode: "automatic",
    battery_min_reserve_pct: 20,
    allow_grid_export: true,
    max_grid_import_kw: 8,
    updated_by: landlord.id,
  })
);

console.log("Random Supabase demo data created.");
console.log(`Property ID: ${propertyId}`);
console.log(`Tenant login: ${users.tenant.email} / ${users.tenant.password}`);
console.log(`Landlord login: ${users.landlord.email} / ${users.landlord.password}`);
console.log(`Agent login: ${users.agent.email} / ${users.agent.password}`);
